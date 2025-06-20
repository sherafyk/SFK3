let dropArea = document.getElementById('drop-area');
let fileElem = document.getElementById('fileElem');
let gallery = document.getElementById('gallery');
let progressContainer = document.getElementById('progress-container');
let progressBar = document.getElementById('progress-bar');
let progressInterval;
let filesToUpload = [];
let editorModal = document.getElementById('editor-modal');
let editorImg = document.getElementById('editor-image');
let zoomRange = document.getElementById('zoomRange');
let brightnessRange = document.getElementById('brightnessRange');
let contrastRange = document.getElementById('contrastRange');
let autoEnhanceBtn = document.getElementById('autoEnhance');
let applyBtn = document.getElementById('applyEdit');
let cancelBtn = document.getElementById('cancelEdit');
let rotateLeftBtn = document.getElementById('rotateLeft');
let rotateRightBtn = document.getElementById('rotateRight');
let cropper;
let currentIndex = null;
let cropperReady;

function loadCropper(){
  if(!cropperReady){
    cropperReady = new Promise((resolve, reject) => {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://cdn.jsdelivr.net/npm/cropperjs@1.5.13/dist/cropper.min.css';
      document.head.appendChild(css);
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/cropperjs@1.5.13/dist/cropper.min.js';
      script.onload = () => resolve();
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  return cropperReady;
}

function getCSRFToken(){
  const meta = document.querySelector('meta[name="csrf-token"]');
  if(meta) return meta.getAttribute('content');
  const inp = document.querySelector('input[name="csrf_token"]');
  return inp ? inp.value : '';
}

function showStatus(message){
  let el = document.getElementById('status-message');
  if(!el){
    el = document.createElement('div');
    el.id = 'status-message';
    document.body.prepend(el);
  }
  el.textContent = message;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 3000);
}

if (dropArea) {
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
  });
  dropArea.addEventListener('drop', handleDrop, false);
  fileElem.addEventListener('change', () => previewFiles(fileElem.files));
}

let form = document.getElementById('form');
if (form) {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    startProgress();
    const dt = new DataTransfer();

    const processed = await Promise.all(
      filesToUpload.map(async file => {
        const img = await createImageBitmap(file);
        const width = Math.min(img.width, 1024);
        const height = Math.min(img.height, 1024);
        let canvas;
        if (typeof OffscreenCanvas !== 'undefined') {
          canvas = new OffscreenCanvas(width, height);
        } else {
          canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
        }
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        let blob;
        if (canvas.convertToBlob) {
          blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.8 });
        } else {
          blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.8));
        }
        return new File([blob], file.name, { type: 'image/jpeg' });
      })
    );

    processed.forEach(f => dt.items.add(f));
    fileElem.files = dt.files;
    form.submit();
  });
}

document.querySelectorAll('.retry-form').forEach(f => {
  f.addEventListener('submit', startProgress);
});

function preventDefaults (e) { e.preventDefault(); e.stopPropagation(); }

function handleDrop(e) {
  let dt = e.dataTransfer;
  let files = dt.files;
  previewFiles(files);
}

function startProgress() {
  if (!progressContainer) return;
  progressContainer.style.display = 'block';
  progressBar.style.width = '0%';
  let width = 0;
  progressInterval = setInterval(() => {
    if (width < 95) {
      width += 1;
      progressBar.style.width = width + '%';
    }
  }, 150);
}

function stopProgress() {
  if (!progressContainer) return;
  clearInterval(progressInterval);
  progressBar.style.width = '100%';
  setTimeout(() => {
    progressContainer.style.display = 'none';
    progressBar.style.width = '0%';
  }, 300);
}

function previewFiles(files) {
  filesToUpload = [...files];
  Array.from(gallery.querySelectorAll('img')).forEach(img => {
    URL.revokeObjectURL(img.src);
  });
  gallery.innerHTML = '';
  const frag = document.createDocumentFragment();
  filesToUpload.forEach((file, idx) => {
    let div = document.createElement('div');
    div.className = 'preview';
    let img = document.createElement('img');
    img.classList.add('thumb');
    img.src = URL.createObjectURL(file);
    let btn = document.createElement('button');
    btn.textContent = 'Edit';
    btn.addEventListener('click', () => openEditor(idx));
    div.appendChild(img);
    div.appendChild(btn);
    frag.appendChild(div);
  });
  gallery.appendChild(frag);
}

async function openEditor(idx){
  await loadCropper();
  currentIndex = idx;
  let file = filesToUpload[idx];
  let reader = new FileReader();
  reader.onload = e => {
    editorImg.src = e.target.result;
    if (cropper) cropper.destroy();
    cropper = new Cropper(editorImg, {viewMode:1});
    zoomRange.value = 1;
    brightnessRange.value = 1;
    contrastRange.value = 1;
    editorImg.style.filter = 'none';
    editorModal.style.display = 'flex';
  };
  reader.readAsDataURL(file);
}

function closeEditor(){
  editorModal.style.display = 'none';
  if(cropper){ cropper.destroy(); cropper = null; }
}

