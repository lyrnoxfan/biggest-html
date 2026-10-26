"""Browser acceptance for the actual standalone audio work. Requires playwright==1.58.0.
ECHO_HTML=artifacts/echo-workshop.html .venv/bin/python tests/browser_echo.py
ECHO_QUICK=1 checks a single Chromium viewport; full run covers both engines and phone widths.
All content is exercised by real visible controls; diagnostics only observe bounded audio state.
"""
import json, os, time, wave, struct
from array import array
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/os.environ.get('ECHO_HTML','artifacts/echo-sketch.html')).resolve()
OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True)
quick=os.environ.get('ECHO_QUICK')=='1'
results=[]
with sync_playwright() as pw:
 for engine in (['chromium'] if quick else ['chromium','firefox']):
  for width in ([360] if quick else [360,1440]):
   browser=getattr(pw,engine).launch()
   c=browser.new_context(viewport={'width':width,'height':900 if width>640 else 800},offline=True,reduced_motion='reduce',accept_downloads=True,has_touch=engine=='chromium' and width==360)
   p=c.new_page();p.set_default_timeout(20000);errors=[];requests=[]
   p.on('pageerror',lambda e:errors.append(str(e)))
   p.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
   if engine=='chromium':
    session=c.new_cdp_session(p);session.send('Emulation.setCPUThrottlingRate',{'rate':4 if width==360 else 1})
    session.send('Performance.enable')
   t=time.monotonic();p.goto(HTML.as_uri(),wait_until='load',timeout=180000);load=time.monotonic()-t
   assert p.locator('html').get_attribute('data-ready')=='true'
   assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
   title=p.locator('h1').bounding_box(); assert title['x']>=0 and title['x']+title['width']<=width
   initial=p.evaluate('echoDiagnostics()');assert initial['audioState']=='not-started' and initial['cache']==0
   p.screenshot(path=str(OUT/f'{HTML.stem}-{engine}-{width}.png'))
   p.locator('#play').click();p.wait_for_function('echoDiagnostics().playing');p.wait_for_function('echoDiagnostics().signalPeak>0.0001');signal_peak=p.evaluate('echoDiagnostics().signalPeak');p.wait_for_timeout(1800)
   assert p.evaluate('echoDiagnostics().audioState')=='running'
   assert p.evaluate('echoDiagnostics().active')>0
   p.locator('#play').click();assert not p.evaluate('echoDiagnostics().playing')
   p.locator('#stop').click()
   # In each score all six timbres are reachable; select then play, stop, and inspect bar 8.
   for i in range(6):
    p.locator('.piece').nth(i).click()
    assert p.locator('#studio-title').inner_text()==['雨走过去','纸上散步','留一盏灯','玻璃电梯','缓慢折返','夜航'][i]
    p.locator('#play').click();p.wait_for_function('echoDiagnostics().playing');p.wait_for_function('echoDiagnostics().signalPeak>0.0001');p.wait_for_timeout(350)
    p.locator('#stop').click();p.get_by_role('button',name='查看第8小节',exact=True).click()
    assert p.locator('.step').count()==128
   # Edits, Shift-velocity, mute, undo, tempo, bar loop, clearing and restoration.
   cell=p.locator('.step').nth(0);old=cell.get_attribute('aria-pressed');cell.click();assert p.locator('.step').nth(0).get_attribute('aria-pressed')!=old
   p.locator('#undo').click();assert p.locator('.step').nth(0).get_attribute('aria-pressed')==old
   before=p.locator('.step').nth(0).get_attribute('aria-label');p.locator('.step').nth(0).click(modifiers=['Shift']);assert p.locator('.step').nth(0).get_attribute('aria-label')!=before
   p.get_by_label('音轨1静音',exact=True).click();assert p.get_by_label('音轨1静音',exact=True).get_attribute('aria-pressed')=='true'
   p.locator('#tempo').fill('120');p.locator('#tempo').press('Tab')
   p.locator('#loop').select_option('bar');p.locator('#play').click();p.wait_for_function('echoDiagnostics().playing');p.wait_for_timeout(2200);assert p.evaluate('echoDiagnostics().bar')==7
   p.locator('#stop').click();p.locator('#clear-bar').click();assert p.locator('.step.on').count()==0
   p.locator('#restore').click();assert p.locator('#tempo').input_value()=='76'
   # A full pass through the fastest original arrangement, not only a playback kickoff.
   p.locator('#restore').click();p.locator('.piece').nth(3).click();p.locator('#tempo').fill('160');p.locator('#tempo').press('Tab');p.locator('#loop').select_option('song');p.locator('#play').click();p.wait_for_function('echoDiagnostics().playing');p.wait_for_timeout(13200);p.locator('#stop').click()
   assert p.evaluate('echoDiagnostics().lateNotes')==0
   p.locator('#restore').click()
   # Screen-key pointer/touch audition and six independently decoded sounds.
   for patch in ['felt','wood','glass','pluck','bass','air']:
    p.locator('#live-patch').select_option(patch)
    key=p.locator('.white').nth(2)
    if engine=='chromium' and width==360:key.tap()
    else:key.click()
   # True physical keyboard path, from unfocused document, with actual nonzero output.
   p.locator('#stop').click();p.locator('h1').click();p.keyboard.press('a');p.wait_for_function('echoDiagnostics().active>0 && echoDiagnostics().signalPeak>0.0001');p.keyboard.press('Escape');assert p.evaluate('echoDiagnostics().active')==0
   # Local save/export/import include actual download bytes, not a receipt-only claim.
   p.get_by_text('保存与继续创作',exact=True).click();p.locator('#saveName').fill('浏览器验收曲');p.locator('#save').click()
   with p.expect_download() as dl:p.locator('#export-project').click()
   file=OUT/f'{HTML.stem}-{engine}-{width}-project.json';dl.value.save_as(file)
   data=json.loads(file.read_text());assert data['title']=='浏览器验收曲' and len(data['tracks'])==8
   p.locator('#project-file').set_input_files(file);p.wait_for_function("document.querySelector('#studio-title').textContent==='浏览器验收曲'")
   # Rejected malformed import must leave current work intact.
   bad=OUT/'echo-invalid.json';bad.write_text('{"format":"echo-workshop","version":1,"tracks":[]}')
   p.locator('#project-file').set_input_files(bad);p.wait_for_function("document.querySelector('#status').textContent.includes('不是有效')");assert p.locator('#studio-title').inner_text()=='浏览器验收曲'
   p.locator('#load').click();assert p.locator('#studio-title').inner_text()=='浏览器验收曲'
   # Desktop exports full mix; mobile export tested separately only once to keep matrix bounded.
   mix=None
   if width==1440 or quick:
    with p.expect_download(timeout=180000) as dl:p.locator('#export-wav').click()
    file=OUT/f'{HTML.stem}-{engine}-{width}-mix.wav';dl.value.save_as(file)
    with wave.open(str(file),'rb') as wav:
     expected_seconds=128*60/data['bpm']/4+3
     assert wav.getnchannels()==2 and wav.getframerate()==44100 and abs(wav.getnframes()/44100-expected_seconds)<.001
     raw=wav.readframes(wav.getnframes());vals=array('h');vals.frombytes(raw);peak=max(abs(v) for v in vals);assert 500<peak<32700
     mix={'frames':wav.getnframes(),'rate':44100,'peak':peak,'bytes':file.stat().st_size}
   # Visible focus and 200% root font with no horizontal page overflow.
   p.evaluate("document.documentElement.style.fontSize='30px'")
   assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
   p.evaluate("document.documentElement.style.fontSize='15px'")
   p.locator('#studio').scroll_into_view_if_needed();p.screenshot(path=str(OUT/f'{HTML.stem}-{engine}-{width}-studio.png'))
   audit=None
   axe=OUT/'axe.min.js'
   if axe.exists():
    p.add_script_tag(path=str(axe));audit=p.evaluate("async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))")
   assert audit==[],audit
   final=p.evaluate('echoDiagnostics()');assert final['cache']<=24 and final['maxActive']<=32 and final['inflight']==0 and final['decodeFailures']==0,final
   heap=None
   if engine=='chromium':heap=session.send('Performance.getMetrics')
   assert not errors,errors;assert not requests,requests
   results.append({'engine':engine,'viewport':width,'cpuThrottle':4 if engine=='chromium' and width==360 else 1,'loadSeconds':round(load,3),'titleBounds':title,'liveSignalPeak':signal_peak,'keyboardNonzeroOutput':True,'touchAudition':engine=='chromium' and width==360,'initial':initial,'final':final,'mix':mix,'errors':errors,'externalRequests':requests,'axeViolations':audit,'performanceMetrics':heap})
   c.close();browser.close()
 (OUT/(HTML.stem+'-browser.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print(json.dumps(results,ensure_ascii=False,indent=2))
