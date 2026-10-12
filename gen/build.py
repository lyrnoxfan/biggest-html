#!/usr/bin/env python3
"""Build the world's biggest HTML: pure-code, zero-asset knowledge-universe exhibition site.

Reads real datasets from --data, emits one giant HTML split into <= --chunk-mib
MiB chunk files (split only at newline boundaries; every emitted line is a
complete, self-contained statement). Also writes worker/src/chunks.js manifest.

Usage:
  build.py --data ~/workspace/biggest-html/data --out /tmp/bigbuild \
      [--chunk-mib 20] [--max-cities 0] [--pi-digits 100000]
  --max-cities 0 means no limit.
"""
import argparse
import csv
import json
import os
import subprocess
import sys

# ---------------------------------------------------------------- chunk writer

class ChunkWriter:
    def __init__(self, outdir, max_bytes):
        self.outdir = outdir
        self.max_bytes = max_bytes
        os.makedirs(outdir, exist_ok=True)
        # A smaller rebuild must not leave old numbered chunks in the asset directory.
        for name in os.listdir(outdir):
            if name.startswith("chunk-") and name.endswith(".html") and name[6:-5].isdigit():
                os.remove(os.path.join(outdir, name))
        self.files = []
        self.cur = None
        self.cur_size = 0
        self.total = 0

    def _open_new(self):
        if self.cur:
            self.cur.close()
        name = "chunk-%05d.html" % len(self.files)
        self.cur = open(os.path.join(self.outdir, name), "w", encoding="utf-8")
        self.files.append(name)
        self.cur_size = 0

    def write(self, text):
        if self.cur is None:
            self._open_new()
        for line in text.splitlines(keepends=True):
            b = len(line.encode("utf-8"))
            if self.cur_size > 0 and self.cur_size + b > self.max_bytes:
                self._open_new()
            self.cur.write(line)
            self.cur_size += b
            self.total += b

    def close(self):
        if self.cur:
            self.cur.close()
            self.cur = None
        return self.total, self.files


def js_str(s):
    """JSON string literal, safe to embed in <script>."""
    return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------- data loaders

