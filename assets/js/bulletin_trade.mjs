import {fail,flat,get} from './bulletin_final.mjs';
import {MONTHS} from './bulletin_imai.mjs';
const LABELS=["Exportaciones totales", "Petroleras", "No petroleras", "Agropecuarias", "Extractivas", "Manufactureras", "Automotrices", "No automotrices", "Importaciones totales", "Petroleras", "No petroleras", "Bienes de consumo", "Petroleras", "No petroleras", "Bienes intermedios", "Petroleras", "No petroleras", "Bienes de capital", "Saldo de la balanza comercial"];
const IDS=["exports", "exports_oil", "exports_non_oil", "agriculture", "extractive", "manufacturing", "automotive", "non_automotive", "imports", "imports_oil", "imports_non_oil", "consumption", "consumption_oil", "consumption_non_oil", "intermediate", "intermediate_oil", "intermediate_non_oil", "capital", "balance"];
const HISTORY_LABELS=["Exportaciones totales", "Petroleras", "No petroleras", "Importaciones totales", "Petroleras", "No petroleras", "Balanza comercial total", "Petrolera", "No petrolera"];
const HISTORY_IDS=["exports", "exports_oil", "exports_non_oil", "imports", "imports_oil", "imports_non_oil", "balance", "balance_oil", "balance_non_oil"];
const MARKET_LABELS=["Total", "Estados Unidos", "Automotriz", "Otras", "Resto del mundo", "Automotriz", "Otras"];
const MARKET_IDS=["total", "usa", "usa_auto", "usa_other", "rest", "rest_auto", "rest_other"];
const DIRS={"descenso": -1, "retroceso": -1, "caída": -1, "disminución": -1, "aumento": 1, "avance": 1, "alza": 1, "crecimiento": 1, "incremento": 1};
const N='-?\\d{1,3}(?: \\d{3})*\\.\\d',P='(?:-?\\d+\\.\\d|S\\.S\\.)',D='('+Object.keys(DIRS).join('|')+')',value=s=>s==='S.S.'?null:Number(s.replaceAll(' ','')),close=(a,b,t=.21)=>Math.abs(a-b)<=t;
function historyRows(layout,year){
 const raw=layout?.items||layout;const words=Array.isArray(raw)?raw.map(w=>{const foot=raw.find(v=>v.text==='1/'&&Math.abs(v.top-w.top)<=5&&v.x0>=w.x1-1&&v.x0-w.x1<4);return foot&&/^(?:ene\.-)?[a-z]{3}\.$/.test(w.text)?{...w,text:w.text+'1/'}:w;}):raw;if(!Array.isArray(words))fail('No se pudo leer la geometría del cuadro histórico.');
 const header=text=>{const a=words.filter(w=>w.text===text);if(a.length!==1)fail('Encabezado histórico ambiguo.');return a[0];};
 const cols=[header(String(year-2)),header(String(year-1))],tail=words.filter(w=>/^(?:ene\.-)?[a-z]{3}\.1\/$|^[a-z]{3}\.$/.test(w.text)&&w.top>cols[0].top-2&&w.top<cols[0].top+20).sort((a,b)=>a.x0-b.x0);
 if(tail.length!==4)fail('Cambió el encabezado histórico.');cols.push(...tail);
 const centers=cols.map(w=>(w.x0+w.x1)/2),edges=[centers[0]-32,...centers.slice(1).map((v,i)=>(v+centers[i])/2),centers.at(-1)+40],top=Math.max(...cols.map(w=>w.top))+6,feet=words.filter(w=>w.text==='1/'&&w.top>top);
 if(!feet.length)fail('Falta pie del cuadro histórico.');const bottom=Math.min(...feet.map(w=>w.top)),lines=[];
 for(const w of words)if(w.top>top&&w.top<bottom){let row=lines.find(r=>Math.abs(r.top-w.top)<2);if(!row){row={top:w.top,words:[]};lines.push(row);}row.words.push(w);}
 const rows=lines.sort((a,b)=>a.top-b.top).map(r=>r.words.sort((a,b)=>a.x0-b.x0)).filter(ws=>ws.some(w=>w.x0>edges[0]&&/\d/.test(w.text)));
 if(rows.length!==9)fail('Número de filas históricas incompatible.');
 return {head:tail.map(w=>w.text),rows:rows.map((ws,i)=>{
  if(ws.filter(w=>w.x1<edges[0]).map(w=>w.text).join(' ')!==HISTORY_LABELS[i])fail('Identidad histórica incompatible.');
  const values=edges.slice(1).map((b,k)=>{const s=ws.filter(w=>(w.x0+w.x1)/2>=edges[k]&&(w.x0+w.x1)/2<b).map(w=>w.text).join(' ');if(!/^-?\d{1,3}(?: \d{3})*$/.test(s))fail('Columna histórica ilegible.');return Number(s.replaceAll(' ',''));});
  return {id:HISTORY_IDS[i],label:HISTORY_LABELS[i],values};
 })};
}
function adjusted(pages){
 const e=flat(pages[4]),i=flat(pages[6]),rows=[];
 const rate=(text,pat,id,label)=>{const m=text.match(new RegExp(pat));if(!m)fail('Falta tasa ajustada '+id+'.');return {id,label,value:DIRS[m[1]]*Number(m[2]),series:'desestacionalizada'};};
 for(const [id,label,pat] of [
 ['exports','Exportaciones totales','exportaciones totales registraron un '+D+' mensual de (\\d+\\.\\d+) por ciento'],
 ['exports_non_oil','Exportaciones no petroleras','un '+D+' de (\\d+\\.\\d+) % en las exportaciones no petroleras'],
 ['exports_oil','Exportaciones petroleras','un '+D+' de (\\d+\\.\\d+) % en las petroleras'],
 ['manufacturing','Exportaciones manufactureras','las manufactureras presentaron una '+D+' mensual de (\\d+\\.\\d+) por ciento'],
 ['non_automotive','Exportaciones no automotrices','una '+D+' de (\\d+\\.\\d+) % en las exportaciones manufactureras no automotrices'],
 ['automotive','Exportaciones automotrices','un '+D+' de (\\d+\\.\\d+) % en las automotrices']])rows.push(rate(e,pat,id,label));
 for(const [id,label,pat] of [
 ['imports','Importaciones totales','importaciones totales de mercancías mostraron un '+D+' mensual de (\\d+\\.\\d+) %'],
 ['imports_non_oil','Importaciones no petroleras','un '+D+' de (\\d+\\.\\d+) % en las importaciones no petroleras'],
 ['imports_oil','Importaciones petroleras','una '+D+' de (\\d+\\.\\d+) % en las petroleras']])rows.push(rate(i,pat,id,label));
 const m=i.match(new RegExp('se observaron (incrementos|descensos) mensuales de (\\d+\\.\\d+) % en las importaciones de bienes de consumo \\('+D+' de (\\d+\\.\\d+) % en las de bienes de consumo no petroleros\\), de (\\d+\\.\\d+) % en las de bienes de uso intermedio \\('+D+' de (\\d+\\.\\d+) % en las de bienes de uso intermedio no petroleros\\) y de (\\d+\\.\\d+) % en las de bienes de capital'));
 if(!m)fail('Cambió la narrativa ajustada de importaciones por uso.');const sign=m[1]==='incrementos'?1:-1;
 for(const [id,label,v] of [['consumption','Importaciones de consumo',sign*+m[2]],['consumption_non_oil','Consumo no petrolero',DIRS[m[3]]*+m[4]],['intermediate','Importaciones intermedias',sign*+m[5]],['intermediate_non_oil','Intermedios no petroleros',DIRS[m[6]]*+m[7]],['capital','Importaciones de capital',sign*+m[8]]])rows.push({id,label,value:v,series:'desestacionalizada'});
 const total=e.match(/balanza comercial registró un (superávit|déficit) de ([\d ]+) mdd, monto que se compara con el de ([\d ]+) mdd de ([a-z]+)/);
 if(!total)fail('Falta saldo ajustado o comparación.');const s=total[1]==='superávit'?1:-1,integer=s=>Number(s.replaceAll(' ','')),balances=[{id:'balance',current:s*integer(total[2]),previous:s*integer(total[3])}];
 for(const [id,kind] of [['balance_non_oil','no petroleros'],['balance_oil','petroleros']]){const m=e.match(new RegExp('un (?:menor|mayor) (superávit|déficit) de la balanza de productos '+kind+'.*?pasó de ([\\d ]+) mdd.*?a ([\\d ]+) mdd'));if(!m)fail('Falta saldo ajustado '+id);const s=m[1]==='superávit'?1:-1;balances.push({id,previous:s*integer(m[2]),current:s*integer(m[3])});}
 for(const c of ['previous','current'])if(!close(balances[0][c],balances[1][c]+balances[2][c],2))fail('Saldos ajustados incompatibles.');return {rows,balances,previousMonth:total[4]};
}
export function parseTrade(f,layout){
 f.pages=f.pages.map(s=>s.replace(/S\s*\.\s*S\s*\./g,'S.S.').replace(/\b(I{1,3})\s+\./g,'$1.').replace(/(\d)\s+\//g,'$1/'));
 const b=f.pages[0].split(/Cuadro\s+1\b/)[1]?.split('Nota:')[0];
 if(!b||!flat(b).includes('a '+f.period)||!flat(b).includes('Enero-'+f.period)||!f.pages[0].includes('I. CIFRAS ORIGINALES')||!/1\/\s*Cifras oportunas/.test(f.pages[0])||!f.pages[0].includes('S.S. Sin significado'))fail('Referencia, acumulado o estatus incompatible.');
 const ms=[...b.matchAll(new RegExp('^(.+?)\\s+('+N+')\\s+('+P+')\\s+('+N+')\\s+('+P+')\\s*$','gm'))];if(ms.length!==IDS.length)fail('Número de filas originales incompatible.');
 f.rows=ms.map((m,i)=>{if(m[1]!==LABELS[i])fail('Identidad o jerarquía original incompatible.');return {id:IDS[i],label:LABELS[i],amount:value(m[2]),yoy:value(m[3]),ytd:value(m[4]),ytd_yoy:value(m[5]),series:'original'};});
 if(f.rows.some(r=>r.id!=='balance'&&(r.amount<0||r.ytd<0||r.yoy==null||r.ytd_yoy==null)))fail('Flujo nominal o tasa inválidos.');
 const hist=historyRows(layout,f.year);f.history=hist.rows;
 const expected=Array.from({length:3},(_,k)=>MONTHS[(f.month-3+k+12)%12].slice(0,3)+'.'+(k===2?'1/':''));
 if(hist.head.slice(0,3).join(',')!==expected.join(',')||hist.head[3]!=='ene.-'+MONTHS[f.month-1].slice(0,3)+'.1/')fail('Periodo histórico incompatible.');
 if(f.history.some(r=>!r.id.startsWith('balance')&&r.values.some(v=>v<0)))fail('Flujo histórico negativo.');
 const market=f.pages[2].split(/Cuadro\s+3\b/)[1]?.split(/1\/\s*Cifras/)[0];if(!market||!flat(market).includes('a '+f.period)||!market.includes('Exportaciones no petroleras')||!flat(market).includes(`${f.year-1} ${f.year}`))fail('Cobertura o periodo de mercados incompatible.');
 const mm=[...market.matchAll(/^(.+?)\s+(\d+\.\d{2})\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s*$/gm)];if(mm.length!==7)fail('Número de mercados incompatible.');
 f.markets=mm.map((m,i)=>{if(m[1]!==MARKET_LABELS[i])fail('Orden de mercados incompatible.');return {id:MARKET_IDS[i],label:MARKET_LABELS[i],share:+m[2],values:m.slice(3).map(Number)};});
 if(f.markets[0].share!==100||f.markets.some(r=>r.share<0||r.share>100))fail('Participaciones inválidas.');
 const a=adjusted(f.pages);f.adjusted=a.rows;f.balances=a.balances;
 if(a.previousMonth!==MONTHS[(f.month+10)%12]||!f.pages[4].includes('II. CIFRAS DESESTACIONALIZADAS'))fail('Comparación ajustada incompatible.');
 if(!['X-13ARIMA-SEATS','Pedimento aduanal','registros administrativos','Periodicidad Mensual'].every(s=>flat(f.pages[8]).includes(s)))fail('Revisar metodología BCMM.');
 for(const field of ['amount','ytd']){
  if(!close(get(f,'exports')[field]-get(f,'imports')[field],get(f,'balance')[field]))fail('Saldo distinto de exportaciones menos importaciones.');
  for(const [total,children] of [['exports',['exports_oil','exports_non_oil']],['exports_non_oil',['agriculture','extractive','manufacturing']],['manufacturing',['automotive','non_automotive']],['imports',['imports_oil','imports_non_oil']],['imports',['consumption','intermediate','capital']],['consumption',['consumption_oil','consumption_non_oil']],['intermediate',['intermediate_oil','intermediate_non_oil']]])if(!close(get(f,total)[field],children.reduce((s,id)=>s+get(f,id)[field],0)))fail('Desglose incompatible: '+total);
 }
 for(const id of HISTORY_IDS.slice(0,7)){const r=get(f,id),h=get(f,id,'history');if(!close(r.amount,h.values[4],.51)||!close(r.ytd,h.values[5],.51))fail('Cuadros 1 y 2 incompatibles.');}
 for(let k=0;k<6;k++)for(const suffix of ['','_oil','_non_oil'])if(!close(get(f,'exports'+suffix,'history').values[k]-get(f,'imports'+suffix,'history').values[k],get(f,'balance'+suffix,'history').values[k],2))fail('Saldo histórico incompatible.');
 for(const [total,children] of [['total',['usa','rest']],['usa',['usa_auto','usa_other']],['rest',['rest_auto','rest_other']]])if(!close(get(f,total,'markets').share,children.reduce((s,id)=>s+get(f,id,'markets').share,0),.02))fail('Participaciones de mercados incompatibles.');
 if(get(f,'total','markets').values.slice(-2).join(',')!==[get(f,'exports_non_oil').yoy,get(f,'exports_non_oil').ytd_yoy].join(','))fail('Mercados y exportaciones no petroleras incompatibles.');
 const cover=f.pages[0].split(/Aumentaron las exportaciones|Disminuyeron las exportaciones/)[0],m=cover.match(/\n(-?\d{1,3}(?: \d{3})*)\s+(\d{1,3}(?: \d{3})*)\s*[▲▼]?\s*(-?\d+\.\d) %\s+(\d{1,3}(?: \d{3})*)\s*[▲▼]?\s*(-?\d+\.\d) %/);
 if(!m||!close(value(m[1]),get(f,'balance').amount,.51)||!close(value(m[2]),get(f,'exports').amount,.51)||!close(value(m[4]),get(f,'imports').amount,.51)||+m[3]!==get(f,'exports').yoy||+m[5]!==get(f,'imports').yoy)fail('Portada y cuadro 1 incompatibles.');return f;
}