if(zoomRange){
  zoomRange.oninput = () => {
    if(cropper) cropper.zoomTo(parseFloat(zoomRange.value));
  };
}

let filterFrame;
function updateFilters(){
  if(filterFrame) cancelAnimationFrame(filterFrame);
  filterFrame = requestAnimationFrame(() => {
    editorImg.style.filter = `brightness(${brightnessRange.value}) contrast(${contrastRange.value})`;
  });
}
if(brightnessRange){
  brightnessRange.oninput = updateFilters;
}
if(contrastRange){
  contrastRange.oninput = updateFilters;
}
rotateLeftBtn && (rotateLeftBtn.onclick = () => { if(cropper) cropper.rotate(-90); });
rotateRightBtn && (rotateRightBtn.onclick = () => { if(cropper) cropper.rotate(90); });

autoEnhanceBtn && (autoEnhanceBtn.onclick = () => {
  if(!cropper) return;
  let canvas = cropper.getCroppedCanvas();
  let ctx = canvas.getContext('2d');
  let data = ctx.getImageData(0,0,canvas.width,canvas.height).data;
  let sum = 0;
  for(let i=0;i<data.length;i+=4){
    sum += 0.299*data[i] + 0.587*data[i+1] + 0.114*data[i+2];
  }
  let avg = sum/(canvas.width*canvas.height)/255;
  let target = 0.75;
  let newBrightness = Math.min(Math.max(target/avg,0.5),1.5);
  let variance = 0;
  for(let i=0;i<data.length;i+=4){
    let lum = 0.299*data[i] + 0.587*data[i+1] + 0.114*data[i+2];
    variance += Math.pow(lum - avg*255,2);
  }
  let std = Math.sqrt(variance/(canvas.width*canvas.height))/255;
  let targetStd = 0.25;
  let newContrast = Math.min(Math.max(targetStd/std,0.5),1.5);
  brightnessRange.value = newBrightness.toFixed(2);
  contrastRange.value = newContrast.toFixed(2);
  updateFilters();
});

applyBtn && (applyBtn.onclick = () => {
  if(!cropper) return;
  let canvas = cropper.getCroppedCanvas();
  let out = document.createElement('canvas');
  out.width = canvas.width;
  out.height = canvas.height;
  let ctx = out.getContext('2d');
  ctx.filter = `brightness(${brightnessRange.value}) contrast(${contrastRange.value})`;
  ctx.drawImage(canvas, 0, 0);
  out.toBlob(blob => {
    let oldFile = filesToUpload[currentIndex];
    let newFile = new File([blob], oldFile.name, {type: oldFile.type});
    filesToUpload[currentIndex] = newFile;
    let previewImg = gallery.children[currentIndex].querySelector('img');
    URL.revokeObjectURL(previewImg.src);
    previewImg.src = URL.createObjectURL(newFile);
    closeEditor();
  }, filesToUpload[currentIndex].type);
});

cancelBtn && (cancelBtn.onclick = closeEditor);

function copy(i){
  let el = document.getElementById('md'+i);
  navigator.clipboard.writeText(el.textContent);
}
function download(i){
  let el = document.getElementById('md'+i);
  let blob = new Blob([el.textContent], {type: 'text/markdown'});
  let a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'result_'+i+'.md';
  a.click();
}

function exportJSON(i){
  let container = document.getElementById('table'+i);
  let md = tablesToMarkdown(container);
  startProgress();
  fetch('/json', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify({markdown: md})
  })
    .then(r => r.json())
    .then(data => {
      let txt = document.getElementById('json'+i);
      txt.style.display = 'block';
      try {
        const obj = JSON.parse(data.json);
        txt.value = JSON.stringify(obj, null, 2);
      } catch {
        txt.value = data.json;
      }
      document.getElementById('copyJson'+i).style.display = 'inline';
      document.getElementById('downloadJson'+i).style.display = 'inline';
      document.getElementById('prettyJson'+i).style.display = 'inline';
      showStatus('JSON generated');
    })
    .finally(() => {
      stopProgress();
    });
}

function copyJson(i){
  let el = document.getElementById('json'+i);
  navigator.clipboard.writeText(el.value);
}

function downloadJson(i){
  let el = document.getElementById('json'+i);
  let blob = new Blob([el.value], {type: 'application/json'});
  let a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'result_'+i+'.json';
  a.click();
}

function prettyPrint(i){
  let el = document.getElementById('json'+i);
  try{
    el.value = JSON.stringify(JSON.parse(el.value), null, 2);
  }catch(e){
    alert('Invalid JSON');
  }
}

function makeTableEditable(container){
  container.querySelectorAll('table').forEach((table, tIdx) => {
    table.classList.add('editable');
    table.querySelectorAll('tr').forEach((row, rIdx) => {
      row.querySelectorAll('th, td').forEach((cell, cIdx) => {
        let text = cell.textContent.trim();
        cell.textContent = '';
        let input = document.createElement('input');
        input.type = 'text';
        input.value = text;
        input.name = `t${tIdx}_r${rIdx}_c${cIdx}`;
        input.id = `t${tIdx}_r${rIdx}_c${cIdx}`;
        cell.appendChild(input);
      });
    });
  });
}

