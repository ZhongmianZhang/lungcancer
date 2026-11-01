"""Optional offline Chromium functional check; Playwright is not a runtime dependency."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    page_html = (ROOT / "site/ras-mapk/index.html").read_text()
    data = json.loads((ROOT / "site/ras-mapk/knowledge.json").read_text())
    requests, errors, checks = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"], headless=True)
        try:
            context = browser.new_context(offline=True, viewport={"width": 1400, "height": 1050})
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: requests.append(r.url) if r.url.startswith(("http://", "https://")) else None)
            page.set_content(page_html, wait_until="domcontentloaded")
            assert page.locator('.node').count() == 10
            assert page.locator('.paper').count() == len(data['unique_evidence'])
            checks.append('10 nodes and unique evidence rendered')
            page.locator('#node-search').fill('node07')
            assert page.locator('.node:visible').count() == 1
            page.locator('#node-search').fill('')
            page.locator('#expand-nodes').click()
            assert page.locator('.node details[open]').count() == 10
            checks.append('node filtering and expansion')
            page.locator('#paper-search').fill('ORCHARD')
            assert 0 < page.locator('.paper:visible').count() < len(data['unique_evidence'])
            page.locator('#paper-search').fill('there_is_no_such_title')
            assert page.locator('.paper:visible').count() == 0
            page.locator('a[href="#ref-N07_E03"]').first.click()
            assert page.locator('.paper:visible').count() == len(data['unique_evidence'])
            assert page.locator('#ref-N07_E03').count() == 1
            checks.append('evidence filters and duplicate-publication citation aliases')
            assert '仅核题录' in page.locator('body').inner_text()
            assert '未取得结果' in page.locator('body').inner_text()
            assert page.locator('a[href="knowledge.json"]').count() == 1
            assert (ROOT / 'site/ras-mapk/README.md').is_file()
            checks.append('conference result restrictions and downloadable assets')
            page.screenshot(path='/tmp/rasmapk-desktop.png', full_page=False)
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            checks.append('390px mobile layout')
            static_context = browser.new_context(offline=True, java_script_enabled=False)
            static = static_context.new_page()
            static.set_content(page_html)
            assert static.locator('.node').count() == 10
            assert static.locator('.paper').count() == len(data['unique_evidence'])
            checks.append('no-JavaScript full content')
            page.set_content((ROOT / 'rasmapk/generated/example/result.html').read_text())
            assert page.locator('.result').count() == 4
            assert '仅通路状态读出' in page.locator('body').inner_text()
            assert '尚需验证' in page.locator('body').inner_text()
            assert not errors and not requests
            checks.append('synthetic case report and zero external requests or JS errors')
        finally:
            browser.close()
    print(json.dumps({'status':'passed','checks':checks,'requests':requests,'errors':errors}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status':'failed','error':type(error).__name__+': '+str(error)}))
        sys.exit(1)
