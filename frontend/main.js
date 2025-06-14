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
let applyBtn = document.getElementById('applyEdit');
let cancelBtn = document.getElementById('cancelEdit');
let cropper;
let currentIndex = null;

if (dropArea) {
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
  });
  dropArea.addEventListener('drop', handleDrop, false);
  fileElem.addEventListener('change', () => previewFiles(fileElem.files));
}

let form = document.getElementById('form');
if (form) {
  form.addEventListener('submit', e => {
    let dt = new DataTransfer();
    filesToUpload.forEach(f => dt.items.add(f));
    fileElem.files = dt.files;
    startProgress();
  });
}

document.querySelectorAll('.retry-form').forEach(f => {
  f.addEventListener('submit', startProgress);
});

function preventDefaults (e) { e.preventDefault(); e.stopPropagation(); }

function handleDrop(e) {
  let dt = e.dataTransfer;
  let files = dt.files;
  fileElem.files = files;
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
  gallery.innerHTML = '';
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
    gallery.appendChild(div);
  });
}

function openEditor(idx){
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

zoomRange.oninput = () => {
  if(cropper) cropper.zoomTo(parseFloat(zoomRange.value));
};

function updateFilters(){
  editorImg.style.filter = `brightness(${brightnessRange.value}) contrast(${contrastRange.value})`;
}
brightnessRange.oninput = updateFilters;
contrastRange.oninput = updateFilters;

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
  let md = document.getElementById('md'+i).textContent;
  startProgress();
  fetch('/json', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({markdown: md})
  })
    .then(r => r.json())
    .then(data => {
      let txt = document.getElementById('json'+i);
      txt.style.display = 'block';
      txt.value = data.json;
      document.getElementById('copyJson'+i).style.display = 'inline';
      document.getElementById('downloadJson'+i).style.display = 'inline';
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
