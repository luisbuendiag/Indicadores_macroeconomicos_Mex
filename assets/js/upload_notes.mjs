import {priceCore} from './bulletin_prices.mjs';
import {demandCore} from './bulletin_demand.mjs';
import {pdfFromFiles} from './bulletin_files.mjs';
import {getDocument,GlobalWorkerOptions} from '../vendor/pdfjs/pdf.min.mjs';
import {parseBulletin,PRODUCTS} from './bulletin_parsers.mjs?v=pib-20261107';
import {buildDocx} from './bulletin_docx.mjs?v=pib-20261107';
import {drawNoteChart,chartBytes} from './bulletin_charts.mjs?v=pib-20261107';
GlobalWorkerOptions.workerSrc=new URL('../vendor/pdfjs/pdf.worker.min.mjs',import.meta.url).href;
const $=id=>document.getElementById(id),fileInput=$('bulletin-file'),status=$('upload-status');
let template,facts=null,task=null,version=0;const urls=new Set();
const dropZone=$('drop-zone');
const key=new URLSearchParams(location.search).get('indicator')||'IMAI',product=Object.hasOwn(PRODUCTS,key)?PRODUCTS[key]:null;
if(product){document.title='Crear nota desde PDF · '+(product.alias||key);$('product-name').textContent=(product.alias||key)+' · '+product.name;$('upload-hint').textContent=`PDF con texto seleccionable · ${product.pages} páginas · máximo 20 MB`;document.querySelector('.back').href='./#'+key;document.querySelector('.back').textContent='← Volver a '+key;}

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
 const gdp=f.indicator==='PIB'||f.indicator==='PIBSEC';
 const meta=[['Periodo',f.period],['Fecha del boletín',f.publicationDate]];if(f.index!=null)meta.push([f.indicator==='INPC'?f.base:(f.base?'Índice base '+f.base+'=100':'Índice estimado'),f.index.toFixed(f.indicator==='INPC'?3:1)+' puntos']);else meta.push(gdp?['Carácter',f.status]:f.indicator==='INPP'?['Cobertura','Total incluido petróleo']:['Variables','Producción, empleo, horas y remuneraciones']);
 for(const [label,value] of meta){const box=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;box.append(dt,dd);$('facts-meta').append(box);}
 $('facts-rows').replaceChildren();
 const estimated=f.indicator==='IMOAM',prices=f.indicator==='INPC'||f.indicator==='INPP';
 $('preview-caption').textContent=estimated?'Estimación e intervalo de confianza al 95%':prices?'Variaciones de precios':'Cifras desestacionalizadas';
 $('preview-head').replaceChildren();for(const label of estimated?['Variable','Estimación','Inferior','Superior']:gdp?['Actividad','Trimestral','Anual','Acumulado']:['Actividad','Mensual','Anual']){const th=document.createElement('th');th.scope='col';th.textContent=label;$('preview-head').append(th);}
 const preview=estimated?[['Índice',...f.indexInterval.map(v=>v.toFixed(1))],['Variación anual',...f.annualInterval.map(v=>v.toFixed(1)+'%')]]:(prices?priceCore(f):f.indicator==='CONSUMO'||f.indicator==='IMFBCF'?demandCore(f):f.rows).map(row=>[row.label.startsWith('Generación')?'Energía, agua y gas':row.label,row.mom.toFixed(prices?2:1)+'%',row.yoy.toFixed(prices?2:1)+'%']);
 if(gdp)preview.forEach((r,i)=>r.push(f.rows[i].ytd.toFixed(1)+'%'));
 for(const row of preview){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v;tr.append(td);}$('facts-rows').append(tr);}
 $('facts-panel').hidden=false;
}
async function receiveFiles(files){
 if(fileInput.disabled)return;
 release();const run=version;
 try{
  const file=pdfFromFiles(files);if(!file)return;
  $('selected-file').textContent=file.name;
  if(file.size>20*1024*1024||file.size<8)throw new Error('Selecciona un PDF de hasta 20 MB.');
  message('Leyendo el boletín y comprobando las cifras…');
  const bytes=new Uint8Array(await file.arrayBuffer());if(new TextDecoder().decode(bytes.subarray(0,5))!=='%PDF-')throw new Error('El archivo no es un PDF válido.');
  if(run!==version)return;
  task=getDocument({data:bytes,isEvalSupported:false,disableFontFace:true,useSystemFonts:false,disableAutoFetch:true,disableStream:true,useWorkerFetch:false});
  const parsingTask=task;const timer=setTimeout(()=>parsingTask.destroy(),30000);let pages,layout;
  try{const pdf=await task.promise;if(pdf.numPages!==product.pages)throw new Error(`El boletín ${key} requiere ${product.pages} páginas.`);pages=[];for(let i=1;i<=product.pages;i++){const page=await pdf.getPage(i);const content=await page.getTextContent();if(content.items.length>50000)throw new Error('El documento es demasiado complejo.');pages.push(lines(content.items));if((key==='INPC'&&i===4)||(key==='INPP'&&i===5)){const v=page.getViewport({scale:1});layout={width:v.width,items:content.items.filter(i=>i.str?.trim()).map(i=>({text:i.str,x0:i.transform[4],x1:i.transform[4]+i.width,top:v.height-i.transform[5]}))};}}}finally{clearTimeout(timer);}
  if(run!==version)return;facts=parseBulletin(key,pages,layout);show(facts);message('Preparando tablas y gráficas del Word…');await prepareNote(facts,run);if(run===version){dropZone.hidden=true;message('Nota preparada. Revisa el periodo y las cifras antes de descargarla.');const title=$('facts-title');title.tabIndex=-1;title.focus();}
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
 const pngs={};for(const field of ['mom','yoy']){const canvas=document.createElement('canvas');drawNoteChart(canvas,f,field);pngs[field]=await chartBytes(canvas);canvas.width=canvas.height=0;}
 if(run!==version)return;
 const bytes=buildDocx(f,template,pngs),blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),url=URL.createObjectURL(blob);urls.add(url);
 const link=$('generate-note');link.href=url;link.download=`${f.indicator}_nota_${f.ym}_recibida.docx`;link.setAttribute('aria-disabled','false');
}
window.addEventListener('pagehide',release);
try{
 if(!product)throw new Error('Indicador no disponible.');
 const response=await fetch('data/source/notas_machote/_PLANTILLA_NOTAS_VISUAL.docx',{cache:'force-cache'});if(!response.ok)throw new Error('No se pudo cargar la plantilla institucional.');template=new Uint8Array(await response.arrayBuffer());await document.fonts.load('11px "Noto Sans"');await document.fonts.load('600 11px "Noto Sans"');fileInput.disabled=false;message('Listo para recibir el boletín.');
}catch(error){message(error.message,true);}
