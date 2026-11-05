// Native OOXML tables, packaged as a DOCX in the browser. No remote service.
const enc = new TextEncoder();
const NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const months = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const xml = (v) => String(v ?? '').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const safeUrl = u => /^https?:\/\//i.test(u || '') ? u : '';
function run(text, bold = false, size = 18, color = '161A1D') {
  return `<w:r><w:rPr><w:rFonts w:ascii="Noto Sans" w:hAnsi="Noto Sans"/><w:sz w:val="${size}"/><w:color w:val="${color}"/>${bold ? '<w:b/>' : ''}</w:rPr><w:t xml:space="preserve">${xml(text)}</w:t></w:r>`;
}
function p(text, opts = {}) {
  return `<w:p><w:pPr>${opts.style ? `<w:pStyle w:val="${opts.style}"/>` : ''}<w:spacing w:before="0" w:after="${opts.after ?? 55}"/>${opts.keep ? '<w:keepNext/>' : ''}</w:pPr>${run(text, opts.bold, opts.size, opts.color)}</w:p>`;
}
function cell(content, width, fill = 'FFFFFF') {
  return `<w:tc><w:tcPr><w:tcW w:w="${width}" w:type="dxa"/><w:shd w:fill="${fill}"/><w:vAlign w:val="top"/></w:tcPr>${content || p('')}</w:tc>`;
}
function table(rows, widths, compact = false) {
  const borders = ['top','left','bottom','right','insideH','insideV'].map(s => `<w:${s} w:val="single" w:sz="4" w:color="D9D9D9"/>`).join('');
  return `<w:tbl><w:tblPr><w:tblW w:w="${widths.reduce((a,b)=>a+b,0)}" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>${borders}</w:tblBorders><w:tblCellMar><w:top w:w="65" w:type="dxa"/><w:left w:w="65" w:type="dxa"/><w:bottom w:w="65" w:type="dxa"/><w:right w:w="65" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${widths.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.map((r,i)=>`<w:tr><w:trPr>${i===0?'<w:tblHeader/>':''}<w:cantSplit/></w:trPr>${r.map((c,j)=>cell(c,widths[j],i===0?'1E5B4F':i%2?'FFFFFF':'F5F7F6')).join('')}</w:tr>`).join('')}</w:tbl>`;
}

// Store-only ZIP, with CRC32 and UTF-8 filenames; deliberately dependency-free.
function crc32(bytes) {
  let crc = -1;
  for (const b of bytes) { crc ^= b; for(let k=0;k<8;k++) crc=(crc>>>1)^((crc&1)?0xedb88320:0); }
  return (crc^-1)>>>0;
}
export function zipFiles(files) {
  const chunks = [], central = []; let offset = 0, centralSize = 0;
  const header = (n) => {const bytes=new Uint8Array(n); return [bytes,new DataView(bytes.buffer)];};
  for(const [name, text] of Object.entries(files)) {
    const filename=enc.encode(name), data=enc.encode(text), crc=crc32(data);
    const [local,v]=header(30); v.setUint32(0,0x04034b50,true); v.setUint16(4,20,true); v.setUint16(6,0x800,true); v.setUint16(12,33,true);
    v.setUint32(14,crc,true); v.setUint32(18,data.length,true); v.setUint32(22,data.length,true); v.setUint16(26,filename.length,true);
    chunks.push(local,filename,data);
    const [dir,d]=header(46); d.setUint32(0,0x02014b50,true); d.setUint16(4,20,true); d.setUint16(6,20,true); d.setUint16(8,0x800,true); d.setUint16(14,33,true);
    d.setUint32(16,crc,true); d.setUint32(20,data.length,true); d.setUint32(24,data.length,true); d.setUint16(28,filename.length,true); d.setUint32(42,offset,true);
    central.push(dir,filename); centralSize += 46+filename.length; offset+=30+filename.length+data.length;
  }
  const [end,e]=header(22); e.setUint32(0,0x06054b50,true); e.setUint16(8,Object.keys(files).length,true); e.setUint16(10,Object.keys(files).length,true); e.setUint32(12,centralSize,true); e.setUint32(16,offset,true);
  const all=[...chunks,...central,end], output=new Uint8Array(offset+centralSize+22); let at=0;
  for(const chunk of all) {output.set(chunk,at);at+=chunk.length;} return output;
}

