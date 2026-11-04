"""Optional offline Chromium functional check for the JAK/STAT reports."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    kb=json.loads((ROOT/'site/jak-stat/knowledge.json').read_text())
    errors,requests,checks=[],[],[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_context(offline=True,viewport={'width':1400,'height':1000}).new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http://','https://')) else None)
            content=(ROOT/'site/jak-stat/index.html').read_text();page.set_content(content)
            assert page.locator('.node').count()==7
            assert page.locator('.paper').count()==len(kb['unique_evidence'])
            checks.append('seven modules and unique bibliography')
            page.locator('#module-search').fill('node03');assert page.locator('.node:visible').count()==1
            page.locator('#module-search').fill('');page.locator('#expand').click()
            assert page.locator('.node details[open]').count()==7
            checks.append('module filtering and expansion')
            page.locator('#paper-search').fill('NO_SUCH_PAPER');assert page.locator('.paper:visible').count()==0
            page.locator('.citations a').first.click();assert page.locator('.paper:visible').count()==len(kb['unique_evidence'])
            for r in kb['evidence']:assert page.locator('[id="ref-'+r['id']+'"]').count()==1
            assert '编辑说明' in page.locator('body').inner_text()
            checks.append('all citation aliases and integrity notices')
            page.evaluate('scrollTo(0,0)');page.screenshot(path='/tmp/jakstat-desktop.png')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            checks.append('390px mobile layout')
            static=browser.new_context(offline=True,java_script_enabled=False).new_page();static.set_content(content)
            assert static.locator('.node').count()==7 and static.locator('.paper').count()==len(kb['unique_evidence'])
            checks.append('full content without JavaScript')
            page.set_content((ROOT/'jakstat/generated/example/result.html').read_text())
            assert page.locator('.signal').count()==5
            assert '信号读出，不是功能依赖' in page.locator('body').inner_text()
            page.set_content((ROOT/'jakstat/generated/model/result.html').read_text())
            assert page.locator('.dependency').count()==1
            assert '尚非临床验证' in page.locator('body').inner_text()
            assert not requests and not errors,json.dumps({'requests':requests,'errors':errors})
            checks.append('readout and model reports; zero external requests or JS errors')
        finally:browser.close()
    print(json.dumps({'status':'passed','checks':checks,'errors':errors,'external_requests':requests},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','error':type(error).__name__+': '+str(error)}));sys.exit(1)
