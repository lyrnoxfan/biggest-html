"""Build the original Echo Workshop. Only authored scores + playable audio, no bulk datasets.
Run with numpy==2.4.2. Generated PCM is deterministic original synthesis, not recordings.
"""
import argparse, base64, hashlib, io, json, math, struct, wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
PATCHES=[
 dict(id='felt',name='毡音钢琴',duration=2.8,color='#426554',description='木头般温暖的起音，尾音缓缓散开。轻触与重弹有不同的泛音。'),
 dict(id='wood',name='木片琴',duration=1.45,color='#a36547',description='短促、清楚，像桌面上落下的小木珠。适合把节奏敲出来。'),
 dict(id='glass',name='玻璃钟',duration=2.6,color='#4e6c8b',description='不完全谐和的金属泛音，余音有微小的摆动。留白时更好听。'),
 dict(id='pluck',name='拨弦',duration=1.8,color='#75638a',description='从亮到暗的拨弦声，低音与高音的衰减各不相同。'),
 dict(id='bass',name='圆低音',duration=1.15,color='#536353',description='柔软的低频与轻微的指尖起音。通常放在第一拍，不必铺满。'),
 dict(id='air',name='风琴',duration=2.0,color='#8d6a73',description='慢慢浮现的簧片声。把相邻的音错开，会像两个人在接话。'),
]
DRUMS=[dict(id='kick',name='底鼓',duration=.42,color='#6b6252'),dict(id='snare',name='沙鼓',duration=.32,color='#6b6252'),dict(id='hat',name='细镲',duration=.18,color='#6b6252')]

def pcm(patch,note,vel,rate,stereo):
    duration=patch['duration']; n=round(duration*rate); t=np.arange(n,dtype=np.float64)/rate
    f=440*2**((note-69)/12); strength=vel; seed=(note+1)*7937+sum(map(ord,patch['id']))*31+round(vel*100)
    rng=np.random.default_rng(seed); name=patch['id']
    def wavepart(freq,decay,phase=0):return np.sin(2*np.pi*freq*t+phase)*np.exp(-t/decay) if freq < rate*.47 else np.zeros(n)
    if name=='felt':
        y=sum((strength**(0.4+h*.12)/(h**1.5))*wavepart(f*h*(1+.00013*h*h),(.55+70/f)/(1+h*.18),.04*h) for h in range(1,13))
        y+=rng.normal(0,1,n)*np.exp(-t/.016)*.045*strength
        env=1-np.exp(-t/.004)
    elif name=='wood':
        y=wavepart(f,.28+15/f)+.52*strength*wavepart(f*3.98,.16)+.24*strength**2*wavepart(f*9.97,.065)
        env=1-np.exp(-t/.001)
    elif name=='glass':
        y=wavepart(f,.9)+.4*strength*wavepart(f*2.756,.65)+.24*wavepart(f*5.404,.45)+.11*strength**2*wavepart(f*8.933,.32)
        y*=1+.13*np.sin(2*np.pi*3.3*t);env=1-np.exp(-t/.002)
    elif name=='pluck':
        y=sum((strength**(h*.2)/h**1.1)*wavepart(f*h*(1+.000035*h*h),(.48+12/f)/(1+h*.28),h*.12) for h in range(1,15));env=1-np.exp(-t/.002)
    elif name=='bass':
        y=wavepart(f,.44)+.24*strength*wavepart(f*2,.24)+.1*strength**2*wavepart(f*3,.12)
        env=1-np.exp(-t/.007)
    elif name=='air':
        y=sum(np.sin(2*np.pi*(f*h+(.15 if h%2 else -.2))*t)/h**2*strength**(h*.1) for h in range(1,9))
        env=(1-np.exp(-t/.08))*np.exp(-t/.6)*(1+.035*np.sin(2*np.pi*5.1*t))
    elif name=='kick':
        phase=2*np.pi*(42*t+80*.035*(1-np.exp(-t/.035)))
        y=np.sin(phase)*np.exp(-t/.09)+.12*rng.normal(0,1,n)*np.exp(-t/.004); env=1-np.exp(-t/.0008)
    elif name=='snare':
        noise=rng.normal(0,1,n); bright=noise-np.roll(noise,1)*.7
        y=bright*np.exp(-t/.048)*.4+wavepart(180,.04)*.4;env=1-np.exp(-t/.0005)
    else:
        noise=rng.normal(0,1,n);y=(noise-np.roll(noise,1))*.3*np.exp(-t/.024);env=1-np.exp(-t/.0003)
    y=y*env*strength
    # Finite natural tails, 20ms anti-click release. No appended silence or repeated PCM.
    y*=np.minimum(1,(duration-t)/.02)
    y=np.tanh(y*.65)*.64
    if stereo:
        delay=round(rate*(.00017+.00004*(note%5)))
        r=.97*np.concatenate((np.zeros(delay),y[:-delay]))
        # Gentle independent room reflection; meaningful stereo, not a duplicate channel.
        d=round(rate*.023);r[d:]+=y[:-d]*.055
        data=np.stack([y,r],axis=1)
    else:data=y
    data=(np.clip(data,-1,1)*32760).astype('<i2')
    out=io.BytesIO()
    with wave.open(out,'wb') as w:w.setnchannels(2 if stereo else 1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(data.tobytes())
    return out.getvalue()

def build(out,low,high,layers,rate,stereo):
    specs=[]; hashes=set();count=0;audio=0
    config=dict(low=low,high=high,layers=layers,rate=rate,stereo=stereo,patches=PATCHES,drums=DRUMS)
    template=(ROOT/'echo.html').read_text()
    before,after=template.split('<!--SAMPLE_BANK-->')
    before=before.replace('__CONFIG__',json.dumps(config,ensure_ascii=False,separators=(',',':')))
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w') as dest:
        dest.write(before)
        for p in PATCHES+DRUMS:
            notes=range(low,high+1) if p in PATCHES else [36]
            for note in notes:
                for layer in range(layers):
                    vel=[.72] if layers==1 else np.linspace(.38,1,layers).tolist()
                    raw=pcm(p,note,vel[layer],rate,stereo)
                    h=hashlib.sha256(raw).hexdigest();assert h not in hashes,'duplicate sample';hashes.add(h)
                    dest.write(f'<script type="application/octet-stream" id="s-{p["id"]}-{note}-{layer}">')
                    dest.write(base64.b64encode(raw).decode());dest.write('</script>\n')
                    specs.append(dict(id=f'{p["id"]}-{note}-{layer}',sha256=h,bytes=len(raw)));audio+=len(raw);count+=1
        dest.write(after)
    report=dict(file=out.name,bytes=out.stat().st_size,sampleCount=count,uniqueSamples=len(hashes),pcmWavBytes=audio,configuration=config,files=specs)
    out.with_suffix('.manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='artifacts/echo-studio.html');ap.add_argument('--low',type=int,default=36);ap.add_argument('--high',type=int,default=83);ap.add_argument('--layers',type=int,choices=[1,2,3],default=2);ap.add_argument('--rate',type=int,choices=[24000,48000],default=48000);ap.add_argument('--mono',action='store_true');a=ap.parse_args()
    if not 24<=a.low<=a.high<=95:ap.error('Use a playable pitch range within C1–B6.')
    build(a.out,a.low,a.high,a.layers,a.rate,not a.mono)
