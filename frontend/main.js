let dropArea = document.getElementById('drop-area');
let fileElem = document.getElementById('fileElem');
let gallery = document.getElementById('gallery');

if (dropArea) {
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
  });
  dropArea.addEventListener('drop', handleDrop, false);
  fileElem.addEventListener('change', () => previewFiles(fileElem.files));
}

function preventDefaults (e) { e.preventDefault(); e.stopPropagation(); }

function handleDrop(e) {
  let dt = e.dataTransfer;
  let files = dt.files;
  fileElem.files = files;
  previewFiles(files);
}

function previewFiles(files) {
  gallery.innerHTML = '';
  [...files].forEach(file => {
    let img = document.createElement('img');
    img.classList.add('thumb');
    img.src = URL.createObjectURL(file);
    gallery.appendChild(img);
  });
}

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