def load_cities(path, max_cities):
    """GeoNames allCountries.txt -> list of (lat, lon, pop, name), pop-desc."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 19:
                continue
            fcode = p[7]
            if not fcode.startswith("PPL"):
                continue
            try:
                lat = float(p[4]); lon = float(p[5]); pop = int(p[14] or 0)
            except ValueError:
                continue
            name = p[1] or p[2]
            if not name:
                continue
            rows.append((pop, lat, lon, name))
    rows.sort(key=lambda r: -r[0])
    if max_cities:
        rows = rows[:max_cities]
    return [(lat, lon, pop, name) for pop, lat, lon, name in rows]


def load_stars(path, mag_limit=6.5):
    """HYG v3 csv -> list of (ra_deg, dec_deg, mag, name)."""
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                mag = float(row["mag"]); ra = float(row["ra"]); dec = float(row["dec"])
            except (ValueError, KeyError):
                continue
            if mag > mag_limit:
                continue
            rows.append((ra, dec, mag, row.get("proper") or ""))
    return rows


def load_hanzi(readings_path, irg_path):
    """Unihan kMandarin (+kHanyuPinyin fallback) + kRSUnicode
    -> list of (char, pinyin, radical, strokes)."""
    mand = {}
    with open(readings_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split("\t")
            if len(p) < 3:
                continue
            field, val = p[1], p[2].strip()
            if field == "kMandarin":
                cp = int(p[0][2:], 16)
                mand[cp] = val.split(" ")[0]
            elif field == "kHanyuPinyin":
                cp = int(p[0][2:], 16)
                if cp not in mand:
                    # format "10002.010:er4" or with tone marks
                    v = val.split(" ")[0]
                    if ":" in v:
                        v = v.split(":", 1)[1]
                    mand.setdefault(cp, v)
    rs = {}
    with open(irg_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split("\t")
            if len(p) >= 3 and p[1] == "kRSUnicode":
                cp = int(p[0][2:], 16)
                if cp in rs:
                    continue  # first value wins
                rad_st = p[2].strip().split(" ")[0].split(".")
                try:
                    rad = int(rad_st[0].rstrip("'"))
                    st = int(rad_st[1].rstrip("'"))
                except (ValueError, IndexError):
                    continue
                rs[cp] = (rad, st)
    out = []
    for cp in sorted(set(mand) & set(rs)):
        try:
            ch = chr(cp)
        except ValueError:
            continue
        rad, st = rs[cp]
        out.append((ch, mand[cp], rad, st))
    return out


def load_pi_digits(n):
    """First n digits of pi after the decimal point, via mpmath."""
    try:
        import mpmath
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "mpmath"], check=True)
        import mpmath
    mpmath.mp.dps = n + 10
    s = mpmath.nstr(mpmath.mp.pi, n + 10, strip_zeros=False)
    digits = s.replace(".", "")
    return digits[1:1 + n]  # drop leading "3", take n fractional digits


# ---------------------------------------------------------------- html shell

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="世界最最最大的 HTML：纯代码、零素材的知识宇宙展览站。天文、地理、数学、汉字、音乐、时间，全部由代码实时绘制。">
<title>世界最最最大的 HTML · 知识宇宙展览站</title>
<style>
:root{--bg:#050810;--bg2:#0a1020;--fg:#e8f1ff;--mut:#93a4c4;--acc:#7dd3fc;--acc2:#f0abfc;--card:rgba(255,255,255,.045);--line:rgba(125,211,252,.16)}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;line-height:1.7;overflow-x:hidden}
nav{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:50;display:flex;gap:4px;padding:8px 14px;border-radius:999px;background:rgba(10,16,32,.55);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid var(--line);box-shadow:0 8px 32px rgba(0,0,0,.45);max-width:96vw;overflow-x:auto}
nav a{color:var(--mut);text-decoration:none;font-size:13px;padding:7px 13px;border-radius:999px;white-space:nowrap;transition:.25s}
nav a:hover,nav a.on{color:#fff;background:rgba(125,211,252,.16)}
.hero{position:relative;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;overflow:hidden;background:radial-gradient(1200px 700px at 50% 20%,#0c1630 0%,var(--bg) 70%)}
#heroCv{position:absolute;inset:0;width:100%;height:100%}
.hero .sub{position:relative;z-index:2;color:var(--mut);margin-top:46vh;font-size:15px;letter-spacing:2px}
.chips{position:relative;z-index:2;display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:18px;padding:0 16px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:7px 16px;font-size:13px;color:var(--acc)}
.chip b{color:#fff;font-weight:700}
.scrolldown{position:absolute;bottom:26px;left:50%;transform:translateX(-50%);color:var(--mut);font-size:12px;letter-spacing:4px;animation:float 2.4s ease-in-out infinite}
@keyframes float{0%,100%{transform:translate(-50%,0)}50%{transform:translate(-50%,10px)}}
section.block{max-width:1180px;margin:0 auto;padding:110px 22px 40px}
.kicker{color:var(--acc);font-size:13px;letter-spacing:6px;margin-bottom:10px}
h2{font-size:clamp(26px,4.6vw,40px);font-weight:800;letter-spacing:2px;margin-bottom:12px;background:linear-gradient(92deg,#fff,#7dd3fc 60%,#f0abfc);-webkit-background-clip:text;background-clip:text;color:transparent}
.desc{color:var(--mut);font-size:15px;max-width:860px;margin-bottom:22px}
.desc b{color:var(--fg)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:18px;backdrop-filter:blur(8px)}
canvas.cv{width:100%;border-radius:14px;background:#04060d;display:block}
.row{display:flex;gap:18px;flex-wrap:wrap}
.row>.panel{flex:1 1 320px}
.card{background:rgba(125,211,252,.07);border:1px solid var(--line);border-radius:16px;padding:16px 18px;font-size:14px}
.card h3{font-size:20px;margin-bottom:6px;color:#fff}
.card .en{color:var(--mut);font-size:12px;letter-spacing:2px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin-top:10px;font-size:13.5px}
.kv dt{color:var(--mut)}.kv dd{color:var(--fg)}
button.btn{background:linear-gradient(92deg,#38bdf8,#a78bfa);border:0;color:#06121f;font-weight:700;border-radius:999px;padding:10px 22px;font-size:14px;cursor:pointer;transition:.2s}
button.btn:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(125,211,252,.35)}
button.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--line)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.hzgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(58px,1fr));gap:8px;margin-top:14px}
.hz{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:26px;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:12px;cursor:pointer;transition:.15s}
.hz:hover{background:rgba(125,211,252,.18);transform:scale(1.08)}
.hzbig{font-size:84px;text-align:center;margin:6px 0}
input.search{width:100%;max-width:420px;background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:999px;color:#fff;padding:11px 20px;font-size:15px;outline:none}
input.search:focus{border-color:var(--acc)}
.clocks{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:12px}
.clock{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;text-align:center}
.clock .t{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;color:#fff}
.clock .c{font-size:13px;color:var(--mut);margin-top:4px}
.clock .z{font-size:11px;color:#5b6b8c}
.notes{margin-top:16px;font-size:12.5px;color:#5b6b8c}
footer{border-top:1px solid var(--line);margin-top:80px;padding:46px 22px 70px;text-align:center;color:var(--mut);font-size:13.5px}
footer .big{font-size:15px;color:var(--fg);margin-bottom:10px}
.stat{display:inline-block;margin:6px 10px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 18px}
.stat b{color:var(--acc);font-size:17px}
.sig{margin-top:22px;font-size:14px;color:var(--acc2);letter-spacing:3px}
@media(max-width:640px){
 nav{top:8px;padding:5px 7px;max-width:calc(100vw - 16px)}
 nav a{font-size:12px;padding:6px 9px}
 section.block{padding:84px 14px 28px}
 .panel{padding:12px;border-radius:16px}
 .row{gap:12px}
 .hero .sub{margin-top:44vh;font-size:12px;letter-spacing:1px;padding:0 16px}
 .chips{gap:6px}
 .chip{padding:6px 10px;font-size:11px}
 .hzgrid{grid-template-columns:repeat(auto-fill,minmax(48px,1fr));gap:6px}
 .clock .t{font-size:21px}
}
@media(prefers-reduced-motion:reduce){
 html{scroll-behavior:auto}
 .scrolldown{animation:none}
 nav a,button.btn,.hz{transition:none}
}
</style>
</head>
<body>
<nav id="nav">
<a href="#hero">知识宇宙</a><a href="#planets">天文馆</a><a href="#earth">地球馆</a><a href="#math">数学馆</a><a href="#hanzi">汉字馆</a><a href="#music">音乐馆</a><a href="#clocks">世界时钟</a>
</nav>
<div class="hero" id="hero">
<canvas id="heroCv"></canvas>
<div class="sub">纯代码 · 零素材 · 所有视觉均由 Canvas / SVG / CSS 实时绘制</div>
<div class="chips" id="chips"></div>
<div class="scrolldown">向下滚动 ▼</div>
</div>
<section class="block" id="planets">
<div class="kicker">PLANETARIUM</div><h2>天文馆 · 太阳系</h2>
<div class="desc">八大行星的<b>真实数据</b>：直径、与太阳距离、公转周期均来自天文观测值。轨道半径按<b>对数缩放</b>以便同屏展示，公转角速度按<b>真实周期比例</b>运转（水星 88 天、海王星 164.8 年）。背景星点为 HYG 星表中的<b>肉眼可见恒星</b>（按赤经赤纬投影）。点击任意行星查看数据卡。</div>
<div class="row">
<div class="panel" style="flex:2 1 560px"><canvas class="cv" id="planetCv" height="560"></canvas></div>
<div class="panel" style="flex:1 1 280px"><div class="card" id="planetCard"><h3>点击行星</h3><div class="en">CLICK A PLANET</div><p style="color:var(--mut);font-size:13px;margin-top:8px">在左侧星图中点击任意行星，这里会显示它的真实物理数据。</p></div></div>
</div>
<div class="notes">数据：NASA 行星参数表（直径/轨道半长轴/公转周期/自转周期/卫星数均为近似值）；恒星：HYG v3 星表。</div>
</section>
<section class="block" id="earth">
<div class="kicker">TERRA</div><h2>地球馆 · 旋转的人类聚居点</h2>
<div class="desc">下方每一个光点都是 <b>GeoNames 地理数据库</b>中的一个真实居民点（PPL 类），按经纬度投影到旋转地球仪上。光点大小对应<b>人口规模</b>。数据随页面分片陆续载入，右下角计数器实时显示已载入数量。</div>
<div class="panel"><canvas class="cv" id="earthCv" height="560"></canvas>
<div class="notes" style="display:flex;justify-content:space-between;flex-wrap:wrap"><span>数据源：GeoNames allCountries（Creative Commons Attribution 4.0）</span><span id="cityCount" style="color:var(--acc)">载入中…</span></div></div>
</section>
<section class="block" id="math">
<div class="kicker">MATHEMATICA</div><h2>数学馆 · 分形与圆周率</h2>
<div class="desc"><b>Mandelbrot 集</b>：z → z² + c 迭代的逃逸时间可视化，全部由 Canvas 逐像素实时计算。单击放大、双击复位，或开启自动巡游。<b>圆周率之舞</b>：取圆周率小数点后 {PIDIGITS} 位，每一位数字决定下一步的方向（数字 × 36°），走出的路径即是 π 的形状。</div>
<div class="row">
<div class="panel"><h3 style="margin-bottom:10px;font-size:16px">Mandelbrot 集</h3><canvas class="cv" id="mandelCv" height="440"></canvas>
<div class="toolbar"><button class="btn" id="mandelTour">自动巡游</button><button class="btn ghost" id="mandelReset">复位</button><span class="notes" id="mandelInfo" style="align-self:center">单击放大 · 双击复位</span></div></div>
<div class="panel"><h3 style="margin-bottom:10px;font-size:16px">圆周率之舞</h3><canvas class="cv" id="piCv" height="440"></canvas>
<div class="notes">π = 3.<span id="piText"></span>……</div></div>
</div>
</section>
<section class="block" id="hanzi">
<div class="kicker">HANZI</div><h2>汉字馆 · 字海</h2>
<div class="desc">收录 Unicode <b>Unihan 数据库</b>中有普通话读音的全部汉字 <b>{NHANZI}</b> 个。每个字标注<b>拼音</b>（kMandarin）、<b>部首序号</b>与<b>笔画数</b>（kRSUnicode）。在搜索框输入汉字或拼音即可筛选，点击单字查看大字卡。</div>
<div class="panel">
<input class="search" id="hzSearch" placeholder="搜索汉字或拼音，如：龙 / LONG">
<div class="toolbar"><span class="notes" id="hzCount"></span></div>
<div class="hzgrid" id="hzGrid"></div>
<div class="toolbar" style="justify-content:center"><button class="btn ghost" id="hzPrev">上一页</button><span class="notes" id="hzPage" style="align-self:center"></span><button class="btn ghost" id="hzNext">下一页</button></div>
<div class="card" id="hzCard" style="margin-top:14px"><h3>点击任意汉字</h3><div class="en">CLICK A CHARACTER</div></div>
</div>
<div class="notes">数据：Unicode Unihan（kMandarin 普通话读音，kRSUnicode 部首·笔画）。</div>
</section>
<section class="block" id="music">
<div class="kicker">MUSICA</div><h2>音乐馆 · 代码作曲</h2>
<div class="desc">《星海》——一段由代码写成的原创五声音阶旋律，无任何音频文件，全部经 <b>Web Audio API 实时合成</b>（三角波主音 + 正弦波泛音 + 包络）。点击播放，下方频谱为实时 Analyser 数据。</div>
<div class="panel">
<div class="toolbar"><button class="btn" id="playBtn">▶ 播放《星海》</button><span class="notes" id="nowPlaying" style="align-self:center"></span></div>
<canvas class="cv" id="musicCv" height="220"></canvas>
<div class="notes">作曲：纯代码（D 宫五声音阶：宫商角徵羽）。演奏：Web Audio OscillatorNode 实时合成。</div>
</div>
</section>
<section class="block" id="clocks">
<div class="kicker">HOROLOGIUM</div><h2>世界时钟</h2>
<div class="desc"><b>{NCLOCKS}</b> 座城市的实时时钟，时区为真实 IANA 时区数据库名称，由浏览器 <b>Intl API</b> 按你设备的本地时间换算。</div>
<div class="clocks" id="clockGrid"></div>
</section>
<footer>
<div class="big">世界最最最大的 HTML · 知识宇宙展览站</div>
<div id="footStats"></div>
<div class="notes" style="max-width:860px;margin:14px auto 0">数据来源：GeoNames（CC BY 4.0）、Unicode Unihan、HYG 恒星星表、NASA 行星参数。页面全部内容由代码生成与绘制，零图片、零外部资源。<br>本单页 HTML 共 <b id="footBytes"></b>，由 <b id="footChunks"></b> 个 ≤25MiB 分片在 Cloudflare 边缘拼接为一次响应发出。</div>
<div class="sig">lyrnox · 2026</div>
</footer>
"""