export function calendarDocx({events, year, month, count = 1, asOf = '', filters = 'Todos los indicadores'}) {
  const relations = []; let body = '';
  const link = (label,url) => {
    if(!safeUrl(url)) return p(label);
    const id=`rIdLink${relations.length+1}`; relations.push(`<Relationship Id="${id}" Type="${REL}/hyperlink" Target="${xml(url)}" TargetMode="External"/>`);
    return `<w:p><w:pPr><w:spacing w:after="0"/></w:pPr><w:hyperlink r:id="${id}">${run(label,false,17,'1E5B4F')}</w:hyperlink></w:p>`;
  };
  for(let i=0;i<count;i++) {
    const start=new Date(year,month-1+i,1), y=start.getFullYear(), m=start.getMonth()+1;
    const prefix=`${y}-${String(m).padStart(2,'0')}`;
    const items=events.filter(e=>(e.fecha_iso||'').slice(0,7)===prefix).sort((a,b)=>a.fecha_iso.localeCompare(b.fecha_iso)||a.clave.localeCompare(b.clave));
    const title=`${months[m-1][0].toUpperCase()+months[m-1].slice(1)} de ${y}`;
    if(i) body+='<w:p><w:r><w:br w:type="page"/></w:r></w:p>';
    body+=p('Calendario de publicaciones económicas',{style:'Title',bold:true,size:30,after:90})+p(title,{bold:true,size:24,after:80});
    body+=p(`Corte del calendario: ${asOf}  |  ${items.length} publicaciones`,{size:17})+p(`Selección: ${filters}`,{size:17,after:100});
    const rows=[['LUN','MAR','MIÉ','JUE','VIE','SÁB','DOM'].map(s=>p(s,{bold:true,color:'FFFFFF'}))];
    const days=new Date(y,m,0).getDate(), first=(start.getDay()+6)%7;
    for(let day=1-first;day<=days;day+=7) {
      rows.push(Array.from({length:7},(_,j)=>{
        const n=day+j; if(n<1||n>days) return p('');
        const on=items.filter(e=>Number(e.fecha_iso.slice(-2))===n);
        return p(String(n),{bold:true,size:18})+on.map(e=>p(e.sigla||e.clave,{bold:true,size:16,color:'1E5B4F'})+p(e.periodo_referencia||e.frecuencia,{size:15})).join('');
      }));
    }
    body+=table(rows,Array(7).fill(1954));
    body+=p('Las fechas programadas pueden cambiar. La disponibilidad del boletín y de la nota se verifica por separado.',{size:16,after:50});
    body+='<w:p><w:r><w:br w:type="page"/></w:r></w:p>';
    body+=p(`Detalle de publicaciones ${title}`,{bold:true,size:24,after:80})+p(`Selección: ${filters}  |  Corte: ${asOf}`,{size:17,after:100});
    const detail=[['Fecha','Indicador y producto','Periodo de referencia','Frecuencia','Fuente y situación'].map(s=>p(s,{bold:true,color:'FFFFFF'}))];
    for(const e of items) detail.push([
      p(e.fecha_iso.split("-").reverse().join("/"),{size:18,after:0}),
      p(`${e.sigla||e.clave} · ${e.nombre_corto||e.producto||e.indicador}`,{size:18,after:0}),
      p(e.periodo_referencia||'Por determinar',{size:18,after:0}),
      p(e.frecuencia === "Decisiones de política monetaria" ? "Por decisión" : e.frecuencia,{size:18,after:0}),
      link(`${(e.source||e.institucion||"").includes("INEGI") ? "INEGI" : /Banco|Banxico/.test(e.institucion||e.source) ? "Banxico" : "SE"} · ${(e.situacion||"Programada").startsWith("Fecha transcurrida") ? "Fecha transcurrida" : (e.situacion||"Programada")}`,e.url_boletin)
    ]);
    if(items.length) body+=table(detail,[1400,4900,2400,1450,3528],true);
    else body+=p('Sin publicaciones registradas para esta selección.');
  }
  const sect='<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/><w:pgMar w:top="600" w:right="1080" w:bottom="650" w:left="1080" w:header="240" w:footer="260"/></w:sectPr>';
  const document=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${NS}" xmlns:r="${REL}"><w:body>${body}${sect}</w:body></w:document>`;
  const contentTypes=`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>`;
  return zipFiles({
    '[Content_Types].xml':contentTypes,
    '_rels/.rels':`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${REL}/officeDocument" Target="word/document.xml"/></Relationships>`,
    'word/document.xml':document,
    'word/_rels/document.xml.rels':`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdStyles" Type="${REL}/styles" Target="styles.xml"/><Relationship Id="rIdFooter" Type="${REL}/footer" Target="footer1.xml"/>${relations.join('')}</Relationships>`,
    'word/styles.xml':`<w:styles xmlns:w="${NS}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Noto Sans" w:hAnsi="Noto Sans"/><w:sz w:val="18"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="50" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/></w:pPr></w:style></w:styles>`,
    'word/footer1.xml':`<w:ftr xmlns:w="${NS}">${p('Secretaría de Economía  |  Agenda de indicadores macroeconómicos',{size:16,color:'666666'})}<w:p><w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t>Página </w:t></w:r><w:fldSimple w:instr="PAGE"/></w:p></w:ftr>`
  });
}

export function downloadCalendar(options, filename) {
  const blob=new Blob([calendarDocx(options)],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});
  const url=URL.createObjectURL(blob), a=document.createElement('a'); a.href=url; a.download=filename;
  document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),30000);
}
