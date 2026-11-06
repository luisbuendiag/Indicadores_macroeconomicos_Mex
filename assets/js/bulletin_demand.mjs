// Filas completas y jerárquicas de los cuadros de consumo e inversión.
const CP=[['total','Consumo privado','Consumo privado'],['nacional','Nacional','Nacional'],['nacional_bienes','Bienes','Bienes nacionales'],['nacional_servicios','Servicios','Servicios nacionales'],['importado','Importado','Bienes importados'],['importado_bienes','Bienes','Bienes importados (detalle)']];
const INV=[['total','Formación bruta de capital fijo','Inversión fija total'],['construccion','Construcción','Construcción'],['residencial','Residencial','Residencial'],['no_residencial','No residencial','No residencial'],['maquinaria','Maquinaria y equipo','Maquinaria y equipo'],['nacional','Nacional','Equipo nacional'],['nacional_transporte','Equipo de transporte','Transporte nacional'],['nacional_otros','Maquinaria, equipo y otros bienes','Otra maquinaria nacional'],['importado','Importado','Equipo importado'],['importado_transporte','Equipo de transporte','Transporte importado'],['importado_otros','Maquinaria, equipo y otros bienes','Otra maquinaria importada']];
const DUR=origin=>[['duradero','Duradero','Duraderos'],['semi','Semi duradero','Semiduraderos'],['no','No duradero','No duraderos']].map(([id,label,short])=>[origin+'_'+id,label,short+(origin==='nacional'?' nacionales':' importados')]);
const BUYERS=[INV[0],INV[1],INV[4]].flatMap(([id,label,short])=>[[id+'_comprador',label,short],[id+'_privada','Privada',short+' privada'],[id+'_publica','Pública',short+' pública']]);
const fail=m=>{throw new Error(m);};
function rows(text,spec,fields){
 const found=[...text.matchAll(/^([^\n]+?)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$/gm)];
 if(found.length!==spec.length)fail('Cambió el número de filas o columnas del cuadro.');
 return found.map((m,i)=>{const [id,label,display]=spec[i];if(m[1].replace(/\d+\/\s*$/,'').trim()!==label)fail('Cambió el orden o la identidad de la fila '+id+'.');const values=[+m[2],+m[3]];if(values.some(v=>v< -100))fail('Hay una variación real incompatible.');return {id,label:display,[fields[0]]:values[0],[fields[1]]:values[1]};});
}
export function parseDemand(f){
 const cp=f.indicator==='CONSUMO',alias=cp?'IMCP':'IMFBCF',pub=f.pages[0].match(/\d{1,2}\s+de\s+\p{L}+\s+de\s+\d{4}/u)?.[0];
 for(let i=0;i<4;i++){const p=f.pages[i];if(!new RegExp('\\(\\s*'+alias+'\\s*\\)').test(p.slice(0,p.indexOf(pub)))||!new RegExp('Página\\s+'+(i+1)+'\\s*\\/\\s*4').test(p)||p.match(/BOLETÍN\s+DE\s+INDICADOR\s+(\d+\s*\/\s*\d+)/i)?.[1].replace(/\s/g,'')!==f.bulletin||p.match(/\d{1,2}\s+de\s+\p{L}+\s+de\s+\d{4}/u)?.[0]!==pub)fail('Las páginas no pertenecen a una misma edición del boletín.');}
 const method=f.pages[3],mb=method.match(/base fija (?:en el año|en)\s+(\d{4})/);
 if(!/FICHA METODOLÓGICA/.test(method)||!/volumen/.test(method)||!method.includes('X-13ARIMA-SEATS')||mb?.[1]!==f.base)fail('Cambió la base o la metodología del indicador.');
 const a=f.pages[1].split(/Cuadro\s+1\b/)[1]?.split(/Nota:/)[0],o=f.pages[2].split(/Cuadro\s+2\b/)[1]?.split(/(?:1\/\s*)?Cifras preliminares/)[0];
 for(const b of [a,o])if(!b||!b.replace(/\s+/g,' ').includes(f.period))fail('El periodo de los cuadros no coincide con la portada.');
 if(!/cifras desestacionalizadas/i.test(a)||!/CIFRAS ORIGINALES/.test(f.pages[2])||!/Cifras preliminares/.test(f.pages[2])||!/independiente/.test(f.pages[1]))fail('No se validaron las series, el estatus o el ajuste independiente.');
 f.rows=rows(a,cp?CP:INV,['mom','yoy']);
 f.originals=rows(o,cp?[...CP.slice(0,3),...DUR('nacional'),...CP.slice(3),...DUR('importado')]:[...INV,...BUYERS],['original','ytd']);
 const row=(list,id)=>list.find(r=>r.id===id),same=(list,a,b,fields)=>fields.every(k=>row(list,a)[k]===row(list,b)[k]);
 if(cp){if(!/Compras netas de residentes/.test(o)||!/^\s*NA\s+NA\s*$/m.test(o)||!same(f.rows,'importado','importado_bienes',['mom','yoy'])||!same(f.originals,'importado','importado_bienes',['original','ytd']))fail('Las compras netas o el desglose importado son incompatibles.');f.netPurchases={original:null,ytd:null,status:'No aplica'};}
 else for(const id of ['total','construccion','maquinaria'])if(!same(f.originals,id,id+'_comprador',['original','ytd']))fail('Los totales por comprador no coinciden con los del tipo de bien.');
 const hero=f.pages[0].match(/(?:^|\n)(\d+\.\d+)\s*[▲▼]?\s*(-?\d+\.\d+)\s*%\s*[▲▼]?\s*(-?\d+\.\d+)\s*%/);
 if(!hero||+hero[1]<=0||+hero[2]!==f.rows[0].mom||+hero[3]!==f.rows[0].yoy)fail('La portada y el cuadro ajustado no coinciden.');f.index=+hero[1];return f;
}
export function demandCore(f){const ids=f.indicator==='CONSUMO'?['total','nacional','nacional_bienes','nacional_servicios','importado']:['total','construccion','residencial','no_residencial','maquinaria','nacional','importado'];return ids.map(id=>f.rows.find(r=>r.id===id));}
export function demandPair(f){return f.indicator==='CONSUMO'?{labels:['Duraderos','Semiduraderos','No duraderos'],a:['duradero','semi','no'].map(i=>f.originals.find(r=>r.id==='nacional_'+i).ytd),b:['duradero','semi','no'].map(i=>f.originals.find(r=>r.id==='importado_'+i).ytd),names:['Nacionales','Importados'],title:'Acumulado por durabilidad de los bienes'}:{labels:['Total','Construcción','Maquinaria y equipo'],a:['total','construccion','maquinaria'].map(i=>f.originals.find(r=>r.id===i+'_privada').ytd),b:['total','construccion','maquinaria'].map(i=>f.originals.find(r=>r.id===i+'_publica').ytd),names:['Privado','Público'],title:'Acumulado por tipo de comprador'};}
