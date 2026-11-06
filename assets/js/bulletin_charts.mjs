import {selectedSectors} from './bulletin_parsers.mjs';
// Gráficas locales; ninguna imagen ni cifra se envía a servicios externos.
export function drawComponentChart(canvas,facts,field){
 const rows=facts.chartRows||facts.rows.slice(1),ctx=canvas.getContext('2d');canvas.width=1840;canvas.height=590;
 ctx.fillStyle='#FFFFFF';ctx.fillRect(0,0,1840,590);
 const values=rows.map(r=>r[field]),low=Math.min(0,...values),high=Math.max(0,...values),span=Math.max(high-low,1);
 const min=low-span*.16,max=high+span*.18,x0=590,x1=1745,y0=140,y1=440,x=v=>x0+(v-min)/(max-min)*(x1-x0);
 ctx.font='600 42px "Noto Sans"';ctx.fillStyle='#10312B';ctx.textAlign='center';
 ctx.fillText(facts.chartTitle||(field==='mom'?'Variación mensual desestacionalizada':'Variación anual desestacionalizada'),920,58);
 ctx.font='30px "Noto Sans"';ctx.textBaseline='middle';
 for(let i=0;i<5;i++){
  const v=min+(max-min)*i/4,xx=x(v);ctx.strokeStyle='#E4E8E5';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(xx,y0-30);ctx.lineTo(xx,y1+35);ctx.stroke();
  ctx.fillStyle='#4C5650';ctx.fillText(v.toFixed(1)+'%',xx,505);
 }
 ctx.strokeStyle='#67756C';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x(0),y0-30);ctx.lineTo(x(0),y1+35);ctx.stroke();
 rows.forEach((r,i)=>{
  const yy=y0+i*(300/Math.max(rows.length-1,1)),label=r.label.startsWith('Generación')?'Energía, agua y gas':r.label;
  ctx.textAlign='right';ctx.fillStyle='#161A1D';ctx.font='32px "Noto Sans"';ctx.fillText(label,x0-30,yy);
  const xx=x(r[field]),zero=x(0);ctx.fillStyle=r[field]>=0?'#246454':'#9B2247';ctx.fillRect(Math.min(xx,zero),yy-22,Math.max(Math.abs(xx-zero),2),44);
  ctx.fillStyle='#161A1D';ctx.textAlign=r[field]>=0?'left':'right';ctx.font='600 32px "Noto Sans"';ctx.fillText(r[field].toFixed(1)+'%',xx+(r[field]>=0?12:-12),yy);
 });
 ctx.textAlign='center';ctx.font='30px "Noto Sans"';ctx.fillStyle='#4C5650';ctx.fillText(facts.chartAxis||'Variación real (%)',1160,565);
}
export async function chartBytes(canvas){const b=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!b)throw new Error('No se pudo generar la gráfica.');return new Uint8Array(await b.arrayBuffer());}

export function drawNoteChart(canvas,f,field){
 if(f.indicator==='IMOAM')return intervalChart(canvas,f,field);
 if(f.indicator==='EMIM'){
  const rows=field==='mom'?f.rows:selectedSectors(f).map(r=>({...r,yoy:r.production}));
  return drawComponentChart(canvas,{...f,chartRows:rows,chartAxis:field==='mom'?'Variación mensual (%)':'Variación real anual (%)',chartTitle:field==='mom'?'Indicadores manufactureros · cifras desestacionalizadas':'Producción por subsector · cifras originales'},field);
 }
 return drawComponentChart(canvas,f,field);
}
function intervalChart(canvas,f,field){
 const annual=field==='yoy',[point,low,high]=annual?f.annualInterval:f.indexInterval,suffix=annual?'%':'',ctx=canvas.getContext('2d');canvas.width=1840;canvas.height=590;
 const span=Math.max(high-low,1),min=Math.min(low,annual?0:low)-span*.2,max=high+span*.2,x=v=>190+(v-min)/(max-min)*1460;
 ctx.fillStyle='#fff';ctx.fillRect(0,0,1840,590);ctx.fillStyle='#10312B';ctx.font='600 42px "Noto Sans"';ctx.textAlign='center';ctx.fillText(annual?'Variación anual estimada e IC al 95%':'Índice estimado e IC al 95%',920,65);
 ctx.font='30px "Noto Sans"';for(let i=0;i<5;i++){const v=min+(max-min)*i/4;ctx.strokeStyle='#e4e8e5';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x(v),170);ctx.lineTo(x(v),380);ctx.stroke();ctx.fillStyle='#4c5650';ctx.fillText(v.toFixed(1)+suffix,x(v),440);}
 if(annual){ctx.strokeStyle='#67756c';ctx.beginPath();ctx.moveTo(x(0),150);ctx.lineTo(x(0),390);ctx.stroke();}
 ctx.strokeStyle='#246454';ctx.lineWidth=12;ctx.beginPath();ctx.moveTo(x(low),270);ctx.lineTo(x(high),270);ctx.stroke();
 ctx.lineWidth=5;for(const v of [low,high]){ctx.beginPath();ctx.moveTo(x(v),245);ctx.lineTo(x(v),295);ctx.stroke();ctx.fillStyle='#161a1d';ctx.fillText(v.toFixed(1)+suffix,x(v),205);}
 ctx.beginPath();ctx.arc(x(point),270,14,0,2*Math.PI);ctx.fillStyle='#9b2247';ctx.fill();ctx.font='600 36px "Noto Sans"';ctx.fillText(point.toFixed(1)+suffix,x(point),350);
 ctx.font='30px "Noto Sans"';ctx.fillStyle='#4c5650';ctx.fillText(annual?'Variación anual estimada (%)':'Puntos del índice'+(f.base?' · base '+f.base+'=100':''),920,530);
}
