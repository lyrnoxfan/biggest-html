"""Opt-in >226 MB single-file experiment. Run after building expedition edition.
Linux process-tree RSS sum includes shared pages counted repeatedly; NOT device RAM requirements.
"""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'artifacts/folded-atlas-expedition.html'

def tree_rss():
    rows = subprocess.check_output(['ps', '-e', '-o', 'pid=,ppid=,rss='], text=True)
    processes = [tuple(map(int, row.split())) for row in rows.splitlines()]
    descendants = {os.getpid()}
    for _ in range(10):
        new = {pid for pid, parent, _ in processes if parent in descendants}
        if new <= descendants:
            break
        descendants |= new
    return sum(rss for pid, _, rss in processes if pid in descendants) * 1024

def run():
    results = []
    assert HTML.stat().st_size >= 226_000_000
    with sync_playwright() as p:
        for engine, width, throttle in [('chromium', 1440, 1), ('chromium', 360, 4), ('firefox', 1440, 1), ('firefox', 360, 1)]:
            stop = threading.Event()
            samples = []
            def sample():
                while not stop.wait(.2):
                    samples.append(tree_rss())
            thread = threading.Thread(target=sample, daemon=True)
            thread.start()
            browser = getattr(p, engine).launch()
            context = browser.new_context(offline=True, viewport={'width': width, 'height': 1000}, reduced_motion='reduce', device_scale_factor=3)
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('https:', 'http:')) else None)
            if engine == 'chromium':
                context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate', {'rate': throttle})
            begin = time.monotonic()
            page.goto(HTML.as_uri(), wait_until='load', timeout=120000)
            page.wait_for_function("document.querySelector('#total').textContent!=='—'")
            ready = time.monotonic() - begin
            metrics = page.evaluate("""() => ({count:COUNT,dom:document.querySelectorAll('*').length,blocks:document.querySelectorAll('script[type="application/json"]').length,cache:cache.size,cards:document.querySelectorAll('.island').length,canvas:[terrain.width,terrain.height],navigation:performance.getEntriesByType('navigation').map(n=>({domContentLoaded:n.domContentLoadedEventEnd,load:n.loadEventEnd})),overflow:document.documentElement.scrollWidth>innerWidth})""")
            assert metrics['count'] == 2097152 and metrics['cards'] == 24 and not metrics['overflow']
            begin = time.monotonic()
            page.locator('#jump').fill('2097152')
            page.locator('#jump-form button').click()
            assert page.url.endswith('#island-2097152')
            assert page.locator('#next').is_disabled()
            jump = time.monotonic() - begin
            page.locator('#save').click()
            page.locator('#notebook').click()
            assert page.locator('.island').count() == 1
            page.locator('#save').click()
            page.locator('#notebook').click()
            page.locator('#filter').select_option('7')
            assert page.locator('.island').count() == 24
            page.locator('#random').click()
            page.locator('#quality').select_option('low')
            assert page.locator('#terrain').evaluate('(el)=>el.width') <= 360
            page.evaluate("() => {filter=-1;bookMode=false;for(let n=0;n<150;n++){page=n*500;render();}select(COUNT-1,true);}")
            after = page.evaluate("() => ({cache:cache.size,cards:document.querySelectorAll('.island').length,dom:document.querySelectorAll('*').length})")
            assert after['cache'] <= 4 and after['cards'] == 24 and after['dom'] <= metrics['dom'] + 5
            assert not errors and not requests
            page.screenshot(path=str(ROOT / f'artifacts/expedition-{engine}-{width}.png'))
            stop.set()
            thread.join()
            results.append({'browser':engine,'version':browser.version,'width':width,'cpuThrottle':throttle,'fileBytes':HTML.stat().st_size,'loadToReadySeconds':round(ready,3),'lastRecordUIJumpSeconds':round(jump,3),'initial':metrics,'after150pages':after,'peakProcessTreeRSSBytes':max(samples,default=0),'rssCaveat':'Linux test driver + browser process-tree RSS sum sampled at 200ms; shared pages counted repeatedly, not exclusive memory or minimum device RAM. Source text still resident.','errors':errors,'externalRequests':requests})
            browser.close()
    target = ROOT / 'artifacts/folded-atlas-expedition-results.json'
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(target.read_text())
if __name__ == '__main__':
    run()