function tablesToMarkdown(container){
  let parts = [];
  container.querySelectorAll('table').forEach(table => {
    let lines = [];
    let rows = table.querySelectorAll('tr');
    rows.forEach((row, idx) => {
      let cells = row.querySelectorAll('th, td');
      let values = Array.from(cells).map(c => {
        let inp = c.querySelector('input');
        return (inp ? inp.value : c.textContent.trim()).replace(/\|/g, '\\|');
      });
      lines.push('|' + values.join('|') + '|');
      if(idx === 0){
        lines.push('|' + values.map(()=>'---').join('|') + '|');
      }
    });
    parts.push(lines.join('\n'));
  });
  return parts.join('\n\n');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-editable-table]').forEach(el => makeTableEditable(el));
});

function adminGenerateJSON(id){
  startProgress();
  const md = document.querySelector(`textarea[name='output_${id}']`).value;
  fetch('/json', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify({markdown: md})
  })
    .then(r => r.json())
    .then(data => {
      const txt = document.querySelector(`textarea[name='json_${id}']`);
      if (txt) txt.value = data.json;
      showStatus('JSON generated');
    })
    .finally(() => {
      stopProgress();
    });
}

function extractBDR(jobId, id){
  startProgress();
  fetch(`/extract_bdr/${jobId}/${id}`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCSRFToken()
    }
  })
    .then(r => r.json())
    .then(data => {
      if (data.error){
        alert(data.error);
        return;
      }
      const txt = document.querySelector(`textarea[name='bdr_md_${id}']`);
      if (txt) txt.value = data.bdr_md;
      const htmlContainer = document.querySelector(`#bdr-html-${id}`);
      if (htmlContainer) htmlContainer.innerHTML = data.html;
      showStatus('BDR tables extracted');
    })
    .finally(() => {
      stopProgress();
    });
}

function bdrTablesToJSON(jobId, id){
  startProgress();
  const md = document.querySelector(`textarea[name='bdr_md_${id}']`).value;
  fetch(`/bdr_json/${jobId}/${id}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify({markdown: md})
  })
    .then(r => r.json())
    .then(data => {
      if (data.error){
        alert(data.error);
        return;
      }
      const txt = document.querySelector(`textarea[name='bdr_json_${id}']`);
      if (txt) txt.value = data.bdr_json;
      showStatus('BDR JSON generated');
    })
    .finally(() => {
      stopProgress();
    });
}

function prettyPrintTextarea(name){
  const txt = document.querySelector(`textarea[name='${name}']`);
  if(!txt) return;
  try{
    txt.value = JSON.stringify(JSON.parse(txt.value), null, 2);
  }catch(e){
    alert('Invalid JSON');
  }
}

function adminGenerateAllJSON(){
  document.querySelectorAll('[data-json-id]').forEach(btn => {
    const id = btn.dataset.jsonId;
    adminGenerateJSON(id);
  });
}

let jsonEditor;
let currentTextarea;
let currentRowId;

function openJSONEditor(id){
  currentRowId = id;
  currentTextarea = document.querySelector(`textarea[name='json_${id}']`);
  if(!currentTextarea) return;
  let obj;
  try{
    obj = currentTextarea.value ? JSON.parse(currentTextarea.value) : {};
  }catch(e){
    alert('Invalid JSON');
    return;
  }
  const container = document.getElementById('jsoneditor');
  if(!jsonEditor){
    jsonEditor = new JSONEditor(container, {mode: 'tree'});
    jsonEditor.on('change', () => {
      try{
        const o = jsonEditor.get();
        document.getElementById('json-preview').textContent = JSON.stringify(o, null, 2);
      }catch{}
    });
  }
  jsonEditor.set(obj);
  document.getElementById('json-preview').textContent = JSON.stringify(obj, null, 2);
  document.getElementById('json-modal').style.display = 'flex';
}

function closeJSONEditor(){
  document.getElementById('json-modal').style.display = 'none';
}

document.getElementById('json-save-btn') && (document.getElementById('json-save-btn').onclick = () => {
  if(!jsonEditor || !currentTextarea) return;
  try{
    const obj = jsonEditor.get();
    const txt = JSON.stringify(obj, null, 2);
    currentTextarea.value = txt;
    const jobId = document.body.dataset.jobId;
    fetch(`/update_json/${jobId}/${currentRowId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
      },
      body: JSON.stringify({json: txt})
    }).then(r => {
      if(!r.ok){
        r.json().then(d => alert(d.error || 'Error'));
      }
    });
    closeJSONEditor();
  }catch(e){
    alert('Invalid JSON: ' + e);
  }
});

document.getElementById('json-cancel-btn') && (document.getElementById('json-cancel-btn').onclick = closeJSONEditor);
