import test from 'node:test';
import assert from 'node:assert/strict';
import {selectRange, normalizeEvent, publicationSituation, referenceLabel} from '../assets/js/calendar.js';
import {calendarDocx} from '../assets/js/calendar-export.js';

const event=(date,key='INPC',source='INEGI',frequency='Mensual')=>normalizeEvent({
  indicator:key,publication_date:date,reference_period:'Octubre de 2026',frequency,
  institution:source,source,product:'Producto & dato <oficial>',category:'Precios',
  url:'https://www.inegi.org.mx/?a=1&b=2'
});
test('El rango mensual excluye otros meses y las fechas sin anunciar',()=>{
  const list=[event('2026-10-31'),event('2026-11-01'),event('2026-11-30'),event('2026-12-01'),event(null)];
  assert.deepEqual(selectRange(list,2026,11,1).map(e=>e.fecha_iso),['2026-11-01','2026-11-30']);
});
test('Tres meses cruzan correctamente el cambio de año',()=>{
  const list=['2026-11-30','2026-12-31','2027-01-01','2027-02-01'].map(d=>event(d));
  assert.equal(selectRange(list,2026,11,3).length,3);
});
test('La selección común a pantalla y Word combina todos los filtros',()=>{
  const list=[event('2026-11-09'),event('2026-11-09','INPP'),event('2026-11-10','RESERVAS','Banco de México','Semanal')];
  assert.equal(selectRange(list,2026,11,1,{category:'Precios',source:'INEGI',frequency:'Mensual',indicator:'INPC'}).length,1);
  assert.equal(selectRange(list,2026,11,1,{frequency:'Trimestral'}).length,0);
});
test('La sigla visible no sustituye la clave interna del indicador',()=>{
  assert.equal(normalizeEvent({indicator:'CONSUMO',sigla:'IMCP'}).clave,'CONSUMO');
  assert.equal(normalizeEvent({indicator:'DESOCUP',sigla:'ENOE'}).clave,'DESOCUP');
});
test('Una fecha pasada no confirma publicación; ENOE trimestral conserva periodicidad',()=>{
  assert.match(publicationSituation({publication_date:'2000-01-01',status:'publicado'}),/^Fecha transcurrida/);
  assert.equal(publicationSituation({publication_confirmed:true}),'Publicación confirmada');
  assert.equal(normalizeEvent({indicator:'DESOCUP',period:'Tercer trimestre de 2026',frequency:'Mensual'}).frecuencia,'Trimestral');
});
test('Word es un paquete DOCX real y escapa texto y enlaces',()=>{
  const bytes=calendarDocx({events:[{...event('2026-11-09'),nombre_corto:'Producto & dato <oficial>'}],year:2026,month:11,asOf:'2026-11-05'});
  assert.equal(Buffer.from(bytes).readUInt32LE(0),0x04034b50);
  const text=new TextDecoder().decode(bytes);
  assert.ok(text.includes('word/document.xml'));
  assert.ok(text.includes('Producto &amp; dato &lt;oficial&gt;'));
  assert.ok(text.includes('a=1&amp;b=2'));
  assert.ok(text.includes('w:orient="landscape"'));
});
test('Exportar una selección vacía y tres meses conserva meses explícitos',()=>{
  const text=new TextDecoder().decode(calendarDocx({events:[],year:2026,month:11,count:3}));
  for(const name of ['Noviembre de 2026','Diciembre de 2026','Enero de 2027']) assert.ok(text.includes(name));
  assert.ok(text.includes('Sin publicaciones registradas'));
});

test('Un periodo futuro incompatible con la publicación no se presenta como confirmado',()=>{
  assert.equal(referenceLabel({publication_date:'2027-01-08',reference_period:'Octubre de 2027'}),'Periodo por confirmar');
  assert.equal(referenceLabel({publication_date:'2027-01-08',reference_period:'Octubre de 2026'}),'Octubre de 2026');
});

test('La fecha oficial sin evidencia no se presenta como un boletín publicado', () => {
  const e = {indicator:'DESOCUP', publication_date:'2026-11-26', status:'publicado',
    url:'https://www.inegi.org.mx/app/saladeprensa/calendario/'};
  const pending = normalizeEvent({...e, publication_confirmed:false});
  assert.equal(pending.estatus, 'sin_confirmar');
  assert.match(pending.situacion, /boletín aún sin confirmar/);
  const proof = 'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/iooe/IOE2026_11.pdf';
  const confirmed = normalizeEvent({...e, publication_confirmed:true, publication_evidence_url:proof});
  assert.equal(confirmed.estatus, 'publicado');
  assert.equal(confirmed.situacion, 'Publicación confirmada');
  assert.equal(confirmed.url_boletin, proof);
});

test("Banxico fuera del verificador INEGI no equivale a un boletín confirmado o fallido", () => {
  const parsed = normalizeEvent({
    indicator: "REMESAS", status: "publicado", institution: "Banco de México",
    publication_date: "2026-11-03", publication_verification: "fuera_de_alcance",
  });
  assert.equal(parsed.estatus, "publicado");
  assert.equal(parsed.situacion, "Fecha de calendario · consultar fuente");
});

// ENOE: la ficha no debe enlazar un boletín de un periodo distinto.
import {readFileSync} from "node:fs";
import vm from "node:vm";

