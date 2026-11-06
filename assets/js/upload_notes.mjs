import {pdfFromFiles} from './bulletin_files.mjs';
import {getDocument,GlobalWorkerOptions} from '../vendor/pdfjs/pdf.min.mjs';
import {parseImai} from './bulletin_imai.mjs';
import {buildDocx} from './bulletin_docx.mjs';
import {drawComponentChart,chartBytes} from './bulletin_charts.mjs';
GlobalWorkerOptions.workerSrc=new URL('../vendor/pdfjs/pdf.worker.min.mjs',import.meta.url).href;
const $=id=>document.getElementById(id),fileInput=$('bulletin-file'),status=$('upload-status');
let template,facts=null,task=null,version=0;const urls=new Set();
const dropZone=$('drop-zone');
if(new URLSearchParams(location.search).get('embedded')==='1') {
 document.body.classList.add('embedded');
 const workspace=document.querySelector('.workspace');
 new ResizeObserver(()=>{
  const frame=window.frameElement;
  if(frame)frame.style.height=Math.max(320,Math.min(1200,Math.ceil(workspace.getBoundingClientRect().height)))+'px';
 }).observe(workspace);
}
function message(text,error=false){status.textContent=text;status.classList.toggle('error',error);}
function release(){dropZone.hidden=false;version++;$('generate-note').removeAttribute('href');$('generate-note').setAttribute('aria-disabled','true');task?.destroy();task=null;facts=null;fileInput.value='';$('selected-file').textContent='';$('facts-panel').hidden=true;$('facts-rows').replaceChildren();$('facts-meta').replaceChildren();for(const url of urls)URL.revokeObjectURL(url);urls.clear();}
function lines(items){
 const rows=[];
 for(const item of items){if(!('str'in item)||!item.str.trim())continue;const y=item.transform[5],x=item.transform[4];let row=rows.find(r=>Math.abs(r.y-y)<2);if(!row){row={y,items:[]};rows.push(row);}row.items.push({x,text:item.str});}
 return rows.sort((a,b)=>b.y-a.y).map(r=>r.items.sort((a,b)=>a.x-b.x).map(x=>x.text).join(' ')).join('\n');
}
function show(f){
 $('facts-meta').replaceChildren();
 for(const [label,value] of [['Periodo',f.period],['Fecha declarada',f.publicationDate],['Índice base '+f.base+'=100',f.index.toFixed(1)+' puntos']]){const box=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;box.append(dt,dd);$('facts-meta').append(box);}
 $('facts-rows').replaceChildren();
 for(const row of f.rows){const tr=document.createElement('tr');for(const v of [row.label.startsWith('Generación')?'Energía, agua y gas':row.label,row.mom.toFixed(1)+'%',row.yoy.toFixed(1)+'%']){const td=document.createElement('td');td.textContent=v;tr.append(td);}$('facts-rows').append(tr);}
 $('facts-panel').hidden=false;
}
async function receiveFiles(files){
 if(fileInput.disabled)return;
 release();const run=version;
 try{
  const file=pdfFromFiles(files);if(!file)return;
  $('selected-file').textContent=file.name;
  if(file.size>20*1024*1024||file.size<8)throw new Error('Selecciona un PDF de hasta 20 MB.');
  message('Leyendo las cinco páginas y comprobando los cuadros…');
  const bytes=new Uint8Array(await file.arrayBuffer());if(new TextDecoder().decode(bytes.subarray(0,5))!=='%PDF-')throw new Error('El archivo no es un PDF válido.');
  if(run!==version)return;
  task=getDocument({data:bytes,isEvalSupported:false,disableFontFace:true,useSystemFonts:false,disableAutoFetch:true,disableStream:true,useWorkerFetch:false});
  const parsingTask=task;const timer=setTimeout(()=>parsingTask.destroy(),30000);let pages;
  try{const pdf=await task.promise;if(pdf.numPages!==5)throw new Error('El piloto IMAI requiere un boletín de cinco páginas.');pages=[];for(let i=1;i<=5;i++){const page=await pdf.getPage(i);const content=await page.getTextContent();if(content.items.length>50000)throw new Error('El documento es demasiado complejo.');pages.push(lines(content.items));}}finally{clearTimeout(timer);}
  if(run!==version)return;facts=parseImai(pages);show(facts);message('Preparando tablas y gráficas del Word…');await prepareNote(facts,run);if(run===version){dropZone.hidden=true;message('Nota preparada. Revisa el periodo y las cifras antes de descargarla.');const title=$('facts-title');title.tabIndex=-1;title.focus();}
 }catch(error){if(run===version){facts=null;$('facts-panel').hidden=true;message(error.name==='PasswordException'?'El PDF está protegido. Utiliza una copia sin contraseña.':error.message||'No se pudo leer el PDF. No se generó la nota.',true);}}
 finally{if(run===version){await task?.destroy();task=null;}}
}
fileInput.addEventListener('change',()=>receiveFiles(Array.from(fileInput.files)));
let dragDepth=0;
for(const eventName of ['dragenter','dragover','dragleave','drop']){
 dropZone.addEventListener(eventName,event=>{
  event.preventDefault();event.stopPropagation();
  if(eventName==='dragenter')dragDepth++;
  if(eventName==='dragleave')dragDepth=Math.max(0,dragDepth-1);
  if(eventName==='drop')dragDepth=0;
  dropZone.classList.toggle('dragging',dragDepth>0&&!fileInput.disabled);
  if(eventName==='dragover'&&event.dataTransfer)event.dataTransfer.dropEffect=fileInput.disabled?'none':'copy';
  if(eventName==='drop'&&event.dataTransfer)receiveFiles(Array.from(event.dataTransfer.files));
 });
}
// Prevent the browser from navigating away when a file misses the drop zone.
for(const eventName of ['dragover','drop'])document.addEventListener(eventName,event=>event.preventDefault());
$('clear-file').addEventListener('click',()=>{release();message('Archivo borrado. Puedes seleccionar otro boletín.');});
async function prepareNote(f,run){
 const pngs={};for(const field of ['mom','yoy']){const canvas=document.createElement('canvas');drawComponentChart(canvas,f,field);pngs[field]=await chartBytes(canvas);canvas.width=canvas.height=0;}
 if(run!==version)return;
 const bytes=buildDocx(f,template,pngs),blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),url=URL.createObjectURL(blob);urls.add(url);
 const link=$('generate-note');link.href=url;link.download=`IMAI_nota_${f.ym}_recibida.docx`;link.setAttribute('aria-disabled','false');
}
window.addEventListener('pagehide',release);
try{
 const response=await fetch('data/source/notas_machote/_PLANTILLA_NOTAS_VISUAL.docx',{cache:'force-cache'});if(!response.ok)throw new Error('No se pudo cargar la plantilla institucional.');template=new Uint8Array(await response.arrayBuffer());await document.fonts.load('11px "Noto Sans"');await document.fonts.load('600 11px "Noto Sans"');fileInput.disabled=false;message('Listo para recibir el boletín.');
}catch(error){message(error.message,true);}
