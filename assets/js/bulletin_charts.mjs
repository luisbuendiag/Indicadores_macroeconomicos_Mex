// Gráficas locales; ninguna imagen ni cifra se envía a servicios externos.
export function drawComponentChart(canvas,facts,field){
 const rows=facts.rows.slice(1),ctx=canvas.getContext('2d');canvas.width=1840;canvas.height=590;
 ctx.fillStyle='#FFFFFF';ctx.fillRect(0,0,1840,590);
 const values=rows.map(r=>r[field]),low=Math.min(0,...values),high=Math.max(0,...values),span=Math.max(high-low,1);
 const min=low-span*.16,max=high+span*.18,x0=590,x1=1745,y0=140,y1=440,x=v=>x0+(v-min)/(max-min)*(x1-x0);
 ctx.font='600 42px "Noto Sans"';ctx.fillStyle='#10312B';ctx.textAlign='center';
 ctx.fillText(field==='mom'?'Variación mensual desestacionalizada':'Variación anual desestacionalizada',920,58);
 ctx.font='30px "Noto Sans"';ctx.textBaseline='middle';
 for(let i=0;i<5;i++){
  const v=min+(max-min)*i/4,xx=x(v);ctx.strokeStyle='#E4E8E5';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(xx,y0-30);ctx.lineTo(xx,y1+35);ctx.stroke();
  ctx.fillStyle='#4C5650';ctx.fillText(v.toFixed(1)+'%',xx,505);
 }
 ctx.strokeStyle='#67756C';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x(0),y0-30);ctx.lineTo(x(0),y1+35);ctx.stroke();
 rows.forEach((r,i)=>{
  const yy=y0+i*100,label=r.label.startsWith('Generación')?'Energía, agua y gas':r.label;
  ctx.textAlign='right';ctx.fillStyle='#161A1D';ctx.font='34px "Noto Sans"';ctx.fillText(label,x0-30,yy);
  const xx=x(r[field]),zero=x(0);ctx.fillStyle=r[field]>=0?'#246454':'#9B2247';ctx.fillRect(Math.min(xx,zero),yy-22,Math.max(Math.abs(xx-zero),2),44);
  ctx.fillStyle='#161A1D';ctx.textAlign=r[field]>=0?'left':'right';ctx.font='600 32px "Noto Sans"';ctx.fillText(r[field].toFixed(1)+'%',xx+(r[field]>=0?12:-12),yy);
 });
 ctx.textAlign='center';ctx.font='30px "Noto Sans"';ctx.fillStyle='#4C5650';ctx.fillText('Variación real (%)',1160,565);
}
export async function chartBytes(canvas){const b=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!b)throw new Error('No se pudo generar la gráfica.');return new Uint8Array(await b.arrayBuffer());}
