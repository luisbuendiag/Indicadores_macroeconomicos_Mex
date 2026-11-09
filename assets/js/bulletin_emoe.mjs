import {fail,flat,escape} from './bulletin_final.mjs';
const N='(-?\\d+\\.\\d+)',COMPONENTS=['Momento para invertir','Situación presente del país','Situación futura del país','Situación presente de la empresa','Situación futura de la empresa'];
export function parseEmoe(f){
 if(!/centrado en 50/.test(f.pages[6])||!/promedio ponderado/.test(flat(f.pages[0])))fail('Cambió la metodología de confianza.');
 const m=f.pages[0].match(new RegExp(N+'\\s*puntos\\s*[▲▼]?\\s*'+N+'\\s*puntos\\s*[▲▼]?\\s*'+N+'\\s*puntos'));
 if(!m)fail('No se identificó el IGOEC de portada.');
 f.globalrow={label:'IGOEC',level:+m[1],mom:+m[2],yoy:+m[3],series:'desestacionalizada'};f.rows=[];f.components=[];
 if(f.globalrow.level<0||f.globalrow.level>100)fail('IGOEC fuera de dominio.');
 for(const [page,id,label,series] of [[1,1,'Manufacturas','desestacionalizada'],[2,2,'Construcción','original'],[3,3,'Comercio','original'],[3,4,'Servicios no financieros','original']]){
  const b=f.pages[page].split(new RegExp('Cuadro\\s+'+id+'\\b'))[1]?.split('Fuente:')[0];
  if(!b||!new RegExp(escape(f.period).replaceAll(' ','\\s+'),'i').test(b.split('(puntos)')[0])||!new RegExp('cifras\\s+'+(id===1?'desestacionalizadas':'originales')).test(b))fail('Periodo o tipo de serie sectorial incompatible.');
  if(id===1&&!/Componente no sujeto a desestacionalización/.test(flat(b))||id===2&&!/Componente ajustado por efecto estacional/.test(flat(b)))fail('Cambió el ajuste de los componentes.');
  if([...b.matchAll(/(?:^|\n)\s*([a-e])\)/g)].map(m=>m[1]).join('')!=='abcde')fail('Orden de componentes de confianza incompatible.');
  const identities=['Momento adecuado para invertir','Situación económica presente del país','Situación económica futura del país','Situación económica presente de la empresa','Situación económica futura de la empresa'];
  for(let j=0;j<identities.length;j++)if(!new RegExp(String.fromCharCode(97+j)+'\\)\\s*'+escape(identities[j])).test(b))fail('Identidad de componentes incompatible.');
  const ms=[...b.matchAll(new RegExp(N+'\\s+'+N+'\\s+'+N+'\\s+(\\d+)\\s+por\\s+(arriba|debajo)','g'))];
  if(ms.length!==6)fail('Cuadro de confianza incompleto.');
  ms.forEach((m,i)=>{
   const row={label:i?COMPONENTS[i-1]:label,sector:label,level:+m[1],mom:+m[2],yoy:+m[3],months:+m[4],side:m[5],series,table:id};
   if(i&&id===1&&i>=3)row.series='original';if(i===1&&id===2)row.series='desestacionalizada';
   if(row.level<0||row.level>100||row.months<1||row.level===50||(row.level>50)!==(row.side==='arriba'))fail('Umbral de confianza incompatible.');
   (i?f.components:f.rows).push(row);
  });
 }
 return f;
}
