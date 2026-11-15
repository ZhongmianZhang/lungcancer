"""Exercise the standalone file in Chromium with HTTP(S) disabled."""
import asyncio
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from playwright.async_api import async_playwright

BASE=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--html',type=Path,default=BASE/'generated/EGFR_structure_offline_20261115.html')
parser.add_argument('--output',type=Path,default=BASE/'validation')
parser.add_argument('--chromium',default=shutil.which('chromium'))
ARGS=parser.parse_args()
HTML=ARGS.html.resolve()
OUT=ARGS.output.resolve()
OUT.mkdir(parents=True,exist_ok=True)


async def main():
    isolated=Path(tempfile.mkdtemp(prefix='egfr-single-html-'))
    target=isolated/'EGFR.html';shutil.copyfile(HTML,target)
    assert len(list(isolated.iterdir()))==1
    data=json.loads((BASE/'report_data.json').read_text(encoding='utf-8'))
    network=[];errors=[];console=[];results=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path=ARGS.chromium,headless=True,
            args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        context=await browser.new_context(offline=True,accept_downloads=True,viewport={'width':1440,'height':1000})
        page=await context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:console.append({'type':m.type,'text':m.text[:700]}))
        page.on('request',lambda req:network.append(req.url) if req.url.startswith(('https:','http:')) else None)
        # Managed Chrome disallows file:// navigation. Render these same, isolated
        # bytes through Playwright's document API without changing browser policy.
        await page.set_content(target.read_text(encoding='utf-8'),wait_until='load',timeout=45000)
        try:
            await page.wait_for_function("['true','error'].includes(document.getElementById('offline-viewer').dataset.ready)",timeout=30000)
            assert await page.locator('#offline-viewer').get_attribute('data-ready')=='true'
        except Exception:
            print(json.dumps({'startup_failure':True,'status':await page.locator('#viewer-status').inner_text(),'errors':errors,'console':console[-12:]},ensure_ascii=False),flush=True)
            await page.screenshot(path=str(OUT/'startup_failure.png'),full_page=False)
            await browser.close();raise
        for s in data['structures']:
            code=s['pdb_id'];await page.select_option('#structure-select',code)
            await page.wait_for_function('(code)=>window.egfrOffline.state().pdb===code && window.egfrOffline.state().ready==="true"',arg=code)
            state=await page.evaluate('window.egfrOffline.state()')
            assert state['atomCount']>1000,state
            if s['ligand']:assert state['ligandAtomCount']>10 and len(state['pocketResidues'])>0,state
            else:
                assert state['ligandAtomCount']==0 and not state['pocketResidues'],state
                assert await page.locator('#pocket-button').is_disabled()
            results.append({'pdb':code,'atoms':state['atomCount'],'ligand_atoms':state['ligandAtomCount'],'pocket_residues':len(state['pocketResidues']),'labels':state['labels']})
            print(json.dumps(results[-1]),flush=True)
        await page.select_option('#structure-select','6LUD')
        canvas=page.locator('#molecule-canvas');await canvas.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        initial=await page.evaluate('window.egfrOffline.state().view')
        box=await canvas.bounding_box();x=box['x']+box['width']*.45;y=box['y']+box['height']*.45
        await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+130,y+55,steps=12);await page.mouse.up()
        await page.wait_for_timeout(150)
        rotated=await page.evaluate('window.egfrOffline.state().view')
        assert any(abs(a-b)>1e-5 for a,b in zip(initial,rotated)),(initial,rotated)
        await page.mouse.wheel(0,-320);await page.wait_for_timeout(200)
        zoomed=await page.evaluate('window.egfrOffline.state().view')
        assert any(abs(a-b)>1e-5 for a,b in zip(rotated,zoomed))
        await page.click('#reset-button');await page.wait_for_timeout(150)
        reset=await page.evaluate('window.egfrOffline.state().view')
        assert all(abs(a-b)<1e-4 for a,b in zip(initial,reset)),(initial,reset)
        await page.locator('#offline-viewer').screenshot(path=str(OUT/'offline_3d_6LUD.png'))
        await page.uncheck('#show-labels');assert not (await page.evaluate('window.egfrOffline.state().labels'))
        await page.check('#show-labels')
        await page.select_option('#protein-style','sticks');await page.select_option('#protein-style','cartoon')
        await page.click('#pocket-button');await page.wait_for_timeout(400)
        await page.locator('#offline-viewer').screenshot(path=str(OUT/'offline_3d_6LUD_pocket.png'))
        async with page.expect_download() as event:await page.click('#png-button')
        download=await event.value;await download.save_as(OUT/'exported_view.png')
        png=(OUT/'exported_view.png').read_bytes()
        assert png.startswith(b'\x89PNG\r\n\x1a\n') and len(png)>5000
        await page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        assert (await page.locator('#print-molecule').get_attribute('src')).startswith('data:image/png')
        async with page.expect_download() as event:await page.click('#current-pdb-download')
        download=await event.value;download_path=OUT/'exported_6LUD.pdb';await download.save_as(download_path)
        expected=next(s for s in data['structures'] if s['pdb_id']=='6LUD')['sha256']
        assert hashlib.sha256(download_path.read_bytes()).hexdigest()==expected
        async with page.expect_download() as event:await page.locator('a[data-export="references.csv"]').first.click()
        download=await event.value;await download.save_as(OUT/'exported_references.csv')
        with (OUT/'exported_references.csv').open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==30
        async with page.expect_download() as event:await page.locator('a[data-export="report_data.json"]').first.click()
        download=await event.value;await download.save_as(OUT/'exported_report_data.json')
        exported=json.loads((OUT/'exported_report_data.json').read_text(encoding='utf-8'));assert exported['meta']['offline_single_file'] is True
        assert exported['factors']==data['factors'] and exported['variants']==data['variants'] and exported['references']==data['references']
        await page.fill('#search','G724S');assert await page.locator('.searchable:not([hidden])').count()>0
        await page.fill('#search','')
        assert await page.locator('#references .reference').count()==30
        assert await page.locator('#structures .card').count()==9
        assert not network,network
        assert not errors,errors
        mobile=await browser.new_context(offline=True,viewport={'width':390,'height':844})
        mp=await mobile.new_page();mp.on('pageerror',lambda e:errors.append('mobile:'+str(e)))
        mp.on('request',lambda req:network.append(req.url) if req.url.startswith(('https:','http:')) else None)
        await mp.set_content(target.read_text(encoding='utf-8'),wait_until='load',timeout=45000)
        await mp.wait_for_selector('#offline-viewer[data-ready="true"]',timeout=30000)
        dimensions=await mp.evaluate('({viewport:innerWidth,scroll:document.documentElement.scrollWidth})')
        assert dimensions['scroll']<=dimensions['viewport']+1,dimensions
        await mp.locator('#offline-viewer').screenshot(path=str(OUT/'offline_mobile.png'))
        assert not errors,errors
        summary={'single_file_isolation':True,'load_method':'document API; file:// navigation is disabled by managed browser policy','offline_browser_context':True,'http_requests':network,'page_errors':errors,
                 'structures':results,'rotation':True,'zoom':True,'reset':True,'labels_toggle':True,'styles':True,
                 'pdb_export_hash_matches':True,'png_export':True,'print_snapshot':True,'reference_csv_rows':30,'json_scientific_content_preserved':True,
                 'mobile_widths':dimensions,'file_bytes':HTML.stat().st_size,'library':'3Dmol.js 2.5.5'}
        (OUT/'offline_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False),flush=True)
        await browser.close()


if __name__=='__main__':asyncio.run(main())
