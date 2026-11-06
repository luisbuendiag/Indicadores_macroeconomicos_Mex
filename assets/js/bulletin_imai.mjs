/* Reglas de extracción del IMAI. Archivo aportado, independiente del corte publicado. */
export const LABELS=['Actividad industrial','Minería','Generación, transmisión','Construcción','Industrias manufactureras'];
export const MONTHS=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const clean=s=>s.normalize('NFKC').replace(/[−–]/g,'-').replace(/\u00a0/g,' ');
const fail=m=>{throw new Error(m);};
export function parseImai(pages){
 if(pages.length!==5||pages.some(p=>!p.trim()))fail('Se requieren boletines IMAI de cinco páginas con texto seleccionable. No se generó la nota.');
 pages=pages.map(clean);const cover=pages[0];
 if(!/\(\s*IMAI\s*\)/.test(cover)||!/ACTIVIDAD INDUSTRIAL/i.test(cover))fail('El archivo no corresponde al IMAI.');
 const publication=cover.match(/(\d{1,2})\s+de\s+(\p{L}+)\s+de\s+(\d{4})/iu);
 const reference=cover.match(/\ben\s+(\p{L}+)\s+de\s+(\d{4})/iu);
 if(!publication||!reference)fail('No se identificaron la fecha declarada y el periodo del boletín.');
 const month=MONTHS.indexOf(reference[1].toLowerCase())+1,year=Number(reference[2]);
 const pm=MONTHS.indexOf(publication[2].toLowerCase())+1,py=Number(publication[3]),pd=Number(publication[1]);
 const date=new Date(Date.UTC(py,pm-1,pd));
 if(!month||!pm||date.getUTCMonth()!==pm-1||date.getUTCDate()!==pd||year*12+month>=py*12+pm)fail('Las fechas del archivo son incompatibles.');
 const base=cover.match(/índice\s+(\d{4})\s*=\s*100/iu)?.[1];
 if(!base)fail('No se pudo identificar la base del índice.');
 if(py!==2026)fail('La fecha declarada requiere actualizar el membrete institucional de 2026.');
 const bases=new Set(pages.flatMap(p=>[...p.matchAll(/índice\s+(\d{4})\s*=\s*100/giu)].map(m=>m[1])));
 if(bases.size!==1)fail('Las bases del índice no coinciden dentro del documento.');
 if(!/independiente/i.test(pages[1])||!/Cifras preliminares/i.test(pages[3]))fail('Cambió la metodología o el estatus estadístico. Este archivo requiere revisión.');
 const adjusted=pages[1].split(/Cuadro\s+1\b/)[1]?.split(/Nota:/)[0];
 const original=pages[3].split(/Cuadro\s+2\b/)[1];
 if(!adjusted||!original||!/desestacionalizadas/i.test(adjusted)||!/CIFRAS ORIGINALES/.test(pages[3]))fail('No se identificaron los cuadros ajustado y original.');
 const periodPattern=new RegExp(`${MONTHS[month-1]}\\s+de\\s+${year}`,'i');
 if(!periodPattern.test(adjusted)||!periodPattern.test(original))fail('Los periodos de los cuadros no coinciden con la portada.');
 const rows=LABELS.map(label=>{
  const escaped=label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const pattern=label.startsWith('Generación')?escaped+'[\\s\\S]{0,400}?(-?\\d+\\.\\d+)\\s+(-?\\d+\\.\\d+)':escaped+'\\s+(-?\\d+\\.\\d+)\\s+(-?\\d+\\.\\d+)';
  const matches=[...adjusted.matchAll(new RegExp(pattern,'g'))];
  let orig=[...original.matchAll(new RegExp(pattern,'g'))];
  if(label.startsWith('Generación'))orig=orig.filter(m=>/\b22\b/.test(m[0])||/\b22\s*$/.test(original.slice(Math.max(0,m.index-8),m.index)));
  if(matches.length!==1||orig.length!==1)fail('No se pudo leer de forma inequívoca la fila '+label+'.');
  return {label,mom:Number(matches[0][1]),yoy:Number(matches[0][2]),original:Number(orig[0][1]),ytd:Number(orig[0][2]),evidenceAdjusted:matches[0][0],evidenceOriginal:orig[0][0]};
 });
 // Anclar la lectura al bloque de portada, antes del texto y de la gráfica.
 const headline=cover.split(/(?:Aumentó|Disminuyó|No (?:cambió|registró)|El Indicador Mensual)/i)[0];
 const hero=headline.match(/(?:^|\n|\s)(\d+\.\d+)\s*[▲▼]?\s*(-?\d+\.\d+)\s*%\s*[▲▼]?\s*(-?\d+\.\d+)\s*%/);
 if(!hero||Number(hero[1])<=0)fail('No se pudo leer el índice y las tasas de portada.');
 if(Math.abs(Number(hero[2])-rows[0].mom)>.00001||Math.abs(Number(hero[3])-rows[0].yoy)>.00001)fail('Las tasas de portada no coinciden con el cuadro 1.');
 return {indicator:'IMAI',ym:`${year}-${String(month).padStart(2,'0')}`,period:`${MONTHS[month-1]} de ${year}`,publicationDate:`${py}-${String(pm).padStart(2,'0')}-${String(pd).padStart(2,'0')}`,bulletin:cover.match(/BOLETÍN\s+(?:DE\s+INDICADOR|DE\s+PRENSA)\s+(\d+\s*\/\s*\d+)/i)?.[1]?.replace(/\s/g,'')||null,base,index:Number(hero[1]),rows};
}
export function narrative(f){
 const parts=f.rows.slice(1),total=f.rows[0],best=Math.max(...parts.map(r=>r.mom)),worst=Math.min(...parts.map(r=>r.yoy));
 const short=r=>r.label.startsWith('Generación')?'Energía, agua y gas':r.label;
 return {
  summary:`En ${f.period}, la actividad industrial registró una variación real mensual de ${total.mom.toFixed(1)}% y anual de ${total.yoy.toFixed(1)}%, con cifras desestacionalizadas. El índice se ubicó en ${f.index.toFixed(1)} puntos.`,
  bullets:[`Mayor variación mensual entre los componentes: ${parts.filter(r=>r.mom===best).map(short).join(' y ')}, con ${best.toFixed(1)}%.`, `Menor variación anual entre los componentes: ${parts.filter(r=>r.yoy===worst).map(short).join(' y ')}, con ${worst.toFixed(1)}%.`],
  balance:`${parts.filter(r=>r.yoy>0).length} de los cuatro componentes principales registraron variaciones anuales positivas en cifras desestacionalizadas. Este conteo no está ponderado y no mide aportaciones al total.`,
  original:`En cifras originales, la variación anual del total fue ${total.original.toFixed(1)}% y el acumulado de enero al mes de referencia fue ${total.ytd.toFixed(1)}%.`
 };
}