# ---------------------------------------------------------------- js app (1/2)

JS_APP_1 = r"""
<script>
"use strict";
const $=id=>document.getElementById(id);
const DPR=Math.min(2,window.devicePixelRatio||1);
const REDUCED_MOTION = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
function animateOnScreen(element, draw) {
 let visible = !("IntersectionObserver" in window), raf = 0, last = 0, drawn = false;
 function tick(now) {
  raf = 0;
  if (!visible || document.hidden || (REDUCED_MOTION && drawn)) return;
  if (!REDUCED_MOTION && now - last < 32) { raf = requestAnimationFrame(tick); return; }
  last = now;
  drawn = true;
  draw(now);
  if (!REDUCED_MOTION) raf = requestAnimationFrame(tick);
 }
 function sync() {
  if (visible && !document.hidden) {
   if (!raf && !(REDUCED_MOTION && drawn)) raf = requestAnimationFrame(tick);
  } else if (raf) {
   cancelAnimationFrame(raf);
   raf = 0;
  }
 }
 const observer = "IntersectionObserver" in window
  ? new IntersectionObserver(entries => { visible = entries.some(entry => entry.isIntersecting); sync(); }, {rootMargin:"100px"})
  : null;
 if (observer) observer.observe(element);
 document.addEventListener("visibilitychange", sync);
 window.addEventListener("resize", () => { drawn = false; sync(); }, {passive:true});
 window.addEventListener("biggest:data-ready", () => { drawn = false; sync(); });
 sync();
 return () => {
  if (raf) cancelAnimationFrame(raf);
  if (observer) observer.disconnect();
  document.removeEventListener("visibilitychange", sync);
 };
}
/* ---------- nav highlight ---------- */
(function(){const links=[...document.querySelectorAll('#nav a')];
const secs=links.map(a=>document.querySelector(a.getAttribute('href')));
function on(){let cur=0;secs.forEach((s,i)=>{if(s&&s.getBoundingClientRect().top<200)cur=i;});
links.forEach((a,i)=>a.classList.toggle('on',i===cur));}
window.addEventListener('scroll',on,{passive:true});on();})();
/* ---------- data holders (filled by later chunks) ---------- */
const S=[];   /* stars: [ra_deg,dec_deg,mag,name] */
const C=[];   /* cities: [lat,lon,pop,name] */
const H=[];   /* hanzi: [char,pinyin,radical,strokes] */
let PI="";    /* pi fractional digits */
/* ---------- hero particle text ---------- */
(function(){
const cv=$('heroCv'),ctx=cv.getContext('2d');let W,H,ps=[];
function build(){
 W=cv.width=cv.offsetWidth*DPR;H=cv.height=cv.offsetHeight*DPR;
 const off=document.createElement('canvas');off.width=W;off.height=H;
 const o=off.getContext('2d');o.fillStyle='#fff';o.textAlign='center';o.textBaseline='middle';
 const fs=Math.min(W/8.5,H/4.6);
 o.font='800 '+fs+'px "PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
 o.fillText('世界最最最大的 HTML',W/2,H/2-fs*0.42);
 o.font='400 '+fs*0.26+'px "PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
 o.fillStyle='#9db4d8';o.fillText('知识宇宙展览站 · 纯代码零素材',W/2,H/2+fs*0.42);
 const d=o.getImageData(0,0,W,H).data,gap=Math.max(3,Math.round(3*DPR)),tg=[];
 for(let y=0;y<H;y+=gap)for(let x=0;x<W;x+=gap)if(d[(y*W+x)*4+3]>128)tg.push([x,y]);
 const stride=Math.max(1,Math.floor(tg.length/16000));
 ps=[];
 for(let i=0;i<tg.length;i+=stride)ps.push({x:Math.random()*W,y:Math.random()*H,tx:tg[i][0],ty:tg[i][1],s:1.5+Math.random()*2.5,hue:200+Math.random()*40});
}
let mx=-1e4,my=-1e4;
cv.parentElement.addEventListener('pointermove',e=>{const r=cv.getBoundingClientRect();mx=(e.clientX-r.left)*DPR;my=(e.clientY-r.top)*DPR;});
function tick(){
 ctx.clearRect(0,0,W,H);
 for(const p of ps){
  p.x+=(p.tx-p.x)*0.055;p.y+=(p.ty-p.y)*0.055;
  const dx=p.x-mx,dy=p.y-my,md=Math.hypot(dx,dy),R=110*DPR;
  if(md<R&&md>1){p.x+=dx/md*3;p.y+=dy/md*3;}
  ctx.fillStyle='hsla('+p.hue+',85%,68%,0.9)';ctx.fillRect(p.x,p.y,p.s,p.s);
 }
}
window.addEventListener('resize',build);build();
animateOnScreen(cv.parentElement,tick);
})();
/* ---------- planetarium ---------- */
const PLANETS=[
{n:'水星',e:'MERCURY',d:4879,au:0.387,km:'0.58亿',per:88,day:'58.6天',mo:0,c:'#b8a88f',de:'离太阳最近的行星，表面昼夜温差超过 600℃，像月球一样布满环形山。'},
{n:'金星',e:'VENUS',d:12104,au:0.723,km:'1.08亿',per:224.7,day:'243天·逆行',mo:0,c:'#e8c47a',de:'被浓厚二氧化碳大气包裹，表面温度约 465℃，是太阳系最热的行星。'},
{n:'地球',e:'EARTH',d:12742,au:1,km:'1.50亿',per:365.25,day:'23.9小时',mo:1,c:'#5aa9ff',de:'目前已知唯一存在生命的行星，表面 71% 被液态水覆盖。'},
{n:'火星',e:'MARS',d:6779,au:1.524,km:'2.28亿',per:687,day:'24.6小时',mo:2,c:'#ff7a59',de:'奥林帕斯山是太阳系最高的火山，水手谷是最大的峡谷系统。'},
{n:'木星',e:'JUPITER',d:139820,au:5.203,km:'7.79亿',per:4332.6,day:'9.9小时',mo:95,c:'#e0b48f',de:'太阳系最大的行星，大红斑风暴已持续至少 190 年。'},
{n:'土星',e:'SATURN',d:116460,au:9.537,km:'14.34亿',per:10759,day:'10.7小时',mo:146,c:'#f0d9a8',de:'拥有太阳系最壮观的光环，由无数冰粒和岩石碎块组成。'},
{n:'天王星',e:'URANUS',d:50724,au:19.19,km:'28.71亿',per:30687,day:'17.2小时·逆行',mo:28,c:'#9be8e0',de:'自转轴倾角达 98°，像躺着绕太阳转，大气含甲烷而呈青色。'},
{n:'海王星',e:'NEPTUNE',d:49244,au:30.07,km:'44.95亿',per:60190,day:'16.1小时',mo:16,c:'#6f8dff',de:'离太阳最远的行星，1846 年先由数学计算预测位置后被观测证实。'}];
(function(){
const cv=$('planetCv'),ctx=cv.getContext('2d');let W,H,cx,cy;
const lmin=Math.log10(0.387),lmax=Math.log10(30.07);
function orbitR(p){return 46+Math.min(W,H)/2*0.42*(Math.log10(p.au)-lmin)/(lmax-lmin);}
function planetR(p){return 3+9*Math.log10(p.d/1000)/Math.log10(140);}
function resize(){W=cv.width=cv.offsetWidth*DPR;H=cv.height=(cv.getAttribute('height')|0)*DPR;cx=W/2;cy=H/2;}
resize();window.addEventListener('resize',resize);
let pos=[],starLayer=null,starLength=-1,starW=0,starH=0;
function draw(t){
 ctx.clearRect(0,0,W,H);
 if(!W||!H)return;
 if(!starLayer||starLength!==S.length||starW!==W||starH!==H){
  starLayer=document.createElement('canvas');starLayer.width=W;starLayer.height=H;
  const starCtx=starLayer.getContext('2d');
  for(let i=0;i<S.length;i++){const s=S[i];
   const x=(s[0]/360)*W,y=((90-s[1])/180)*H,a=Math.max(0.08,0.9-(s[2]+1.5)/8);
   starCtx.fillStyle='rgba(255,255,255,'+a.toFixed(2)+')';starCtx.fillRect(x,y,1.4,1.4);}
  starLength=S.length;starW=W;starH=H;
 }
 ctx.drawImage(starLayer,0,0);
 /* sun */
 const g=ctx.createRadialGradient(cx,cy,0,cx,cy,34*DPR);
 g.addColorStop(0,'#fff7d6');g.addColorStop(0.35,'#ffd76a');g.addColorStop(1,'rgba(255,150,40,0)');
 ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,34*DPR,0,7);ctx.fill();
 ctx.fillStyle='#ffdf8a';ctx.font=(11*DPR)+'px sans-serif';ctx.textAlign='center';ctx.fillText('太阳',cx,cy+48*DPR);
 pos=[];
 PLANETS.forEach((p,i)=>{
  const r=orbitR(p);
  ctx.strokeStyle='rgba(125,211,252,0.18)';ctx.lineWidth=1;
  ctx.beginPath();ctx.arc(cx,cy,r,0,7);ctx.stroke();
  const ang=t*0.9*(88/p.per)+i*0.7;   /* speed ratio by real period */
  const x=cx+r*Math.cos(ang),y=cy+r*Math.sin(ang),pr=planetR(p)*DPR/1.6;
  const pg=ctx.createRadialGradient(x-pr*0.3,y-pr*0.3,pr*0.1,x,y,pr);
  pg.addColorStop(0,'#ffffff');pg.addColorStop(0.25,p.c);pg.addColorStop(1,'rgba(0,0,0,0.9)');
  ctx.fillStyle=pg;ctx.beginPath();ctx.arc(x,y,Math.max(2.5*DPR/1.6,pr),0,7);ctx.fill();
  ctx.fillStyle='rgba(232,241,255,0.75)';ctx.font=(10*DPR)+'px sans-serif';ctx.fillText(p.n,x,y-pr-6*DPR/1.6);
  pos.push({x,y,r:Math.max(10,pr+6),p});
 });
}
animateOnScreen(cv,draw);
cv.addEventListener('click',e=>{
 const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*DPR,my=(e.clientY-r.top)*DPR;
 for(const o of pos){if(Math.hypot(o.x-mx,o.y-my)<o.r){
  const p=o.p;
  $('planetCard').innerHTML='<h3>'+p.n+'</h3><div class="en">'+p.e+'</div><dl class="kv">'+
  '<dt>直径</dt><dd>'+p.d.toLocaleString()+' km</dd>'+
  '<dt>距日</dt><dd>'+p.au+' AU（约'+p.km+' km）</dd>'+
  '<dt>公转周期</dt><dd>'+p.per.toLocaleString()+' 天</dd>'+
  '<dt>自转周期</dt><dd>'+p.day+'</dd>'+
  '<dt>已知卫星</dt><dd>'+p.mo+' 颗</dd></dl>'+
  '<p style="color:var(--mut);font-size:13px;margin-top:10px">'+p.de+'</p>';
  break;}}
});
})();
</script>
"""

