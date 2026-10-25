#!/usr/bin/env python3
"""Build Folded Atlas: real bytes, synthetic geography, bounded runtime working set."""
import argparse
import json
import math
from pathlib import Path
try:
    from .build import ChunkWriter
except ImportError:
    from build import ChunkWriter

BIOMES = ['雾林', '沙洲', '雪原', '火山', '草甸', '盐湖', '苔原', '雨林']
PREFIX = ['沉默', '月白', '回声', '青铜', '远岫', '潮汐', '晚晴', '琥珀', '候鸟', '薄暮', '风信', '北辰', '石榴', '微光', '银杉', '松烟']
SUFFIX = ['之屿', '浅湾', '山脊', '环礁', '河口', '群峰', '岬角', '盆地', '长滩', '台地', '峡湾', '旷野', '丘陵', '海岸', '高地', '湿地']

def mix(n):
    n = ((n ^ (n >> 16)) * 0x45d9f3b) & 0xffffffff
    n = ((n ^ (n >> 16)) * 0x45d9f3b) & 0xffffffff
    return (n ^ (n >> 16)) & 0xffffffff

def record(i):
    s = mix(i + 7919)
    # These are authored simulation parameters, NOT measurements of real places.
    lat = round((s % 15000) / 100 - 75, 2)
    rain = 180 + ((s >> 8) % 3200)
    temp = round(29 - abs(lat) * .55 + ((s >> 16) % 100) / 20, 1)
    monthly = [round(temp + 8 * math.sin((m / 12) * math.tau + lat), 1) for m in range(12)]
    return [i, PREFIX[s % 16] + SUFFIX[(s >> 4) % 16], s, lat, rain, temp,
            200 + ((s >> 10) % 3800), monthly]

def build(count, html_path, out=None, worker_src=None, chunk_mib=20):
    if count < 256 or count > 2097152 or count % 256:
        raise ValueError('count must be a multiple of 256, between 256 and 2097152')
    if chunk_mib < 1 or chunk_mib > 24:
        raise ValueError('chunk-mib must be between 1 and 24')
    if bool(out) != bool(worker_src):
        raise ValueError('out and worker-src must be supplied together')
    template = Path(__file__).with_name('atlas.html').read_text(encoding='utf-8')
    start, end = template.replace('__COUNT__', str(count)).split('<!--ATLAS_DATA-->')
    target = Path(html_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Build deterministic inert chunks, never executable C.push(...) statements.
    with target.open('w', encoding='utf-8', newline='\n') as f:
        f.write(start)
        for block in range(count // 256):
            payload = json.dumps([record(i) for i in range(block * 256, (block + 1) * 256)], ensure_ascii=False, separators=(',', ':'))
            f.write('<script type="application/json" id="data-%d">%s</script>\n' % (block, payload))
        f.write(end)
    if out:
        writer = ChunkWriter(out, chunk_mib * 262144)
        with target.open(encoding='utf-8') as f:
            for line in f:
                writer.write(line)
        total, files = writer.close()
        manifest = Path(worker_src) / 'chunks.js'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text('export const CHUNKS = %s;\nexport const TOTAL_BYTES = %d;\n' % (json.dumps(files), total), encoding='utf-8')
        assert total == target.stat().st_size
    return target.stat().st_size

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count', type=int, default=65536)
    p.add_argument('--html', default='artifacts/folded-atlas.html')
    p.add_argument('--out')
    p.add_argument('--worker-src')
    p.add_argument('--chunk-mib', type=int, default=20)
    a = p.parse_args()
    try:
        print('HTML bytes:', build(a.count, a.html, a.out, a.worker_src, a.chunk_mib))
    except ValueError as e:
        p.error(str(e))
