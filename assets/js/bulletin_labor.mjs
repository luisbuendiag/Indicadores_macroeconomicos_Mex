import {fail,flat,escape,get} from './bulletin_final.mjs';
import {MONTHS} from './bulletin_imai.mjs';
const ACTIVITY=["Total", "Población económicamente activa (PEA)", "Ocupada", "Desocupada", "Población no económicamente activa (PNEA)", "Disponible", "No disponible"];
const ACT_IDS=["population", "pea", "occupied", "unemployed", "pnea", "available", "unavailable"];
const RATES=["Tasa de participación económica", "Tasa de desocupación (TD)", "TD mujeres", "TD hombres", "Tasa de ocupación parcial y desocupación", "Tasa de presión general", "Tasa de trabajo asalariado", "Tasa de subocupación", "Tasa de condiciones críticas de ocupación", "Tasa de informalidad laboral 1", "Tasa de ocupación en el sector informal 1"];
const RATE_IDS=["participation", "unemployment", "unemployment_women", "unemployment_men", "partial", "pressure", "salary", "underemployment", "critical", "informality", "informal_sector"];
const ADJUSTED=["Tasa de participación económica", "Tasa de ocupación", "Tasa de subocupación", "Tasa de desocupación (TD)", "TD mujeres", "TD hombres", "Tasa de informalidad laboral 1", "Tasa de ocupación en el sector informal 1"];
const ADJ_IDS=["participation", "occupation", "underemployment", "unemployment", "unemployment_women", "unemployment_men", "informality", "informal_sector"];
const SECTOR_LABELS=["Posición en la ocupación", "Trabajadores subordinados y remunerados", "Empleadores", "Trabajadores por cuenta propia", "Trabajadores no remunerados", "Sector de actividad económica", "Primario", "Agricultura, ganadería, silvicultura, caza y pesca", "Secundario", "Industria extractiva y de la electricidad", "Industria manufacturera", "Construcción", "Terciario", "Comercio", "Restaurantes y servicios de alojamiento", "Transportes, comunicaciones, correo y almacenamiento", "Servicios profesionales, financieros y corporativos", "Servicios sociales", "Servicios diversos", "Gobierno y organismos internacionales", "No especificado", "Nivel de ingresos", "Hasta un salario mínimo", "Más de 1 hasta 2 salarios mínimos", "Más de 2 hasta 3 salarios mínimos", "Más de 3 hasta 5 salarios mínimos", "Más de 5 salarios mínimos", "No recibe ingresos", "No especificado"];
const SECTOR_IDS=["position_total", "salaried", "employers", "self", "unpaid", "sector_total", "primary", "agriculture", "secondary", "extractive", "manufacturing", "construction", "tertiary", "commerce", "hospitality", "transport", "professional", "social", "other_services", "government", "sector_unspecified", "income_total", "income_1", "income_2", "income_3", "income_5", "income_over5", "income_none", "income_unspecified"];
export function integers(text){
 const tokens=text.trim().split(/\s+/),found=[];
 for(let i=1;i<tokens.length-1;i++)for(let j=i+1;j<tokens.length;j++){
  const parts=[tokens.slice(0,i),tokens.slice(i,j),tokens.slice(j)].map(a=>a.join(' '));
  if(!parts.every(s=>/^-?\d{1,3}(?: \d{3})*$/.test(s)))continue;
  const v=parts.map(s=>Number(s.replaceAll(' ','')));if(v.every(Number.isSafeInteger)&&v[0]>=0&&v[1]>=0&&v[1]-v[0]===v[2])found.push(v);
 }
 if(found.length!==1)fail('Enteros ambiguos o diferencia poblacional incompatible.');return found[0];
}
function population(b,labels,ids,groups=false){
 const ms=[...b.matchAll(/^(.+?)\s+((?:-?\d+\s+)+)(\d+\.\d)\s+(\d+\.\d)(?:\s+(-?\d+\.\d))?\s*$/gm)],expected=groups?Array.from({length:3},(_,g)=>labels.map((l,i)=>g&&i===0?(g===1?'Mujeres':'Hombres'):l)).flat():labels;
 if(ms.length!==expected.length)fail('Número de filas poblacionales incompatible.');
 return ms.map((m,i)=>{
  if(m[1].replace(/\d+\//g,'').trim()!==expected[i])fail('Identidad u orden poblacional incompatible: '+expected[i]);
  const v=integers(m[2]),r={id:ids[i%ids.length],group:groups?['total','women','men'][Math.floor(i/ids.length)]:'total',label:expected[i],previous:v[0],current:v[1],difference:v[2],relative_previous:+m[3],relative_current:+m[4],relative_difference:m[5]==null?null:+m[5],series:'original'};
  if([r.relative_previous,r.relative_current].some(v=>v<0||v>100))fail('Porcentaje poblacional inválido.');return r;
 });
}
function rates(b,labels,ids,adjusted=false){
 const ms=[...b.matchAll(/^(.+?)\s+(\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s*$/gm)];if(ms.length!==labels.length)fail('Número de tasas incompatible.');
 return ms.map((m,i)=>{if(!new RegExp('^'+escape(labels[i])+'(?:\\s*\\d+/)*\\s*$').test(m[1]))fail('Identidad u orden de tasas incompatible: '+ids[i]);
 const v=m.slice(2).map(Number);if(v[0]<0||v[0]>100||!adjusted&&(v[1]<0||v[1]>100))fail('Tasa fuera de dominio.');
 return {id:ids[i],label:labels[i],...(adjusted?{current:v[0],mom:v[1],yoy:v[2]}:{previous:v[0],current:v[1],difference:v[2]}),series:adjusted?'desestacionalizada':'original'};
 });
}
export function parseLabor(f){
 const blocks=[[3,1,'1/ Valor'],[5,2,'1/ Porcentaje'],[8,4,'1/ Población']].map(([i,n,end])=>f.pages[i].split(new RegExp('Cuadro\\s+'+n+'\\b'))[1]?.split(new RegExp(end.replace('1/ ','1/\\s*')))[0]);
 for(const b of blocks)if(!b||!flat(b).includes(`${MONTHS[f.month-1]} de ${f.year-1} y ${f.year}`)||!flat(b).includes(`${f.year}-${f.year-1}`)||!new RegExp('\\b'+(f.year-1)+'\\s+'+f.year+'\\b').test(b))fail('Periodo o columnas originales incompatibles.');
 f.population=population(blocks[0],ACTIVITY,ACT_IDS,true);f.sectors=population(blocks[1],SECTOR_LABELS,SECTOR_IDS);f.rates=rates(blocks[2],RATES,RATE_IDS);
 const b=f.pages[11].split(/Cuadro\s+7\b/)[1]?.split('Nota:')[0],prev=MONTHS[(f.month+10)%12],prevYear=f.month===1?f.year-1:f.year;
 if(!b||!flat(b).includes(f.period)||!b.includes('cifras desestacionalizadas')||!flat(b).includes('puntos porcentuales')||!b.includes(prev)||!b.includes('de '+prevYear)||!b.includes('de '+(f.year-1)))fail('Periodo, serie o unidad ajustada incompatible.');
 const both=b.split('Agregado urbano de 32 ciudades');if(both.length!==2)fail('Agregación urbana incompatible.');
 f.adjusted=rates(both[0].split(/\nNacional\s*\n/)[1]||'',ADJUSTED,ADJ_IDS,true);f.urban=rates(both[1],ADJUSTED,ADJ_IDS,true);
 const method=flat(f.pages[14]),foot=flat(f.pages[8]),base=foot.match(/base enero de (\d{4})/);
 if(!base||!method.includes('X-13ARIMA-SEATS')||!method.includes('Probabilístico, bietápico, estratificado y por conglomerados')||!f.pages[3].includes('15 años y más')||!flat(f.pages[11]).includes('todos sus decimales')||!['Porcentaje respecto a la PEA','Porcentaje respecto a la población ocupada','salarios mínimos equivalentes'].every(t=>foot.includes(t)))fail('Revisar metodología, denominadores o precisión.');
 f.wageBase=base[1];
 const pop=(id,g='total')=>f.population.find(r=>r.id===id&&r.group===g);
 for(const g of ['total','women','men'])for(const c of ['previous','current']){
  if(pop('pea',g)[c]!==pop('occupied',g)[c]+pop('unemployed',g)[c]||pop('population',g)[c]!==pop('pea',g)[c]+pop('pnea',g)[c]||pop('pnea',g)[c]!==pop('available',g)[c]+pop('unavailable',g)[c])fail('Identidad poblacional incompatible.');
 }
 for(const id of ACT_IDS)for(const c of ['previous','current','difference'])if(pop(id)[c]!==pop(id,'women')[c]+pop(id,'men')[c])fail('Desglose por sexo incompatible.');
 for(const c of ['previous','current','difference'])for(const id of ['position_total','sector_total','income_total'])if(get(f,id,'sectors')[c]!==pop('occupied')[c])fail('Totales de ocupación incompatibles.');
 for(const [id,rateid] of [['pea','participation'],['unemployed','unemployment']])for(const c of ['previous','current','difference'])if(pop(id)['relative_'+c]!==get(f,rateid,'rates')[c])fail('Tasas originales y población incompatibles.');
 const cover=f.pages[0].split('Sumó ')[0],values=[...cover.matchAll(/(\d+\.\d)\s*%/g)].map(m=>+m[1]);
 if(values.join(',')!==['participation','unemployment','underemployment','informality'].map(id=>get(f,id,'rates').current).join(','))fail('Portada y tasas originales incompatibles.');
 const m=cover.match(/(\d+\.\d) millones/);if(!m||Math.abs(+m[1]-pop('pea').current/1e6)>.051)fail('PEA de portada incompatible.');
 for(const field of ['rates','adjusted','urban'])for(const r of f[field])r.denominator=r.id==='participation'?'Población de 15 años y más':['unemployment','occupation','unemployment_women','unemployment_men','partial','pressure'].includes(r.id)?'PEA':'Población ocupada';
 return f;
}
