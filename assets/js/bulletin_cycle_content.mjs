import {currentIoae,intervalText,periodText} from './bulletin_cycles.mjs';
const short=r=>r.id==='total'?'IGAE':r.label.replace('Actividades ','').replace(/^./,s=>s.toUpperCase());
const signed=(v,d=2)=>(v>0?'+':'')+v.toFixed(d);
const range=v=>v.low<0&&v.high>0?'incluye disminuciones y aumentos':v.low<=0&&v.high>=0?'incluye la ausencia de cambio':v.low>0?'se encuentra por encima de cero':'se encuentra por debajo de cero';
const position=g=>g.level>100?'por arriba de la tendencia de largo plazo':g.level<100?'por debajo de la tendencia de largo plazo':'en torno a la referencia de tendencia, al redondeo publicado';
export function cycleBody(f,{title,table,h,p,note,image,gap,source}){
 if(f.indicator==='SIC'){
  const [c,a]=f.groups;
  let b=title(f)+table([['Indicador y periodo','Nivel y cambio mensual'],...f.groups.map(g=>[`${g.name} · ${g.period}`,`${g.level.toFixed(1)} puntos · ${signed(g.delta)} puntos`])],[4419,4419]);
  b+=h('Resumen ejecutivo')+p(`En ${c.period}, el Coincidente se ubicó en ${c.level.toFixed(1)} puntos, ${position(c)}, con un cambio mensual de ${signed(c.delta)} puntos.`);
  b+=p(`En ${a.period}, el Adelantado registró ${a.level.toFixed(1)} puntos y un cambio mensual de ${signed(a.delta)} puntos; se ubicó ${position(a)}.`,{list:true});

  for(let i=0;i<2;i++){
   const g=f.groups[i],positive=g.components.filter(r=>r.delta>0).length,negative=g.components.filter(r=>r.delta<0).length;
   b+=h(`Componentes del ${g.name} en ${g.period}`)+table([['Componente cíclico','Cambio (puntos)','Relación'],...g.components.map(r=>[r.label,signed(r.delta),r.inverse?'Inversa':'Directa'])],[4900,2138,1800]);
   b+=source(f,`Cuadro ${i+1}, página ${i?6:3}. Cambios de componentes cíclicos; se conserva el signo publicado.`);
   b+=gap()+image(i?'uploadYoy':'uploadMom',i?902:901)+note('Doce diferencias mensuales publicadas; no son niveles del indicador.');
   b+=p(`${positive} componentes aumentaron, ${negative} disminuyeron y ${6-positive-negative} no cambiaron al redondeo publicado. Es un conteo de signos, sin ponderación; no mide contribuciones.`,{list:true});
  }
  b+=h('Lectura de la posición cíclica')+p('Los cambios se expresan en puntos, no en tasas de crecimiento del PIB. El Coincidente refleja el estado general de la economía; el Adelantado busca anticipar sus puntos de giro. La posición respecto a 100 y el cambio mensual se leen conjuntamente. Cruzar 100 no determina por sí solo una recesión.');
  b+=h('Notas y fuente')+note('Desocupación urbana, tipo de cambio real y TIIE tienen relación inversa con la actividad. Las diferencias de sus componentes cíclicos no son cambios de las variables originales ni rendimientos financieros. Las trayectorias pueden revisarse con nueva información.')+source(f,'Cuadros 1–2, páginas 3 y 6; interpretación, páginas 9–12; metodología, página 13. Series ajustadas, filtro Hodrick-Prescott y estandarización.',true);return b;
 }
 const rows=currentIoae(f),t=rows[0],prior=f.rows.filter(r=>r.ym!==f.ym);
 let b=title(f)+table([['Periodo estimado','Fecha del boletín'],[f.period,f.publicationDate]],[4419,4419]);
 b+=h('Resumen ejecutivo')+p(`Para ${f.period}, el IOAE estima una variación real del IGAE de ${t.yoy.point.toFixed(1)}% anual y ${t.mom.point.toFixed(1)}% mensual, con cifras desestacionalizadas.`);
 b+=p(`El intervalo anual del total es ${intervalText(t.yoy)}% y ${range(t.yoy)}. El mensual es ${intervalText(t.mom)}% y ${range(t.mom)}.`,{list:true});
 for(const [field,label,id,n] of [['yoy','Anual','uploadYoy',902],['mom','Mensual','uploadMom',901]]){
  b+=h(`Comparación ${label.toLowerCase()} del mes estimado`)+table([['Actividad',`${label} (%)`,'IC 95% (%)'],...rows.map(r=>[short(r),r[field].point.toFixed(1),intervalText(r[field])])],[4050,2250,2538]);
  b+=gap()+image(id,n,1550000)+source(f,`Cuadro ${field==='yoy'?1:2}, página ${field==='yoy'?1:2}. Punto: estimación. Segmento: intervalo de confianza al 95%.`);
 }
 b+=h('Nivel estimado de actividad')+table([['Actividad','Índice estimado','IC 95% (puntos)'],...rows.map(r=>[short(r),r.index.point.toFixed(1),intervalText(r.index)])],[4050,2250,2538])+note(`Cuadro 3, página 2. Índice base ${f.base}=100, desestacionalizado; los intervalos están en puntos del índice.`);
 b+=h(`Mes previo en la misma edición ${periodText(prior[0].ym)}`)+table([['Actividad y condición','Anual (%)','Mensual (%)'],...prior.map(r=>[`${short(r)} · ${r.status}`,r.yoy.point.toFixed(1),r.mom.point.toFixed(1)])],[5250,1794,1794]);
 b+=h('Alcance y fuente')+p('El IOAE no reemplaza el cálculo tradicional del IGAE. El total se estima de forma independiente de sus componentes: las tasas sectoriales no se suman ni se promedian. El dato previo de secundarias es observado según el IMAI y no tiene intervalo publicado; no se sustituye por cero.')+note('Los intervalos describen incertidumbre de cada estimación; no prueban por sí solos diferencias significativas entre sectores. Anual compara con el mismo mes del año anterior; mensual, con el mes inmediato previo.')+source(f,'Cuadros 1–3, páginas 1–2; gráficas, páginas 3–5; metodología, página 6.',true);return b;
}
