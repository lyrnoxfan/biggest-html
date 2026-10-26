"""Explore actual file parsing/interaction cost at two delivery scales and an optional echo-workshop.html stress scale.
RSS is sum across Playwright's browser descendants, shared pages may be double-counted.
Requires playwright==1.58.0 and psutil==7.2.2. Sequential runs avoid competing browsers.
"""
import os,json,time,threading
from pathlib import Path
import psutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'artifacts';rows=[]
with sync_playwright() as pw:
 for name in ['echo-sketch','echo-studio']+(['echo-workshop'] if (out/'echo-workshop.html').exists() else []):
  for engine in ['chromium','firefox']:
   browser=getattr(pw,engine).launch();ctx=browser.new_context(viewport={'width':360,'height':800},offline=True,reduced_motion='reduce');page=ctx.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
   if engine=='chromium':ctx.new_cdp_session(page).send('Emulation.setCPUThrottlingRate',{'rate':4})
   driver=psutil.Process(pw._impl_obj._connection._transport._proc.pid)
   mem=[];running=True
   def sample():
    while running:
     total=0
     for p in driver.children(recursive=True):
      try:total+=p.memory_info().rss
      except (psutil.NoSuchProcess,psutil.AccessDenied):pass
     mem.append(total);time.sleep(.05)
   thread=threading.Thread(target=sample);thread.start();file=out/(name+'.html');t=time.monotonic();row={'file':file.name,'bytes':file.stat().st_size,'engine':engine,'width':360,'cpuThrottle':4 if engine=='chromium' else 1}
   try:
    page.goto(file.as_uri(),wait_until='load',timeout=180000);row['loadSeconds']=round(time.monotonic()-t,3);row['initial']=page.evaluate('echoDiagnostics()')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    t=time.monotonic();page.locator('#play').click();page.wait_for_function('echoDiagnostics().playing',timeout=30000);page.wait_for_function('echoDiagnostics().signalPeak>0.0001',timeout=20000);row['playReadySeconds']=round(time.monotonic()-t,3);page.wait_for_timeout(5000);page.locator('#stop').click()
    page.locator('#octave').select_option(page.locator('#octave option').last.get_attribute('value'))
    page.locator('.white').last.click(position={'x':10,'y':100});page.wait_for_timeout(500)
    page.get_by_role('button',name='查看第8小节',exact=True).click();t=time.monotonic();page.locator('.step').last.click();row['editSeconds']=round(time.monotonic()-t,3)
    row['final']=page.evaluate('echoDiagnostics()');assert not errs,errs;assert row['final']['decodeFailures']==0 and row['final']['cache']<=24 and row['final']['maxActive']<=32,row['final'];row['errors']=errs;row['completed']=True
   except Exception as e:row['completed']=False;row['error']=repr(e)
   finally:
    running=False;thread.join();row['peakProcessTreeRSSBytes']=max(mem,default=0);row['tailProcessTreeRSSBytes']=mem[-1] if mem else None;rows.append(row);(out/'echo-scale-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(row,ensure_ascii=False),flush=True);ctx.close();browser.close()

assert rows and all(row.get("completed") for row in rows), "Scale experiment failed; inspect artifacts/echo-scale-results.json"