const app=readFileSync(new URL("../assets/js/app.js", import.meta.url),"utf8");
function part(name) {
  const i=app.indexOf("function " + name + "(");
  if(i<0) return "";
  return app.slice(i,app.indexOf("\n}",i)+2);
}
const CAL="https://www.inegi.org.mx/app/saladeprensa/calendario/";
const SEP="https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/iooe/IOE2026_10.pdf";
function ofSept() {
  return {key:"DESOCUP",fuente:{nombre:"INEGI"},last_observation:"Sep 26",periodo_referencia:"Sep 26",
    fecha_publicacion:"22-oct-2026",url_boletin_oficial:SEP,periodo_boletin:"Sep 26",
    boletin_validado:true,
    enoe_mensual:{periodo:"Sep 26",fuente:SEP,boletin:"634/26",publicado_en:"2026-10-22"}};
}
function replay(ind) {
  let opened;
  const context={
    ind, el:()=>({children:[],querySelector(){return null;},append(...nodes){this.children.push(...nodes);}}),
    productBtn:(label,icon,enabled,title,click,kind)=>({label,enabled,title,click,kind,setAttribute(){}}),
    openBoletin:url=>{opened=url;},
    document:{},
  };
  const result=vm.runInNewContext(["verifiedMonthlyEnoe","productToolbar","fechaPubDato"].map(part).join("\n")
    + "\n[productToolbar(ind).children,fechaPubDato(ind)]",context);
  const doc=result[0].find(n=>n.kind==="boletin"), note=result[0].find(n=>n.kind==="nota");
  doc.click();
  return {label:doc.label,title:doc.title,date:result[1],opened,note};
}
test("September authentic monthly bulletin remains accessible with its publication day",()=>{
  const r=replay(ofSept());
  assert.equal(r.opened,SEP); assert.equal(r.label,"Boletín oficial");
  assert.match(r.date,/\b22\b.*oct.*2026/i);
});
test("October observation + September PDF and day render neither as current",()=>{
  const r=replay({...ofSept(),last_observation:"Oct 26",periodo_referencia:"Oct 26",boletin_validado:false});
  assert.equal(r.opened,CAL); assert.equal(r.label,"Calendario INEGI"); assert.equal(r.date,null);
});
test("Even a discovery flag cannot override a conflicting monthly parser",()=>{
  const r=replay({...ofSept(),last_observation:"Oct 26",periodo_referencia:"Oct 26",periodo_boletin:"Oct 26",boletin_validado:true});
  assert.equal(r.opened,CAL); assert.equal(r.date,null);
});
test("Missing supplement and conflicting URLs degrade to listing",()=>{
  for(const changes of [{enoe_mensual:undefined},{url_boletin_oficial:SEP.replace("_10","_11")}]){
    const r=replay({...ofSept(),...changes});
    assert.equal(r.opened,CAL); assert.equal(r.date,null);
  }
});
test("Quarterly, external, query-string and invalid calendar-date data do not qualify",()=>{
  const q=SEP.replace("/iooe/IOE2026_10","/enoe/enoe2026_11");
  for(const fuente of [q,SEP.replace("www.inegi.org.mx","otra.example"),SEP+"?x=1"]){
    const r=replay({...ofSept(),url_boletin_oficial:fuente,enoe_mensual:{...ofSept().enoe_mensual,fuente}});
    assert.equal(r.opened,CAL); assert.equal(r.date,null);
  }
  const r=replay({...ofSept(),enoe_mensual:{...ofSept().enoe_mensual,publicado_en:"2026-02-30"}});
  assert.equal(r.opened,CAL); assert.equal(r.date,null);
});
test("Non-ENOE source and release-date behavior unchanged",()=>{
  const url="https://www.banxico.org.mx/";
  const r=replay({key:"FIX",fuente:{nombre:"Banco de México"},url_fuente_oficial:url,fecha_publicacion:"25-nov-2026"});
  assert.equal(r.opened,url);assert.equal(r.date,"25-nov-2026");
  const inegi=replay({key:"IMAI",fuente:{nombre:"INEGI"},url_boletin_oficial:SEP,fecha_publicacion:"22-oct-2026"});
  assert.equal(inegi.opened,SEP);assert.equal(inegi.date,"22-oct-2026");
});

test("October using its verified bulletin restores document link and correct local calendar day",()=>{
 const url=SEP.replace("_10.pdf","_11.pdf");
 const r=replay({...ofSept(),last_observation:"Oct 26",periodo_referencia:"Oct 26",
     url_boletin_oficial:url,boletin_validado:true,
     enoe_mensual:{periodo:"Oct 26",fuente:url,boletin:"738/26",publicado_en:"2026-11-26"}});
 assert.equal(r.opened,url); assert.equal(r.label,"Boletín oficial");assert.match(r.date,/\b26\b.*nov.*2026/i);
});


test("ENOE labels a retained Word, unknown period, current Word and absent Word distinctly",()=>{
 const split={...ofSept(),last_observation:"Oct 26",periodo_referencia:"Oct 26",nota_disponible:true};
 const retained=replay({...split,nota:{periodo:"Sep 26"}}).note;
 assert.equal(retained.label,"Nota anterior · Sep 26");
 assert.equal(retained.enabled,true);
 assert.match(retained.title,/nota de Oct 26 todavía no disponible/);
 const unknown=replay(split).note;
 assert.equal(unknown.label,"Nota · periodo sin verificar");
 assert.doesNotMatch(unknown.title,/Oct 26/);
 const current=replay({...split,nota:{periodo:"Oct 26"}}).note;
 assert.equal(current.label,"Nota Análisis Indicador");
 assert.match(current.title,/Oct 26/);
 assert.equal(replay({...split,nota_disponible:false}).note.enabled,false);
 const other=replay({...split,key:"IMOAM"}).note;
 assert.equal(other.label,"Nota Análisis Indicador");
});
