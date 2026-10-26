"""Check recoverable unsupported audio and blocked persistence using visible UI."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('artifacts');rows=[]
with sync_playwright() as pw:
 b=pw.chromium.launch();c=b.new_context(offline=True,viewport={'width':360,'height':800});c.add_init_script("Object.defineProperty(window,'AudioContext',{value:undefined}); Object.defineProperty(window,'webkitAudioContext',{value:undefined}); Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})");p=c.new_page();errs=[];p.on('pageerror',lambda e:errs.append(str(e)));p.goto((out/'echo-sketch.html').resolve().as_uri());p.locator('#play').click();p.wait_for_function("document.querySelector('#status').textContent.includes('不支持 Web Audio')");assert not p.locator('#play').is_disabled();before=p.locator('.step').first.get_attribute('aria-pressed');p.locator('.step').first.click();assert p.locator('.step').first.get_attribute('aria-pressed')!=before;p.get_by_text('保存与继续创作',exact=True).click();p.locator('#save').click();p.wait_for_function("document.querySelector('#status').textContent.includes('不允许本机保存')");
 with p.expect_download() as d:p.locator('#export-project').click()
 file=out/'echo-recovery-project.json';d.value.save_as(file);assert len(json.loads(file.read_text())['tracks'])==8;assert not errs;rows.append({'audioUnavailableMessage':True,'playButtonReenabled':True,'editStillWorks':True,'blockedStorageMessage':True,'projectExportStillWorks':True,'errors':errs});b.close()
(out/'echo-recovery.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(rows)