JS_APP_2 = r"""
<script>
"use strict";
const $2=id=>document.getElementById(id);
const DPR2=Math.min(2,window.devicePixelRatio||1);
/* ---------- earth: rotating globe of GeoNames populated places ---------- */
(function(){
const cv=$2('earthCv'),ctx=cv.getContext('2d');let W,H,cx,cy,R;
function resize(){W=cv.width=Math.floor(cv.offsetWidth*DPR2);H=cv.height=(cv.getAttribute('height')|0)*DPR2;cx=W/2;cy=H/2;R=Math.max(10,Math.min(W,H)/2-14*DPR2);}
resize();window.addEventListener('resize',resize);
let ang=0,frame=0,lastFrame=0,sourceCount=-1;
const RAD=Math.PI/180;
function preparePlaces(){
 if(sourceCount===C.length)return;
 const start=Math.max(0,sourceCount);
 for(let i=start;i<C.length;i++){
  const c=C[i],lat=c[0]*RAD;
  c[0]=lat;c[1]*=RAD;c[4]=Math.cos(lat);c[5]=Math.sin(lat);
 }
 sourceCount=C.length;
}
function draw(now){
 if(!W||!H)return;
 ctx.clearRect(0,0,W,H);
 let g=ctx.createRadialGradient(cx,cy,R*0.9,cx,cy,R*1.25);
 g.addColorStop(0,'rgba(90,169,255,0)');g.addColorStop(1,'rgba(90,169,255,0.28)');
 ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*1.25,0,7);ctx.fill();
 g=ctx.createRadialGradient(cx-R*0.4,cy-R*0.4,R*0.1,cx,cy,R);
 g.addColorStop(0,'#0e2038');g.addColorStop(1,'#050b18');
 ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R,0,7);ctx.fill();
 ctx.strokeStyle='rgba(125,211,252,0.35)';ctx.lineWidth=1.5;ctx.stroke();
 if(lastFrame)ang+=Math.min(50,now-lastFrame)*0.00012;
 lastFrame=now;frame++;
 const oldCount=sourceCount;preparePlaces();
 for(let i=0;i<C.length;i++){
  const c=C[i],lo=c[1]+ang,X=c[4]*Math.sin(lo),Y=c[5],Z=c[4]*Math.cos(lo);
  if(Z<=0.02)continue;
  const sx=cx+R*X,sy=cy-R*Y,a=0.2+0.8*Z,pop=c[2];
  const s=(pop>1000000?2.6:pop>100000?1.9:pop>10000?1.4:1)*DPR2/1.4;
  ctx.fillStyle=pop>1000000?('rgba(240,171,252,'+a.toFixed(2)+')'):('rgba(125,211,252,'+a.toFixed(2)+')');
  ctx.fillRect(sx,sy,s,s);
 }
 if(frame%20===0||oldCount!==sourceCount)$2('cityCount').textContent='已载入 '+C.length.toLocaleString()+' 个居民点';
}
animateOnScreen(cv,draw);
})();

</script>
<script>
"use strict";
const $2b=id=>document.getElementById(id);
const DPR3=Math.min(2,window.devicePixelRatio||1);
/* ---------- mandelbrot ---------- */
(function(){
const cv=$2b('mandelCv'),ctx=cv.getContext('2d');
let W=0,H=0,renderVersion=0;
const home={x:-0.5,y:0,r:1.7};let view={...home},touring=false,tourT=null;
function resize(){
 const cssW=Math.max(1,cv.offsetWidth),cssH=Math.max(1,Number(cv.getAttribute('height'))||440);
 const scale=Math.min(DPR3,Math.sqrt(400000/(cssW*cssH)));
 W=cv.width=Math.max(1,Math.floor(cssW*scale));H=cv.height=Math.max(1,Math.floor(cssH*scale));
 render();
}
function render(){
 const version=++renderVersion,w=W,h=H,current={...view};
 if(!w||!h)return;
 $2b('mandelInfo').textContent='渲染中…';
 const img=ctx.createImageData(w,h),d=img.data,maxI=100;
 let py=0;
 function paintBatch(){
  if(version!==renderVersion)return;
  const end=Math.min(py+8,h);
  for(let y=py;y<end;y++){
   const ci=current.y+(y/h-0.5)*2*current.r;
   for(let x=0;x<w;x++){
    const cr=current.x+(x/w-0.5)*2*current.r*(w/h);
    let zr=0,zi=0,it=0;
    while(zr*zr+zi*zi<4&&it<maxI){const t=zr*zr-zi*zi+cr;zi=2*zr*zi+ci;zr=t;it++;}
    const k=(y*w+x)*4;
    if(it>=maxI){d[k]=d[k+1]=d[k+2]=4;}
    else{const t=it/maxI;
     d[k]=Math.floor(9*(1-t)*t*t*t*255);d[k+1]=Math.floor(15*(1-t)*(1-t)*t*t*255);d[k+2]=Math.floor(8.5*(1-t)*(1-t)*(1-t)*t*255);}
    d[k+3]=255;
   }
  }
  ctx.putImageData(img,0,0,0,py,w,end-py);
  py=end;
  if(py<h){requestAnimationFrame(paintBatch);return;}
  $2b('mandelInfo').textContent='中心 '+current.x.toFixed(6)+' , '+current.y.toFixed(6)+'　放大 '+(home.r/current.r).toFixed(1)+'×';
 }
 requestAnimationFrame(paintBatch);
}
cv.addEventListener('click',e=>{
 const r=cv.getBoundingClientRect(),px=(e.clientX-r.left)/r.width,py=(e.clientY-r.top)/r.height;
 view.x+=(px-0.5)*2*view.r*(W/H);view.y+=(py-0.5)*2*view.r;view.r/=2.2;render();});
cv.addEventListener('dblclick',()=>{view={...home};render();});
$2b('mandelReset').onclick=()=>{stopTour();view={...home};render();};
function stopTour(){touring=false;$2b('mandelTour').textContent='自动巡游';if(tourT!==null){clearInterval(tourT);tourT=null;}}
$2b('mandelTour').onclick=()=>{
 if(touring){stopTour();return;}
 touring=true;$2b('mandelTour').textContent='停止巡游';
 view={x:-0.745,y:0.113,r:1.2};render();
 tourT=setInterval(()=>{if(!touring)return;view.r*=0.82;if(view.r<1e-6){stopTour();view={...home};}render();},900);};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopTour();});
window.addEventListener('resize',resize);resize();
})();

</script>
"""

