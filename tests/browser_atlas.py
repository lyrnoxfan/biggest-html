"""Offline browser regression, no server necessary. pip install playwright==1.58.0."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / os.environ.get('ATLAS_HTML', 'artifacts/folded-atlas.html')
OUT = ROOT / 'artifacts'

def run():
    results = []
    with sync_playwright() as p:
        for engine in ('chromium', 'firefox'):
            browser = getattr(p, engine).launch()
            for width in (360, 1440):
                context = browser.new_context(viewport={'width': width, 'height': 1000}, offline=True, reduced_motion='reduce', device_scale_factor=3)
                page = context.new_page()
                if engine == 'chromium':
                    context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate', {'rate': 4})
                errors, requests = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('https:', 'http:')) else None)
                page.goto(HTML.as_uri(), wait_until='load')
                page.wait_for_function("document.querySelector('#total').textContent!=='—'")
                initial = page.evaluate("""() => ({dom:document.querySelectorAll('*').length,cards:document.querySelectorAll('.island').length,inertBlocks:document.querySelectorAll('script[type="application/json"]').length,cache:cache.size,canvas:[terrain.width,terrain.height],load:performance.timing.loadEventEnd-performance.timing.navigationStart,overflow:document.documentElement.scrollWidth>innerWidth,count:COUNT})""")
                assert initial['cards'] == 24 and initial['cache'] <= 4 and not initial['overflow'], initial
                assert initial['dom'] < initial['count'] // 256 + 300, initial
                page.screenshot(path=str(OUT / f'{engine}-{width}.png'), full_page=False)
                # axe is test tooling only; never included in shipped HTML.
                axe = OUT / 'axe.min.js'
                if axe.exists():
                    page.add_script_tag(path=str(axe))
                    audit = page.evaluate("async () => (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
                    assert not audit, audit
                # last page, exact deep link, classification, save/unsave, empty collection
                count = initial['count']
                page.locator('#jump').fill(str(count))
                page.locator('#jump-form button').click()
                assert page.url.endswith(f'#island-{count}')
                assert page.locator('#next').is_disabled()
                page.locator('#save').click()
                page.locator('#notebook').click()
                assert page.locator('.island').count() == 1
                page.locator('#save').click()
                assert page.locator('.island').count() == 0
                page.locator('#notebook').click()
                for b in range(8):
                    page.locator('#filter').select_option(str(b))
                    ids = page.locator('.island').evaluate_all('(els)=>els.map(e=>Number(e.dataset.id))')
                    assert len(ids) == 24 and all(i % 8 == b for i in ids)
                page.locator('#quality').select_option('low')
                assert page.locator('#terrain').evaluate('(el)=>el.width') <= 360
                page.locator('#random').click()
                assert page.locator('#map-code').inner_text().startswith('ARCHIPELAGO /')
                # Long traversal via real handlers: bounded cache/DOM regardless of catalogue size.
                page.evaluate("""() => {filter=-1;bookMode=false;for(let n=0;n<150;n++){page=n*10;render();}select(COUNT-1,true);}""")
                state = page.evaluate("""() => ({dom:document.querySelectorAll('*').length,cache:cache.size,cards:document.querySelectorAll('.island').length,requests:performance.getEntriesByType('resource').length})""")
                assert state['cache'] <= 4 and state['cards'] <= 24 and state['dom'] <= initial['dom'] + 5
                page.reload()
                assert page.locator('#map-code').inner_text().endswith(str(count).zfill(6))
                assert not errors, errors
                assert not requests, requests
                # Dark theme, large text, keyboard focus, mobile overflow.
                page.emulate_media(color_scheme='dark')
                page.evaluate("document.documentElement.style.fontSize='24px'")
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.tagName') == 'A'
                page.screenshot(path=str(OUT / f'{engine}-{width}-dark.png'), full_page=False)
                results.append({'browser':engine,'width':width,'initial':initial,'after150pages':state,'errors':errors,'externalRequests':requests,'axeWCAGViolations':0 if axe.exists() else 'not run','cpuThrottle':4 if engine == 'chromium' else 1})
                context.close()
            browser.close()
        # Hostile localStorage must not prevent basic offline exploration.
        browser = p.chromium.launch()
        c = browser.new_context(offline=True)
        c.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('denied')}})")
        page = c.new_page()
        page.goto(HTML.as_uri())
        page.locator('#save').click()
        assert '本次' in page.locator('#status').inner_text()
        page.locator('#random').click()
        c.close()
        browser.close()
    (OUT / (HTML.stem + '-results.json')).write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    run()
