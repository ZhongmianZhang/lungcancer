"""Optional Chromium functional checks; no web requests or clinical input."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    kb = json.loads((ROOT/'site/multiomics/knowledge.json').read_text())
    checks, errors, requests = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        try:
            page = browser.new_context(offline=True, viewport={'width':1400, 'height':1000}).new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http://', 'https://')) else None)
            content = (ROOT/'site/multiomics/index.html').read_text()
            page.set_content(content)
            assert page.locator('.node').count() == 7
            assert page.locator('.paper').count() == len(kb['unique_evidence'])
            assert page.locator('.platform').count() == 7
            checks.append('seven research modules, seven versioned platforms, unique bibliography')
            page.locator('#platform-search').fill('Hartwig')
            assert page.locator('.platform:visible').count() == 1
            page.locator('#platform-search').fill('')
            page.locator('#module-search').fill('node04')
            assert page.locator('.node:visible').count() == 1
            page.locator('#module-search').fill(''); page.locator('#expand').click()
            assert page.locator('.node details[open]').count() == 7
            checks.append('platform and mechanism filtering; full expansion')
            page.locator('#paper-search').fill('NO_SUCH_SOURCE')
            assert page.locator('.paper:visible').count() == 0
            page.locator('.citations a').first.click()
            assert page.locator('.paper:visible').count() == len(kb['unique_evidence'])
            for r in kb['evidence']:
                assert page.locator('[id="ref-'+r['id']+'"]').count() == 1
            text = page.locator('body').inner_text()
            assert 'JCR排名待核验' in text and '仅核题录；未审读结果' in text
            assert '更正与完整性说明' in text
            checks.append('citation aliases, filter reset, JCR uncertainty and metadata-only conference labels')
            page.evaluate('scrollTo(0,0)'); page.screenshot(path='/tmp/omniresist-desktop.png')
            page.set_viewport_size({'width':390, 'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            checks.append('390px mobile layout without page overflow')
            static = browser.new_context(offline=True, java_script_enabled=False).new_page()
            static.set_content(content)
            assert static.locator('.node').count() == 7
            assert static.locator('.paper').count() == len(kb['unique_evidence'])
            checks.append('complete bibliography and mechanisms without JavaScript')
            page.set_content((ROOT/'omniresist/generated/plasma/result.html').read_text())
            assert page.locator('.assay').count() == 1 and page.locator('.gap').count() >= 4
            assert '低于该实验室' in page.locator('body').inner_text()
            page.set_content((ROOT/'omniresist/generated/ret/result.html').read_text())
            assert page.locator('.finding').count() == 1
            assert 'CCDC6::RET' in page.locator('body').inner_text()
            assert 'JCR筛选' in page.locator('body').inner_text()
            assert not errors and not requests, json.dumps({'errors':errors, 'requests':requests})
            checks.append('synthetic negative and RET reports; zero JavaScript errors or external requests')
        finally:
            browser.close()
    print(json.dumps({'status':'passed', 'checks':checks, 'errors':errors, 'external_requests':requests}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status':'failed', 'error':type(error).__name__+': '+str(error)}))
        sys.exit(1)
