"""Independently verify every inlined WAV against the generated sample manifest.
Usage: python tests/verify_echo.py artifacts/echo-workshop.html
No NumPy dependency; one sample at a time, including on the large edition.
"""
import argparse,base64,hashlib,io,json,re,wave
from pathlib import Path

def verify(path):
 path=Path(path);manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
 expected={x['id']:x for x in manifest['files']};seen=set();unique=set();total=0
 with path.open(encoding='utf-8') as f:
  for line in f:
   if not line.startswith('<script type="application/octet-stream"'):continue
   m=re.fullmatch(r'<script type="application/octet-stream" id="s-([a-z]+-\d+-\d+)">([A-Za-z0-9+/=]+)</script>\s*',line)
   assert m,'malformed inlined sample'
   key,encoded=m.groups();assert key in expected and key not in seen
   data=base64.b64decode(encoded,validate=True);digest=hashlib.sha256(data).hexdigest()
   assert len(data)==expected[key]['bytes'] and digest==expected[key]['sha256']
   assert digest not in unique
   with wave.open(io.BytesIO(data)) as w:
    c=manifest['configuration'];assert w.getnchannels()==(2 if c['stereo'] else 1)
    assert w.getsampwidth()==2 and w.getframerate()==c['rate'] and w.getnframes()>0
   total+=len(data);seen.add(key);unique.add(digest)
 assert seen==set(expected) and total==manifest['pcmWavBytes'] and path.stat().st_size==manifest['bytes']
 result={'file':path.name,'htmlBytes':path.stat().st_size,'verifiedUniqueWavs':len(seen),'wavBytes':total,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()}
 path.with_suffix('.verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('html');args=ap.parse_args();verify(args.html)
