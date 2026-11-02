"""Optional offline Playwright/Chromium smoke checks, separate from stdlib tests."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    html=(ROOT/'site/lineage/index.html').read_text()
    kb=json.loads((ROOT/'site/lineage/knowledge.json').read_text())
    errors,requests,checks=[],[],[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            ctx=browser.new_context(offline=True,viewport={'width':1400,'height':1000})
            page=ctx.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http://','https://')) else None)
            page.set_content(html)
            assert page.locator('.node').count()==8
            assert page.locator('.paper').count()==len(kb['unique_evidence'])
            checks.append('eight modules and unique bibliography')
            page.locator('#module-search').fill('node05')
            assert page.locator('.node:visible').count()==1
            page.locator('#module-search').fill('')
            page.locator('#expand').click()
            assert page.locator('.node details[open]').count()==8
            checks.append('module search and full detail expansion')
            page.locator('#paper-search').fill('NO_SUCH_LITERATURE')
            assert page.locator('.paper:visible').count()==0
            page.locator('.citations a').first.click()
            assert page.locator('.paper:visible').count()==len(kb['unique_evidence'])
            for e in kb['evidence']:assert page.locator('[id="ref-'+e['id']+'"]').count()==1
            checks.append('filter reset and all duplicate-source citation anchors')
            page.evaluate('scrollTo(0,0)')
            page.screenshot(path='/tmp/lineage-desktop.png')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            checks.append('390px mobile layout')
            static=browser.new_context(offline=True,java_script_enabled=False).new_page()
            static.set_content(html)
            assert static.locator('.node').count()==8 and static.locator('.paper').count()==len(kb['unique_evidence'])
            checks.append('full content without JavaScript')
            page.set_content((ROOT/'lineage/generated/example/result.html').read_text())
            assert page.locator('.result').count()==4
            assert 'DNA或表达不能决定EGFR依赖' in page.locator('body').inner_text()
            assert '共享事件仍需' in page.locator('body').inner_text()
            assert not errors and not requests, json.dumps({'errors':errors,'requests':requests})
            checks.append('four-axis example and no JS errors or external requests')
        finally:browser.close()
    print(json.dumps({'status':'passed','checks':checks,'errors':errors,'external_requests':requests},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','error':type(error).__name__+': '+str(error)}));sys.exit(1)
