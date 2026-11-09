import {MONTHS} from './bulletin_imai.mjs';
const fail=m=>{throw new Error(m);},flat=s=>s.replace(/\s+/g,' ').replace(/\(\s+/g,'(').replace(/\s+\)/g,')').trim(),clean=s=>s.normalize('NFKC').replace(/[−–]/g,'-').replace(/\u00a0/g,' ');
const LABELS=[["IGAE", "Actividad industrial", "Ingresos al por menor", "Asegurados permanentes IMSS", "Desocupación urbana", "Importaciones totales"], ["Tendencia del empleo manufacturero", "Momento adecuado para invertir", "IPC de la BMV real", "Tipo de cambio real México-EUA", "TIIE", "S&P 500 de EUA"]],INVERSE=[[false, false, false, false, true, false], [false, false, false, true, true, false]],HEADERS=["Índice de Indicador ingresos por Asegurados Indicador de Tasa de Indicador global de la suministro de trabajadores Importaciones Año Mes la actividad desocupación Coincidente actividad bienes y permanentes totales industrial1/ urbana económica1/ servicios al por en el IMSS menor1/", "Indicador de Índice de precios Índice confianza y cotizaciones Tasa de Standard & Tendencia del Tipo de cambio Indicador empresarial: de la Bolsa interés Poor’s 500 Año Mes empleo en las real bilateral Adelantado momento Mexicana de interbancaria (índice manufacturas México-EUA adecuado para Valores en de equilibrio bursátil de invertir1/ términos reales EUA)"];
const headerText=s=>flat(s.replace(/[12]\//g,'')).replace(/\s*-\s*/g,'-').replace(/\s*\)/g,')');
const compact=s=>s.replace(/\s+/g,'');
const ABBR=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const addMonth=(ym,d)=>{const [y,m]=ym.split('-').map(Number),n=y*12+m-1+d;return `${Math.floor(n/12)}-${String(n%12+1).padStart(2,'0')}`;};
const monthCode=(name,year)=>{const n=MONTHS.indexOf(name);if(n<0)fail('Mes no reconocido en el cuadro.');return `${year}-${String(n+1).padStart(2,'0')}`;};
export const periodText=ym=>`${MONTHS[Number(ym.slice(5))-1]} de ${ym.slice(0,4)}`;
function context(key,input){
 const count=key==='SIC'?13:6;if(input.length!==count||input.some(p=>!p.trim()))fail(`El boletín ${key} requiere ${count} páginas con texto seleccionable.`);
 const pages=input.map(clean),cover=pages[0],pub=cover.match(/(\d{1,2})\s+de\s+(\p{L}+)\s+de\s+(\d{4})/iu),number=cover.match(/BOLETÍN\s+DE\s+INDICADOR\s+(\d+\s*\/\s*\d+)/i)?.[1].replace(/\s/g,'');
 if(!pub||!number)fail('Falta la fecha o la edición del boletín.');const pm=MONTHS.indexOf(pub[2].toLowerCase())+1,py=+pub[3],pd=+pub[1],date=new Date(Date.UTC(py,pm-1,pd));
 if(!pm||date.getUTCMonth()!==pm-1||date.getUTCDate()!==pd)fail('La fecha del boletín es inválida.');if(py!==2026)fail('Se requiere actualizar el membrete institucional para ese año.');
 const identity=key==='SIC'?'CÍCLICOS (SIC)':'DE LA ACTIVIDAD ECONÓMICA (IOAE)';
 for(let i=0;i<count;i++){const p=pages[i],d=p.match(/\d{1,2}\s+de\s+\p{L}+\s+de\s+\d{4}/iu)?.[0],b=p.match(/BOLETÍN\s+DE\s+INDICADOR\s+(\d+\s*\/\s*\d+)/i)?.[1].replace(/\s/g,'');if(!flat(p).includes(identity)||flat(d||'')!==flat(pub[0])||b!==number||!new RegExp('Página\\s+'+(i+1)+'\\s*/\\s*'+count+'\\b').test(p))fail('Las páginas no pertenecen a la misma edición o producto.');}
 return {indicator:key,pages,publicationDate:`${py}-${String(pm).padStart(2,'0')}-${String(pd).padStart(2,'0')}`,bulletin:number};
}
function sicTable(text,n){
 const b=text.split(new RegExp('Cuadro\\s+'+n+'\\b'))[1]?.split('Nota:')[0],name=n===1?'Coincidente':'Adelantado';
 const ref=b?.match(new RegExp('Diferencias del Indicador '+name+' y de sus componentes\\s+([a-z]+) de (\\d{4})\\s*-\\s*([a-z]+) de (\\d{4})'));
 if(!ref)fail('Faltan los periodos del cuadro SIC.');const start=monthCode(ref[1],ref[2]),end=monthCode(ref[3],ref[4]);if(addMonth(start,11)!==end)fail('La historia debe abarcar doce meses consecutivos.');
 const unit='(diferencia en puntos respecto al mes inmediato anterior)';if(!b.includes(unit))fail('Cambió la unidad del cuadro SIC.');
 const matches=[...b.matchAll(new RegExp('^(?:(\\d{4})\\s+)?('+ABBR.join('|')+')\\.\\s+((?:-?\\d+\\.\\d{2}\\s+){6}-?\\d+\\.\\d{2})\\s*$','gm'))];if(matches.length!==12)fail('Faltan filas o columnas del cuadro SIC.');
 if(headerText(b.slice(b.indexOf(unit)+unit.length,matches[0].index))!==headerText(HEADERS[n-1]))fail('Cambió el orden o la identidad de las columnas SIC.');
 let year;return matches.map((m,i)=>{if(m[1])year=+m[1];if(!year)fail('Falta el año de una fila SIC.');const ym=`${year}-${String(ABBR.indexOf(m[2])+1).padStart(2,'0')}`;if(ym!==addMonth(start,i))fail('Las fechas del cuadro SIC no son consecutivas.');return {ym,values:m[3].trim().split(/\s+/).map(Number)};});
}
function parseSic(input){
 const f=context('SIC',input),p=f.pages,histories=[sicTable(p[2],1),sicTable(p[5],2)],[cy,ay]=histories.map(h=>h.at(-1).ym);
 if(addMonth(cy,1)!==ay||ay>=f.publicationDate.slice(0,7))fail('Los periodos de los indicadores SIC son incompatibles.');
 const intro=p[0].split('puntos dif. mensual puntos dif. mensual'),pairs=intro[1]?.match(/(\d+\.\d)\s+[▲▼]?\s*(-?\d+\.\d{2})\s+(\d+\.\d)\s+[▲▼]?\s*(-?\d+\.\d{2})/);
 if(intro.length!==2||!pairs||+pairs[2]!==histories[0].at(-1).values[0]||+pairs[4]!==histories[1].at(-1).values[0])fail('La portada no coincide con los cuadros SIC.');
 if(flat(intro[0].split('Indicador Coincidente Indicador Adelantado')[1]||'')!==`${MONTHS[+cy.slice(5)-1]} ${MONTHS[+ay.slice(5)-1]}`)fail('Los meses de portada no coinciden con los cuadros.');
 if(!p[1].includes('línea ubicada en 100')||!['Hodrick-Prescott','estandarizan','FICHA METODOLÓGICA'].every(s=>p[12].includes(s))||(!flat(p[3]).includes('Tasa de desocupación urbana')||(p[3].match(/1\//g)||[]).length!==2)||(!compact(p[7]).includes('México-EUA')||!p[7].includes('equilibrio')||(p[7].match(/2\//g)||[]).length!==3)||![p[3],p[7]].every(s=>s.includes('Serie cuyo comportamiento es inverso'))||!['no se establece la magnitud del cambio','caída significativa y generalizada'].every(s=>flat(p[9]).includes(s)))fail('Cambió la metodología o la relación inversa de los componentes SIC.');
 f.groups=histories.map((history,n)=>{const level=+pairs[n?3:1],name=n?'Adelantado':'Coincidente';if(level<=0)fail('Nivel SIC incompatible.');const direction=level>100?'por arriba':level<100?'por debajo':null,sentence=flat(p[0]).match(new RegExp('El Indicador '+name+'.{0,180}?tendencia de largo','i'));if(direction&&(!sentence||!sentence[0].includes(direction)))fail('La posición cíclica no coincide con la portada.');return {name,ym:history.at(-1).ym,period:periodText(history.at(-1).ym),level,delta:history.at(-1).values[0],history,components:LABELS[n].map((label,i)=>({label,delta:history.at(-1).values[i+1],inverse:INVERSE[n][i]}))};});
 return {...f,name:'Sistema de Indicadores Cíclicos',ym:cy,period:periodText(cy)};
}
function ioaeTable(text,n){
 let b=text.split(new RegExp('Cuadro\\s+'+n+'\\b'))[1]?.split('Nota:')[0];
 b=b?.replace(/^2\/\s*\n([a-z]+\s+-?\d+\.\d)\s*$/gm,(_,row)=>row+'2/');
 const ref=b?.match(/\n([a-z]+) y ([a-z]+) de (\d{4})\n/);if(!ref)fail('Falta el periodo del cuadro IOAE.');const months=[monthCode(ref[1],ref[3]),monthCode(ref[2],ref[3])];if(addMonth(months[0],1)!==months[1])fail('Los meses IOAE no son consecutivos.');
 const unit=['variación porcentual anual','variación porcentual mensual','índice base'][n-1];if(!b.includes(unit)||!b.includes('cifras desestacionalizadas')||!b.includes('Intervalo de confianza a 95.0 %')||!b.includes('Inferior Superior'))fail('Cambió la unidad, el ajuste o la confianza del IOAE.');
 const matches=[...b.matchAll(new RegExp('^('+ref[1]+'|'+ref[2]+')\\s+(-?\\d+\\.\\d)(?:(2/)|\\s+(-?\\d+\\.\\d)\\s+(-?\\d+\\.\\d))\\s*$','gm'))];if(matches.length!==6)fail('El cuadro IOAE requiere seis filas completas.');
 return matches.map((m,i)=>{const group=Math.floor(i/2),observed=Boolean(m[3]);if(m[1]!==ref[i%2?2:1]||observed!==(i===2))fail('Cambió el mes o la condición observado/estimado del IOAE.');if(i%2===0&&!b.slice(m.index,matches[i+2]?.index??b.length).includes(['IGAE','Actividades secundarias','Actividades terciarias'][group]))fail('Cambió el orden de actividades IOAE.');const point=+m[2],low=observed?null:+m[4],high=observed?null:+m[5];if(!observed&&!(low<=point&&point<=high))fail('El intervalo IOAE no contiene su estimación.');if(n===3&&(point<=0||(low!==null&&low<=0)))fail('El nivel del índice IOAE es inválido.');return {id:['total','secundarias','terciarias'][group],label:['IGAE','Actividades secundarias','Actividades terciarias'][group],ym:months[i%2],status:observed?'observado IMAI':'estimación IOAE',point,low,high};});
}
function parseIoae(input){
 const f=context('IOAE',input),p=f.pages,groups=[ioaeTable(p[0],1),ioaeTable(p[1],2),ioaeTable(p[1],3)];
 if(!p.slice(0,2).every(s=>['Se considera como valor observado','Indicador Mensual de la Actividad Industrial (IMAI)','independiente'].every(t=>flat(s).includes(t))))fail('Cambió la condición observada o el ajuste independiente del IOAE.');
 if(groups.some(g=>JSON.stringify(g.map(r=>[r.id,r.ym,r.status]))!==JSON.stringify(groups[0].map(r=>[r.id,r.ym,r.status]))))fail('Los cuadros IOAE mezclan meses o actividades.');
 const ym=groups[0][1].ym;if(ym>=f.publicationDate.slice(0,7))fail('La referencia IOAE es incompatible con su publicación.');const cover=p[0].split('El IOAE anticipa')[0],rates=[...cover.matchAll(/(-?\d+\.\d)\s*%/g)].map(m=>+m[1]);if(rates.join(',')!==[groups[0][1].point,groups[1][1].point].join(',')||!cover.includes(MONTHS[+ym.slice(5)-1]))fail('La portada no coincide con los cuadros IOAE.');
 const base=p[1].match(/índice base (\d{4})=100/)?.[1],method=flat(p[5]);if(!base||![`base ${base}=100`,'Factores Dinámicos','validación cruzada','no reemplaza el cálculo tradicional del IGAE','95.0 %'].every(s=>method.includes(s)))fail('Cambió la base o la metodología del IOAE.');
 const bases=new Set(p.flatMap(s=>[...s.matchAll(/base (\d{4})=100/g)].map(m=>m[1])));if(bases.size!==1)fail('Hay bases incompatibles en el IOAE.');
 return {...f,name:'Indicador Oportuno de la Actividad Económica',ym,period:periodText(ym),base,rows:groups[0].map((r,i)=>({id:r.id,label:r.label,ym:r.ym,status:r.status,yoy:groups[0][i],mom:groups[1][i],index:groups[2][i]}))};
}
export function parseCycles(key,pages){return key==='SIC'?parseSic(pages):parseIoae(pages);}
export const currentIoae=f=>f.rows.filter(r=>r.ym===f.ym);
export const intervalText=v=>v.low===null?'No publicado':`[${v.low.toFixed(1)}, ${v.high.toFixed(1)}]`;
export function cyclePreview(f){return f.indicator==='SIC'?{meta:['Referencia','Tendencia de largo plazo = 100'],caption:'Niveles y cambios mensuales en puntos',head:['Indicador y periodo','Nivel','Cambio mensual'],rows:f.groups.map(g=>[`${g.name} · ${g.period}`,g.level.toFixed(1),g.delta.toFixed(2)+' puntos'])}:{meta:['Carácter','Estimaciones e IC al 95%'],caption:'Estimaciones desestacionalizadas e intervalos al 95%',head:['Actividad','Anual e IC (%)','Mensual e IC (%)'],rows:currentIoae(f).map(r=>[r.label,`${r.yoy.point.toFixed(1)} ${intervalText(r.yoy)}`,`${r.mom.point.toFixed(1)} ${intervalText(r.mom)}`])};}
