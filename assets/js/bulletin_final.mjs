import {MONTHS} from './bulletin_imai.mjs';
import {parseEmoe} from './bulletin_emoe.mjs';
import {parseLabor} from './bulletin_labor.mjs';
import {parseTrade} from './bulletin_trade.mjs';
export const FINAL_PRODUCTS={EMOE:{name:'Indicadores de Confianza Empresarial',pages:7},DESOCUP:{name:'Indicadores de Ocupación y Empleo',alias:'ENOE',pages:15},BCMM:{name:'Balanza Comercial de Mercancías de México',pages:9}};
export const fail=m=>{throw new Error(m);};
export const flat=s=>s.replace(/\s+/g,' ').trim();
export const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
export function finalContext(key,input){
 const product=FINAL_PRODUCTS[key];if(input.length!==product.pages||input.some(s=>!s.trim()))fail(`Se requieren ${product.pages} páginas completas con texto seleccionable.`);
 const pages=input.map(s=>s.normalize('NFKC').replace(/[−–]/g,'-').replace(/\u00a0/g,' ').replace(/\(\s+/g,'(').replace(/\s+\)/g,')')),cover=pages[0],label=product.alias||key;
 const date=p=>p.match(/(\d{1,2})\s+de\s+(\p{L}+)\s+de\s+(\d{4})/iu)?.slice(1).join(' '),edition=p=>p.match(/BOLETÍN\s+(?:DE\s+INDICADOR|DE\s+PRENSA)\s+(\d+\s*\/\s*\d+)/i)?.[1].replace(/\s/g,''),pub=cover.match(/(\d{1,2})\s+de\s+(\p{L}+)\s+de\s+(\d{4})/iu),ref=cover.match(/\ben\s+(\p{L}+)\s+de\s+(\d{4})/iu);
 if(!pub||!ref||!edition(cover))fail('No se identificaron fecha, edición y periodo.');
 const pm=MONTHS.indexOf(pub[2].toLowerCase())+1,py=+pub[3],pd=+pub[1],month=MONTHS.indexOf(ref[1].toLowerCase())+1,year=+ref[2],d=new Date(Date.UTC(py,pm-1,pd));
 if(!pm||!month||d.getUTCMonth()!==pm-1||d.getUTCDate()!==pd||year*12+month>=py*12+pm)fail('Las fechas del archivo son incompatibles.');
 if(py!==2026)fail('Se requiere actualizar el membrete institucional para ese año.');
 for(let i=0;i<pages.length;i++){const p=flat(pages[i]);if(!new RegExp('\\(\\s*'+label+'\\s*\\)').test(p.split(/\d{1,2} de /)[0])||!new RegExp('Página\\s+'+(i+1)+'\\s*/\\s*'+pages.length+'\\b').test(p)||date(pages[i])!==date(cover)||edition(pages[i])!==edition(cover))fail('Páginas de distinto producto, edición, fecha u orden.');}
 if(key==='EMOE'&&!pages.every(p=>/INDICADORES DE CONFIANZA EMPRESARIAL/.test(p)))fail('EMOE requiere confianza empresarial, no pedidos ni tendencia.');
 if(key==='DESOCUP'&&!pages.every(p=>/INDICADORES DE OCUPACIÓN Y EMPLEO/.test(p)))fail('Se requiere ENOE mensual.');
 return {indicator:key,name:product.name,pages,period:`${MONTHS[month-1]} de ${year}`,ym:`${year}-${String(month).padStart(2,'0')}`,year,month,publicationDate:`${py}-${String(pm).padStart(2,'0')}-${String(pd).padStart(2,'0')}`,bulletin:edition(cover)};
}
export function parseFinal(key,pages,layout){const f=finalContext(key,pages);return key==='EMOE'?parseEmoe(f):key==='DESOCUP'?parseLabor(f):parseTrade(f,layout);}
export const num=(v,d=1)=>v==null?'S.S.':v.toLocaleString('es-MX',{minimumFractionDigits:d,maximumFractionDigits:d});
export const signed=(v,d=1)=>(v>0?'+':'')+num(v,d);
export const get=(f,id,field='rows')=>f[field].find(r=>r.id===id);
export function finalPreview(f){
 if(f.indicator==='EMOE')return {meta:['IGOEC',`${num(f.globalrow.level)} puntos · serie desestacionalizada`],caption:'Confianza por sector · diferencias en puntos',head:['Sector y serie','Nivel','Mensual','Anual'],rows:f.rows.map(r=>[r.label+' · '+r.series,num(r.level),signed(r.mom),signed(r.yoy)])};
 if(f.indicator==='DESOCUP')return {meta:['Cobertura','ENOE mensual · personas y tasas nacionales'],caption:'Tasas nacionales desestacionalizadas',head:['Tasa','Nivel (%)','Mensual (pp)','Anual (pp)'],rows:f.adjusted.filter(r=>['participation','unemployment','underemployment','informality'].includes(r.id)).map(r=>[r.label,num(r.current),signed(r.mom),signed(r.yoy)])};
 return {meta:['Unidad','Millones de dólares corrientes'],caption:'Mercancías · cifras originales',head:['Concepto','Mes (mdd)','Anual (%)','Enero–mes (mdd)'],rows:['exports','imports','balance'].map(id=>{const r=get(f,id);return [r.label,num(r.amount),id==='balance'?'—':num(r.yoy),num(r.ytd)];})};
}
