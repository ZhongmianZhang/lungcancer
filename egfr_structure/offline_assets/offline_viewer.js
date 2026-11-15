(function () {
  'use strict';
  const assets = JSON.parse(document.getElementById('offline-assets').textContent);
  const report = assets.report;
  const structures = new Map(report.structures.map(s => [s.pdb_id, s]));
  const el = id => document.getElementById(id);
  const panel = el('offline-viewer');
  const select = el('structure-select');
  const status = el('viewer-status');
  let viewer = null, current = null, initialView = null, spinning = false;
  let pocketResidues = [], labelsShown = [], ligandCount = 0, atomCount = 0;

  function bytes(b64) {
    const value = atob(b64), out = new Uint8Array(value.length);
    for (let i = 0; i < value.length; i++) out[i] = value.charCodeAt(i);
    return out;
  }

  function exportAsset(key) {
    const asset = assets.files[key];
    if (!asset) return;
    const blob = new Blob([bytes(asset.base64)], {type: asset.mime});
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = asset.filename;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }

  document.addEventListener('click', event => {
    const target = event.target.closest('[data-export], [data-view]');
    if (!target) return;
    event.preventDefault();
    if (target.dataset.export) exportAsset(target.dataset.export);
    if (target.dataset.view) {
      select.value = target.dataset.view;
      loadStructure(target.dataset.view);
      panel.scrollIntoView({behavior: 'smooth', block: 'start'});
    }
  });

  const residueLabels = {
    '2ITY': [[790,'T790'], [793,'M793'], [797,'C797']],
    '2ITZ': [[858,'R858'], [793,'M793'], [797,'C797']],
    '2ITO': [[719,'S719'], [793,'M793'], [797,'C797']],
    '7TVD': [[746,'缺失区前侧 746'], [750,'缺失区后侧 750'], [762,'E762']],
    '6JXT': [[790,'T790'], [793,'M793'], [797,'C797']],
    '6JX0': [[790,'M790'], [793,'M793'], [797,'C797']],
    '6LUD': [[790,'M790'], [797,'S797'], [858,'R858']],
    '4LRM': [[771,'插入 N771'], [772,'插入 P772'], [773,'插入 G773'], [800,'标准 C797 / 作者 C800']],
    '5D41': [[790,'M790'], [948,'工程 R948']]
  };

  function baseSelection() {
    return el('show-all-chains').checked ? {hetflag: false} : {chain: current.author_chain, hetflag: false};
  }

  function ligandSelection() {
    return {chain: current.author_chain, resn: current.ligand, resi: current.ligand_author_number};
  }

  function heavy(atom) {
    const element = String(atom.elem || '').toUpperCase();
    return element !== 'H' && element !== 'D';
  }

  function calculatePocket() {
    pocketResidues = []; ligandCount = 0;
    if (!current.ligand) return;
    const ligand = viewer.selectedAtoms(ligandSelection()).filter(heavy);
    ligandCount = ligand.length;
    const protein = viewer.selectedAtoms({chain: current.author_chain, hetflag: false}).filter(heavy);
    const residues = new Set();
    for (const atom of protein) {
      for (const target of ligand) {
        const dx = atom.x-target.x, dy = atom.y-target.y, dz = atom.z-target.z;
        if (dx*dx+dy*dy+dz*dz <= 25) {residues.add(atom.resi); break;}
      }
    }
    pocketResidues = [...residues].sort((a,b) => a-b);
  }

  function applyStyle() {
    if (!viewer || !current) return;
    viewer.setStyle({}, {});
    viewer.removeAllLabels();
    const base = baseSelection();
    if (el('protein-style').value === 'sticks') {
      viewer.setStyle(base, {stick: {colorscheme: 'cyanCarbon', radius: 0.10}});
    } else {
      viewer.setStyle(base, {cartoon: {color: '#53bdc7', thickness: 0.38}});
    }
    if (el('show-pocket').checked && pocketResidues.length) {
      viewer.addStyle({chain: current.author_chain, resi: pocketResidues, hetflag: false},
        {stick: {colorscheme: 'whiteCarbon', radius: 0.15}});
    }
    const targets = residueLabels[current.pdb_id] || [];
    viewer.addStyle({chain: current.author_chain, resi: targets.map(t=>t[0]), hetflag: false},
      {stick: {colorscheme: 'orangeCarbon', radius: 0.22}, sphere: {scale: 0.25, colorscheme: 'orangeCarbon'}});
    if (current.ligand) {
      viewer.addStyle(ligandSelection(),
        {stick: {colorscheme: 'greenCarbon', radius: 0.23}, sphere: {scale: 0.27, colorscheme: 'greenCarbon'}});
    }
    if (current.pdb_id === '5D41') {
      viewer.addStyle({chain: 'A', resn: 'ANP', resi: 1102},
        {stick: {colorscheme: 'magentaCarbon', radius: 0.20}});
      viewer.addStyle({chain: 'A', resn: 'MG', resi: 1101},
        {sphere: {color: '#ce99ff', radius: 0.6}});
    }
    labelsShown = [];
    if (el('show-labels').checked) {
      for (const [resi, label] of targets) {
        const atoms = viewer.selectedAtoms({chain: current.author_chain, resi, atom: 'CA'});
        if (!atoms.length) continue;
        const atom = atoms[0];
        viewer.addLabel(label, {position: {x: atom.x, y: atom.y, z: atom.z},
          fontSize: 12, fontColor: '#ffffff', backgroundColor: '#122c3d',
          backgroundOpacity: 0.84, borderThickness: 0, inFront: true});
        labelsShown.push(resi);
      }
    }
    viewer.render();
    el('pocket-summary').textContent = current.ligand
      ? '5 Å重原子几何邻域：'+pocketResidues.length+'个残基；不代表化学键或药敏。'
      : '该结构无共晶抑制剂；展示蛋白与缺失区附近位点。';
  }

  function loadStructure(code) {
    if (!viewer || !structures.has(code)) return;
    try {
      panel.dataset.ready = 'false'; status.textContent = '正在载入内置结构…';
      current = structures.get(code);
      if (spinning) {viewer.spin(false); spinning = false; el('spin-button').textContent = '自动旋转';}
      viewer.removeAllModels(); viewer.removeAllShapes(); viewer.removeAllLabels();
      const pdb = atob(assets.files['pdb:'+code].base64);
      const model = viewer.addModel(pdb, 'pdb');
      atomCount = model.selectedAtoms({}).length;
      calculatePocket(); applyStyle();
      viewer.zoomTo(baseSelection()); viewer.render();
      initialView = viewer.getView().slice();
      el('structure-title').textContent = code+' · '+current.label;
      el('structure-description').textContent = '观察：'+current.focus;
      el('structure-caveat').textContent = current.limits;
      el('structure-metadata').textContent = '实验：X-ray；分辨率 '+current.resolution_A+' Å；作者链 '+current.author_chain+
        '；目标配体 '+(current.ligand ? current.ligand+' '+current.author_chain+current.ligand_author_number : '无');
      el('pocket-button').disabled = !current.ligand;
      el('current-pdb-download').dataset.export = 'pdb:'+code;
      status.textContent = '已离线载入 '+code+' · '+atomCount.toLocaleString()+'个原子';
      panel.dataset.ready = 'true'; panel.dataset.pdb = code;
    } catch(error) {fail(error);}
  }

  function fail(error) {
    panel.dataset.ready = 'error';
    status.textContent = '3D未能启动；正文及内置文件导出仍可使用。';
    el('viewer-error').hidden = false;
    el('viewer-error').textContent = '请使用支持WebGL并启用图形加速的Chrome、Edge或Firefox打开此HTML。';
    console.error('EGFR offline viewer:',error);
  }

  function initialize() {
    try {
      if (!window.$3Dmol) throw new Error('Embedded molecular engine is unavailable');
      viewer = $3Dmol.createViewer(el('molecule-canvas'), {backgroundColor: '#071b29', antialias: true});
      select.addEventListener('change',()=>loadStructure(select.value));
      ['show-pocket','show-labels','show-all-chains','protein-style'].forEach(id=>el(id).addEventListener('change',applyStyle));
      el('reset-button').addEventListener('click',()=>{if(initialView){viewer.setView(initialView.slice());viewer.render();}});
      el('full-button').addEventListener('click',()=>{viewer.zoomTo(baseSelection(),250);viewer.render();});
      el('pocket-button').addEventListener('click',()=>{
        if(!current.ligand)return;
        viewer.zoomTo({chain:current.author_chain,resi:pocketResidues.concat([current.ligand_author_number])},250);
        viewer.render();
      });
      el('spin-button').addEventListener('click',()=>{
        spinning=!spinning;viewer.spin(spinning?'y':false,0.6);
        el('spin-button').textContent=spinning?'停止旋转':'自动旋转';
      });
      el('png-button').addEventListener('click',()=>{
        viewer.render();const a=document.createElement('a');a.href=viewer.pngURI();a.download='EGFR_'+current.pdb_id+'.png';a.click();
      });
      window.addEventListener('resize',()=>{viewer.resize();viewer.render();});
      window.addEventListener('beforeprint',()=>{viewer.render();el('print-molecule').src=viewer.pngURI();});
      window.egfrOffline = Object.freeze({
        state:()=>({pdb:current?.pdb_id,ready:panel.dataset.ready,atomCount,ligandAtomCount:ligandCount,
          pocketResidues:pocketResidues.slice(),labels:labelsShown.slice(),view:viewer.getView().slice()}),
        exportAsset
      });
      requestAnimationFrame(()=>{loadStructure(select.value);viewer.resize();viewer.render();});
    } catch(error) {fail(error);}
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',initialize,{once:true});
  else initialize();
})();