JS_APP_3 = r"""
<script>
"use strict";
const $3=id=>document.getElementById(id);
/* ---------- pi walk ---------- */
(function(){
const cv=$3('piCv'),ctx=cv.getContext('2d');
const cols=['#f87171','#fb923c','#facc15','#4ade80','#2dd4bf','#60a5fa','#a78bfa','#f0abfc','#f472b6','#94a3b8'];
function draw(){
 const W=cv.width=cv.offsetWidth*DPR,H=cv.height=(cv.getAttribute('height')|0)*DPR;
 ctx.clearRect(0,0,W,H);
 const N=Math.min(PI.length,60000);
 let x=W/2,y=H/2;ctx.lineWidth=Math.max(1,DPR/1.5);
 for(let i=0;i<N;i++){
  const dg=PI.charCodeAt(i)-48;if(dg<0||dg>9)continue;
  const a=dg*Math.PI/5,st=2.6*DPR/1.5;
  const nx=x+Math.cos(a)*st,ny=y+Math.sin(a)*st;
  ctx.strokeStyle=cols[dg];ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(nx,ny);ctx.stroke();
  x=nx;y=ny;
  if(x<0||x>W||y<0||y>H){x=W/2;y=H/2;}
 }
 $3('piText').textContent=PI.slice(0,120);
}
window.addEventListener('resize',draw);draw();
})();
/* ---------- hanzi sea ---------- */
(function(){
const PER=600;let page=0,flt='';
function list(){
 if(!flt)return H;
 const q=flt.toUpperCase();
 return H.filter(h=>h[0]===flt||(h[1]&&h[1].toUpperCase().indexOf(q)===0));
}
function render(){
 const L=list(),pages=Math.max(1,Math.ceil(L.length/PER));
 page=Math.min(page,pages-1);
 const g=$3('hzGrid');g.innerHTML='';
 const s=page*PER;
 for(let i=s;i<Math.min(s+PER,L.length);i++){
  const d=document.createElement('div');d.className='hz';d.textContent=L[i][0];
  d.onclick=(()=>{const h=L[i];return()=>{
   $3('hzCard').innerHTML='<div class="hzbig">'+h[0]+'</div><h3 style="text-align:center">'+h[0]+'</h3>'+
   '<div class="en" style="text-align:center">U+'+h[0].codePointAt(0).toString(16).toUpperCase().padStart(4,'0')+'</div>'+
   '<dl class="kv"><dt>拼音</dt><dd>'+h[1]+'</dd><dt>部首序号</dt><dd>'+h[2]+'</dd><dt>笔画数</dt><dd>'+h[3]+'</dd></dl>';};})();
  g.appendChild(d);
 }
 $3('hzPage').textContent='第 '+(page+1)+' / '+pages+' 页（共 '+L.length.toLocaleString()+' 字）';
 $3('hzCount').textContent='Unihan 收录 '+H.length.toLocaleString()+' 个有普通话读音的汉字';
}
$3('hzSearch').addEventListener('input',e=>{flt=e.target.value.trim();page=0;render();});
$3('hzPrev').onclick=()=>{if(page>0){page--;render();}};
$3('hzNext').onclick=()=>{page++;render();};
render();
})();
/* ---------- music: code-composed 《星海》 ---------- */
const SONG_META={title:'星海',scale:'D宫五声音阶',bpm:92};
const SONG=[
['D5',1],['E5',1],['F#5',1.5],['A5',0.5],['B5',2],['A5',1],['F#5',1],
['E5',1.5],['D5',0.5],['E5',2],['F#5',1],['D5',1],
['D5',1],['E5',1],['F#5',1.5],['A5',0.5],['B5',1],['A6',1],['B6',2],['A6',1],
['F#6',1.5],['E6',0.5],['D6',2],['B5',1],['A5',1],
['F#5',1.5],['E5',0.5],['D5',1],['E5',1],['D5',3],
];
const FREQ={C:261.63,'C#':277.18,D:293.66,'D#':311.13,E:329.63,F:349.23,'F#':369.99,G:392.0,'G#':415.3,A:440.0,'A#':466.16,B:493.88};
function noteHz(n){const m=n.match(/^([A-G]#?)(\d)$/);return FREQ[m[1]]*Math.pow(2,parseInt(m[2])-4);}
(function(){
let actx=null,playing=false,timers=[];
function ensure(){if(!actx){actx=new (window.AudioContext||window.webkitAudioContext)();}return actx;}
function tone(f,t,dur){
 const o=actx.createOscillator(),o2=actx.createOscillator(),g=actx.createGain(),an=actx._an;
 o.type='triangle';o.frequency.value=f;o2.type='sine';o2.frequency.value=f*2;
 const g2=actx.createGain();g2.gain.value=0.25;
 o.connect(g);o2.connect(g2);g2.connect(g);g.connect(an||actx.destination);
 const v=0.5;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(v,t+0.03);
 g.gain.exponentialRampToValueAtTime(0.001,t+dur);
 o.start(t);o2.start(t);o.stop(t+dur+0.1);o2.stop(t+dur+0.1);
}
function drawVis(an){
 const cv=$3('musicCv'),ctx=cv.getContext('2d');
 let W=0,H=0,raf=0;const data=new Uint8Array(an.frequencyBinCount);
 function resize(){W=cv.width=Math.floor(cv.offsetWidth*DPR);H=cv.height=(cv.getAttribute('height')|0)*DPR;}
 function tick(){
  raf=0;
  if(!playing||document.hidden)return;
  an.getByteFrequencyData(data);
  ctx.clearRect(0,0,W,H);
  const n=64,bw=W/n;
  for(let i=0;i<n;i++){const v=data[Math.floor(i/n*data.length*0.7)]/255;
   const h=Math.max(2,v*H*0.92);
   const gr=ctx.createLinearGradient(0,H,0,H-h);gr.addColorStop(0,'#38bdf8');gr.addColorStop(1,'#f0abfc');
   ctx.fillStyle=gr;ctx.fillRect(i*bw+1,H-h,bw-2,h);}
  raf=requestAnimationFrame(tick);
 }
 resize();window.addEventListener('resize',resize);
 return function(active){
  if(active&&!document.hidden&&!raf)raf=requestAnimationFrame(tick);
  else if(!active&&raf){cancelAnimationFrame(raf);raf=0;}
 };
}
let visControl=null;
document.addEventListener('visibilitychange',()=>{if(visControl)visControl(playing);});
$3('playBtn').onclick=()=>{
 const ac=ensure();ac.resume();
 if(playing){timers.forEach(clearTimeout);timers=[];playing=false;if(visControl)visControl(false);$3('playBtn').textContent='▶ 播放《星海》';$3('nowPlaying').textContent='已停止';return;}
 if(!actx._an){actx._an=ac.createAnalyser();actx._an.fftSize=256;actx._an.connect(ac.destination);}
 if(!visControl)visControl=drawVis(actx._an);
 playing=true;visControl(true);$3('playBtn').textContent='⏸ 停止';
 const beat=60/SONG_META.bpm;let t=ac.currentTime+0.1;
 SONG.forEach((nd,i)=>{
  const f=noteHz(nd[0]),dur=nd[1]*beat;
  tone(f,t,dur*1.8);
  timers.push(setTimeout(()=>{$3('nowPlaying').textContent='♪ '+nd[0]+'  ('+(i+1)+'/'+SONG.length+')';},(t-ac.currentTime)*1000));
  t+=dur;});
 const total=t-ac.currentTime;
 timers.push(setTimeout(()=>{playing=false;if(visControl)visControl(false);$3('playBtn').textContent='▶ 播放《星海》';$3('nowPlaying').textContent='演奏完毕 · 全曲 '+total.toFixed(1)+' 秒';timers=[];},(t-ac.currentTime)*1000+300));
};
})();
/* ---------- world clocks ---------- */
const ZONES=[['北京','Asia/Shanghai'],['东京','Asia/Tokyo'],['首尔','Asia/Seoul'],['新加坡','Asia/Singapore'],['曼谷','Asia/Bangkok'],['新德里','Asia/Kolkata'],['迪拜','Asia/Dubai'],['莫斯科','Europe/Moscow'],['开罗','Africa/Cairo'],['巴黎','Europe/Paris'],['伦敦','Europe/London'],['纽约','America/New_York'],['芝加哥','America/Chicago'],['丹佛','America/Denver'],['洛杉矶','America/Los_Angeles'],['圣保罗','America/Sao_Paulo'],['悉尼','Australia/Sydney'],['奥克兰','Pacific/Auckland'],['檀香山','Pacific/Honolulu'],['安克雷奇','America/Anchorage']];
(function(){
const grid=$3('clockGrid');const cells=ZONES.map(z=>{
 const d=document.createElement('div');d.className='clock';
 d.innerHTML='<div class="t">--:--:--</div><div class="c">'+z[0]+'</div><div class="z">'+z[1]+'</div>';
 grid.appendChild(d);return d;});
const formatters=ZONES.map(z=>{
 try{return new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZone:z[1]});}
 catch(e){return null;}
});
function tick(){
 const now=new Date();
 cells.forEach((cell,i)=>{const formatter=formatters[i];cell.querySelector('.t').textContent=formatter?formatter.format(now):'N/A';});
}
tick();let timer=setInterval(tick,1000);
document.addEventListener('visibilitychange',()=>{
 if(document.hidden){clearInterval(timer);timer=null;}
 else if(timer===null){tick();timer=setInterval(tick,1000);}
});
})();
/* ---------- header chips + footer stats (filled by generator) ---------- */
(function(){
const chips=[['总字节','<b>'+STATS.bytes+'</b>'],['居民点','<b>'+STATS.cities+'</b>'],['汉字','<b>'+STATS.hanzi+'</b>'],['恒星','<b>'+STATS.stars+'</b>'],['π 位数','<b>'+STATS.pi+'</b>']];
$3('chips').innerHTML=chips.map(c=>'<span class="chip">'+c[0]+' '+c[1]+'</span>').join('');
$3('footStats').innerHTML='<span class="stat">总字节 <b>'+STATS.bytes+'</b></span><span class="stat">分片 <b>'+STATS.chunks+'</b></span><span class="stat">居民点 <b>'+STATS.cities+'</b></span><span class="stat">汉字 <b>'+STATS.hanzi+'</b></span><span class="stat">恒星 <b>'+STATS.stars+'</b></span>';
$3('footBytes').textContent=STATS.bytes;$3('footChunks').textContent=STATS.chunks;
})();
window.dispatchEvent(new Event("biggest:data-ready"));
</script>
</body>
</html>
"""

