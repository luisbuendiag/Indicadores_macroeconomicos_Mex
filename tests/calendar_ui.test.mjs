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
