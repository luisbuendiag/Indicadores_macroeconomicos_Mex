import {parseDemand} from './bulletin_demand.mjs';
import {parseImai,MONTHS} from './bulletin_imai.mjs';
export const PRODUCTS={
 IMAI:{name:'Indicador Mensual de la Actividad Industrial',pages:5},
 IGAE:{name:'Indicador Global de la Actividad Económica',pages:5},
 IMOAM:{name:'Indicador Mensual Oportuno de la Actividad Manufacturera',pages:4},
 EMIM:{name:'Encuesta Mensual de la Industria Manufacturera',pages:5},
 CONSUMO:{name:'Indicador Mensual del Consumo Privado',alias:'IMCP',pages:4},
 IMFBCF:{name:'Indicador Mensual de la Formación Bruta de Capital Fijo',pages:4}
};
export const SECTORS={'311':'Alimentos','312':'Bebidas y tabaco','313':'Insumos textiles','314':'Productos textiles','315':'Prendas de vestir','316':'Cuero y piel','321':'Madera','322':'Papel','323':'Impresión','324':'Petróleo y carbón','325':'Química','326':'Plástico y hule','327':'Minerales no metálicos','331':'Metálicas básicas','332':'Productos metálicos','333':'Maquinaria y equipo','334':'Computación y electrónica','335':'Equipo eléctrico','336':'Equipo de transporte','337':'Muebles','339':'Otras manufacturas'};
const fail=m=>{throw new Error(m);};
const clean=s=>s.normalize('NFKC').replace(/[−–]/g,'-').replace(/\u00a0/g,' ');
const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const NUM='(-?\\d+\\.\\d+)';
function unique(text,pattern,label){const all=[...text.matchAll(new RegExp(pattern,'giu'))];if(all.length!==1)fail('No se pudo identificar una única fila de '+label+'.');return all[0];}
function context(key,input){
 const product=PRODUCTS[key];if(!product)fail('Indicador no disponible.');
 if(input.length!==product.pages||input.some(p=>!p.trim()))fail(`El boletín ${key} debe contener ${product.pages} páginas con texto seleccionable.`);
 const pages=input.map(clean),cover=pages[0];if(!new RegExp('\\(\\s*'+(product.alias||key)+'\\s*\\)').test(cover))fail('El archivo no corresponde a '+key+'.');
 const pub=cover.match(/(\d{1,2})\s+de\s+(\p{L}+)\s+de\s+(\d{4})/iu),ref=cover.match(/\ben\s+(\p{L}+)\s+de\s+(\d{4})/iu);
 if(!pub||!ref)fail('No se identificaron la fecha y el periodo del boletín.');
 const pm=MONTHS.indexOf(pub[2].toLowerCase())+1,py=+pub[3],pd=+pub[1],month=MONTHS.indexOf(ref[1].toLowerCase())+1,year=+ref[2],date=new Date(Date.UTC(py,pm-1,pd));
 if(!pm||!month||date.getUTCMonth()!==pm-1||date.getUTCDate()!==pd||year*12+month>=py*12+pm)fail('Las fechas del archivo son incompatibles.');
 if(py!==2026)fail('Se requiere actualizar el membrete institucional para ese año.');
 const bases=new Set(pages.flatMap(p=>[...p.matchAll(/(?:índice\s+|base\s+)?((?:19|20)\d{2})\s*=\s*100/giu)].map(m=>m[1])));
 if(bases.size>1||(!bases.size&&key!=='IMOAM'))fail('No se pudo validar la base del índice.');
 return {indicator:key,name:product.name,pages,period:`${MONTHS[month-1]} de ${year}`,ym:`${year}-${String(month).padStart(2,'0')}`,publicationDate:`${py}-${String(pm).padStart(2,'0')}-${String(pd).padStart(2,'0')}`,base:[...bases][0]||null,bulletin:cover.match(/BOLETÍN\s+(?:DE\s+INDICADOR|DE\s+PRENSA)\s+(\d+\s*\/\s*\d+)/i)?.[1].replace(/\s/g,'')||null};
}
function block(page,n,f){const b=page.split(new RegExp('Cuadro\\s+'+n+'\\b'))[1]?.split(/Nota:|1\/\s*Cifras preliminares/)[0];if(!b||!new RegExp(f.period.replaceAll(' ','\\s+'),'i').test(b))fail('El periodo del cuadro '+n+' no coincide con la portada.');return b;}
function hero(f){const h=f.pages[0].match(new RegExp('(?:^|\\n|\\s)(\\d+\\.\\d+)\\s*[▲▼]?\\s*'+NUM+'\\s*%\\s*[▲▼]?\\s*'+NUM+'\\s*%'));if(!h||+h[1]<=0||+h[1]!==f.rows[0].index||+h[2]!==f.rows[0].mom||+h[3]!==f.rows[0].yoy)fail('El índice o las tasas de portada no coinciden con el cuadro 1.');}
export function parseIgae(pages){
 const f=context('IGAE',pages),a=block(f.pages[1],1,f),o=block(f.pages[3],2,f);
 if(!/desestacionalizadas/i.test(a)||!/independiente/i.test(f.pages[1])||!/CIFRAS ORIGINALES/.test(f.pages[3])||!/Cifras preliminares/i.test(f.pages[3]))fail('No se validaron el tipo de serie y su estatus.');
 f.rows=['Indicador Global de la Actividad Económica','Actividades primarias','Actividades secundarias','Actividades terciarias'].map(label=>{const m=unique(a,escape(label)+'\\s+'+NUM+'\\s+'+NUM+'\\s+'+NUM,label),n=unique(o,escape(label)+'\\s+'+NUM+'\\s+'+NUM,label);return {label,index:+m[1],mom:+m[2],yoy:+m[3],original:+n[1],ytd:+n[2]};});
 if(f.rows.some(r=>r.index<=0))fail('Los índices deben ser positivos.');
 f.index=f.rows[0].index;hero(f);return f;
}
export function parseEmim(pages){
 const f=context('EMIM',pages),a=block(f.pages[2],1,f),o=block(f.pages[3],2,f);
 if(!/desestacionalizadas/i.test(a)||!/independiente/i.test(f.pages[2])||!/CIFRAS ORIGINALES/.test(f.pages[3])||!/Cifras preliminares/i.test(f.pages[3]))fail('No se validaron las series y el estatus de la EMIM.');
 const labels=['Volumen físico de la producción','Personal ocupado total','Horas trabajadas por el personal ocupado total','Remuneraciones medias reales pagadas'];
 f.rows=labels.map((label,i)=>{const m=unique(a,'(?:^|\\n)'+escape(label)+'\\s+'+NUM+'\\s+'+NUM,label);return {label:['Producción','Personal ocupado','Horas trabajadas','Remuneraciones medias reales'][i],mom:+m[1],yoy:+m[2]};});
 const cover=f.pages[0].split(/Aumentó|Disminuyó|Se mantuvo|La Encuesta/)[0];const rates=[...cover.matchAll(/(-?\d+\.\d+)\s*%/g)].map(m=>+m[1]);
 if(rates.length!==8||f.rows.some((r,i)=>r.mom!==rates[2*i]||r.yoy!==rates[2*i+1]))fail('Las tasas de portada no coinciden con el cuadro 1.');
 const text=o.split(/31\s*-\s*33\s+Industrias manufactureras/i)[1];if(!text)fail('Falta el agregado manufacturero.');
 const starts=[...text.matchAll(/(?:^|\n)\s*(3\d{2})\s/g)];const vals=b=>{const v=[...b.matchAll(/-?\d+\.\d+/g)].map(m=>+m[0]);if(v.length!==8)fail('Cambió el número de columnas de los subsectores.');return v;};
 const total=vals(text.slice(0,starts[0]?.index));f.rows.forEach((r,i)=>Object.assign(r,{index:total[2*i],original:total[2*i+1]}));
 f.sectors=starts.map((m,i)=>{const code=m[1],b=text.slice(m.index+m[0].length,starts[i+1]?.index??text.length),v=vals(b);if(!SECTORS[code])fail('Cambió el universo de subsectores.');return {code,label:SECTORS[code],production:v[1],employment:v[3],hours:v[5],pay:v[7]};});
 if(f.sectors.map(r=>r.code).join(',')!==Object.keys(SECTORS).join(','))fail('El universo de 21 subsectores está incompleto o duplicado.');
 if(f.rows.some(r=>r.index<=0))fail('Los índices originales deben ser positivos.');return f;
}
export function parseImoam(pages){
 const f=context('IMOAM',pages),table=block(f.pages[0],1,f),whole=f.pages.join('\n');
 if(!/cifras originales/i.test(f.pages[0])||!/estadística\s+experimental/i.test(whole)||!/confianza\s+a\s+95\s*%/i.test(table))fail('No se validó el carácter estimado, la serie original o el IC al 95%.');
 const triple=label=>unique(table,'(?:^|\\n)'+label+'\\s+'+NUM+'\\s*%?\\s+'+NUM+'\\s*%?\\s+'+NUM+'\\s*%?(?=\\s*(?:\\n|$))',label).slice(1).map(Number);
 f.indexInterval=triple('Índice');f.annualInterval=triple('Variación anual');f.index=f.indexInterval[0];
 if(!(0<f.indexInterval[1]&&f.indexInterval[1]<=f.index&&f.index<=f.indexInterval[2]&&f.indexInterval[2]<500&&-100<f.annualInterval[1]&&f.annualInterval[1]<=f.annualInterval[0]&&f.annualInterval[0]<=f.annualInterval[2]&&f.annualInterval[2]<100))fail('La estimación y sus intervalos son incompatibles.');
 const headline=f.pages[0].split(/En\s+/i)[0].match(/(\d+\.\d+)\s*[▲▼]?\s*(-?\d+\.\d+)\s*%/);if(!headline||+headline[1]!==f.index||+headline[2]!==f.annualInterval[0])fail('La portada no coincide con los intervalos del cuadro 1.');
 const cov=f.pages[2].match(/En\s+(\d+(?:[.,]\d+)?)\s*%\s+de las ocasiones/i),win=f.pages[2].match(/entre\s+(\p{L}+) de (\d{4}) y\s+(\p{L}+) de (\d{4})/iu),ahead=f.pages[3].match(/alrededor de\s+(\d+)\s+días antes/i);
 if(!cov||!win||!ahead||!['RENEM','CFE','CENACE','confidencialidad'].every(x=>f.pages[3].includes(x)))fail('Cambió el bloque de evaluación o metodología del IMOAM.');
 f.coverage=Number(cov[1].replace(',','.'));if(f.coverage<0||f.coverage>100)fail('La evaluación histórica es inválida.');f.evaluation=`${win[1]} de ${win[2]} a ${win[3]} de ${win[4]}`;f.daysAhead=+ahead[1];return f;
}
export function parseBulletin(key,pages){if(key==='CONSUMO'||key==='IMFBCF')return parseDemand(context(key,pages));if(key==='IMAI')return {...parseImai(pages),name:PRODUCTS.IMAI.name};if(key==='IGAE')return parseIgae(pages);if(key==='EMIM')return parseEmim(pages);if(key==='IMOAM')return parseImoam(pages);fail('Indicador no disponible.');}
export function selectedSectors(f){return [...f.sectors].sort((a,b)=>b.production-a.production||a.code.localeCompare(b.code)).filter((_,i,a)=>i<3||i>=a.length-3);}