# ---------------------------------------------------------------- main

def fmt_int(n):
    return "{:,}".format(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk-mib", type=int, default=20)
    ap.add_argument("--max-cities", type=int, default=0)
    ap.add_argument("--pi-digits", type=int, default=100000)
    ap.add_argument("--worker-src", required=True,
                    help="worker/src dir; chunks.js manifest is written here")
    args = ap.parse_args()
    if args.chunk_mib < 1:
        ap.error("--chunk-mib must be at least 1")
    if args.max_cities < 0:
        ap.error("--max-cities must be 0 (unlimited) or a positive integer")
    if args.pi_digits < 0:
        ap.error("--pi-digits must be non-negative")

    d = args.data
    print("[1/6] loading cities...", flush=True)
    cities = load_cities(os.path.join(d, "allCountries.txt"), args.max_cities)
    print("      cities:", fmt_int(len(cities)), flush=True)
    print("[2/6] loading stars...", flush=True)
    stars = load_stars(os.path.join(d, "hygdata_v3.csv"))
    print("      stars:", fmt_int(len(stars)), flush=True)
    print("[3/6] loading hanzi...", flush=True)
    hanzi = load_hanzi(os.path.join(d, "Unihan_Readings.txt"),
                       os.path.join(d, "Unihan_IRGSources.txt"))
    print("      hanzi:", fmt_int(len(hanzi)), flush=True)
    print("[4/6] computing pi digits...", flush=True)
    pi = load_pi_digits(args.pi_digits)
    print("      pi digits:", fmt_int(len(pi)), flush=True)

    w = ChunkWriter(args.out, args.chunk_mib * 1024 * 1024)
    print("[5/6] emitting html...", flush=True)
    head = HTML_HEAD.replace("{PIDIGITS}", fmt_int(len(pi)))
    head = head.replace("{NHANZI}", fmt_int(len(hanzi)))
    head = head.replace("{NCLOCKS}", str(len(ZONES_PY)))
    w.write(head)
    w.write('<script>"use strict";const STATS=/*__STATS__*/null;</script>\n')
    w.write(JS_APP_1)
    w.write(JS_APP_2)
    # stars
    w.write('<script>"use strict";\n')
    for ra, dec, mag, name in stars:
        w.write("S.push([%.4f,%.4f,%.2f,%s]);\n" % (ra, dec, mag, js_str(name)))
    w.write("</script>\n")
    # cities (the bulk)
    w.write('<script>"use strict";\n')
    for i, (lat, lon, pop, name) in enumerate(cities):
        w.write("C.push([%.4f,%.4f,%d,%s]);\n" % (lat, lon, pop, js_str(name)))
        if (i + 1) % 500000 == 0:
            print("      ...%s cities emitted" % fmt_int(i + 1), flush=True)
    w.write("</script>\n")
    # hanzi
    w.write('<script>"use strict";\n')
    for ch, pinyin, rad, st in hanzi:
        w.write("H.push([%s,%s,%d,%d]);\n" % (js_str(ch), js_str(pinyin), rad, st))
    w.write("</script>\n")
    # pi
    w.write('<script>"use strict";\n')
    for i in range(0, len(pi), 4000):
        w.write('PI+="%s";\n' % pi[i:i + 4000])
    w.write("</script>\n")
    w.write(JS_APP_3)
    total, files = w.close()

    # Patch the stats placeholder and converge on the actual final output size.
    p0 = os.path.join(args.out, files[0])
    with open(p0, encoding="utf-8") as f:
        template = f.read()
    placeholder = "/*__STATS__*/null"
    if placeholder not in template:
        raise RuntimeError("stats placeholder missing from first chunk")
    stats = {"bytes": "", "chunks": fmt_int(len(files)),
             "cities": fmt_int(len(cities)), "hanzi": fmt_int(len(hanzi)),
             "stars": fmt_int(len(stars)), "pi": fmt_int(len(pi))}
    for _ in range(10):
        stats["bytes"] = fmt_int(total) + " 字节"
        c0 = template.replace(placeholder, json.dumps(stats, ensure_ascii=False))
        with open(p0, "w", encoding="utf-8") as f:
            f.write(c0)
        actual_total = sum(os.path.getsize(os.path.join(args.out, x)) for x in files)
        if stats["bytes"] == fmt_int(actual_total) + " 字节":
            total = actual_total
            break
        total = actual_total
    else:
        raise RuntimeError("could not converge on the final byte count")

    print("[6/6] writing worker manifest...", flush=True)
    os.makedirs(args.worker_src, exist_ok=True)
    with open(os.path.join(args.worker_src, "chunks.js"), "w",
              encoding="utf-8") as f:
        f.write("// auto-generated by gen/build.py — do not edit\n")
        f.write("export const CHUNKS = %s;\n" % json.dumps(files))

    print("DONE: %d chunks, %s bytes (%.1f MiB)" %
          (len(files), fmt_int(total), total / 1048576))
    for x in files:
        print("  %s  %s" % (x, fmt_int(os.path.getsize(os.path.join(args.out, x)))))


ZONES_PY = ['北京', '东京', '首尔', '新加坡', '曼谷', '新德里', '迪拜', '莫斯科',
            '开罗', '巴黎', '伦敦', '纽约', '芝加哥', '丹佛', '洛杉矶', '圣保罗',
            '悉尼', '奥克兰', '檀香山', '安克雷奇']


if __name__ == "__main__":
    main()
