import {unzipSync,zipSync,strFromU8,strToU8} from '../vendor/fflate/fflate.mjs';
import {narrative} from './bulletin_imai.mjs';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const r=(s,{size=22,bold=false,color='000000',italic=false}={})=>`<w:r><w:rPr><w:rFonts w:ascii="Noto Sans" w:hAnsi="Noto Sans" w:cs="Noto Sans"/><w:sz w:val="${size}"/><w:szCs w:val="${size}"/><w:color w:val="${color}"/>${bold?'<w:b/>':''}${italic?'<w:i/>':''}</w:rPr><w:t xml:space="preserve">${esc(s)}</w:t></w:r>`;
const p=(s,opts={})=>`<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="${opts.center?'center':'both'}"/><w:widowControl/>${opts.keep?'<w:keepNext/>':''}${opts.list?'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="997"/></w:numPr>':''}</w:pPr>${r(s,opts)}</w:p>`;
const gap=()=>p('',{size:13});
const h=s=>gap()+p(s,{bold:true,color:'246454',keep:true});
const note=s=>p(s,{size:16,color:'666666',italic:true});
function table(rows,widths){
 const cell=(v,i,j)=>`<w:tc><w:tcPr><w:tcW w:w="${widths[j]}" w:type="dxa"/><w:vAlign w:val="center"/><w:shd w:fill="${i===0?'10312B':i%2===0?'F2F2F2':'FFFFFF'}"/></w:tcPr>${p(v,{size:21,bold:i===0||j===0,color:i===0?'FFFFFF':'000000',center:j>0,keep:i<rows.length-1})}</w:tc>`;
 const edges=['top','left','bottom','right','insideH','insideV'].map(x=>`<w:${x} w:val="single" w:sz="4" w:color="D9D9D9"/>`).join('');
 return `<w:tbl><w:tblPr><w:tblW w:w="${widths.reduce((a,b)=>a+b,0)}" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>${edges}</w:tblBorders><w:tblCellMar><w:top w:w="65" w:type="dxa"/><w:left w:w="85" w:type="dxa"/><w:bottom w:w="65" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${widths.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.map((row,i)=>`<w:tr><w:trPr><w:cantSplit/>${i===0?'<w:tblHeader/>':''}</w:trPr>${row.map((v,j)=>cell(v,i,j)).join('')}</w:tr>`).join('')}</w:tbl>`;
}
function image(id,n){
 const cx=5610000,cy=1800000;
 return `<w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${n}" name="Gráfica ${n}" descr="Variaciones de los componentes del IMAI"/><wp:cNvGraphicFramePr/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="${id}.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`;
}
export function buildDocx(f,template,pngs){
 const files=unzipSync(template),xml=strFromU8(files['word/document.xml']);
 const section=xml.match(/<w:sectPr\b[\s\S]*?<\/w:sectPr>/)?.[0];
 if(!section||!files['word/header1.xml']||!pngs.mom||!pngs.yoy)throw new Error('No se pudo preparar el formato institucional.');
 const texts=narrative(f),short=r=>r.label.startsWith('Generación')?'Energía, agua y gas':r.label;
 const total=f.rows[0];
 let body=p('',{size:16})+p('Indicador Mensual de la Actividad Industrial',{size:24,bold:true,color:'10312B',center:true});
 body+=table([['Periodo de referencia','Fecha declarada en el boletín'],[f.period,f.publicationDate],['Índice desestacionalizado',`Mensual ${total.mom.toFixed(1)}%   Anual ${total.yoy.toFixed(1)}%`],[`${f.index.toFixed(1)} puntos · base ${f.base}=100`,'Versión recibida · documento de trabajo']],[4419,4419]);
 body+=h('Resumen ejecutivo')+p(texts.summary)+texts.bullets.map(t=>p(t,{list:true})).join('');
 body+=h('Cifras desestacionalizadas')+table([['Actividad','Mensual (%)','Anual (%)'],...f.rows.map(row=>[short(row),row.mom.toFixed(1),row.yoy.toFixed(1)])],[5250,1794,1794]);
 body+=note('Fuente: cuadro 1, página 2 del archivo recibido. Variaciones reales; los componentes se ajustan de manera independiente.');
 body+=gap()+image('uploadMom',901)+note('Comparación respecto al mes inmediato anterior. Las barras muestran tasas, no contribuciones al total.');
 body+=h('Cifras originales y acumulado del año')+table([['Actividad','Anual (%)','Enero–mes (%)'],...f.rows.map(row=>[short(row),row.original.toFixed(1),row.ytd.toFixed(1)])],[5250,1794,1794]);
 body+=note('Fuente: cuadro 2, página 4 del archivo recibido. Cifras preliminares. El acumulado compara enero al mes de referencia con el mismo intervalo del año anterior.');
 body+=h('Balance anual por actividad')+image('uploadYoy',902)+note('Comparación con el mismo mes del año anterior, cifras desestacionalizadas.');
 body+=h('Lectura de conjunto')+p(texts.balance,{list:true})+p(texts.original,{list:true});
 body+=h('Notas y fuente')+p('El IMAI comprende minería, energía, agua y gas, construcción y manufacturas. Las tasas de sus componentes no se suman ni se promedian para reconstruir el total. Las cifras originales y desestacionalizadas se presentan por separado.');
 body+=note(`Fuente: documento recibido identificado como boletín IMAI del INEGI${f.bulletin?' '+f.bulletin:''}, con fecha declarada ${f.publicationDate}. Resultados: páginas 1–2; cifras originales: página 4; metodología: página 5. La nota no acredita su publicación oficial.`);
 files['word/document.xml']=strToU8(xml.replace(/<w:body>[\s\S]*<\/w:body>/,`<w:body>${body}${section}</w:body>`));
 let rels=strFromU8(files['word/_rels/document.xml.rels']);
 for(const [id,bytes] of [['uploadMom',pngs.mom],['uploadYoy',pngs.yoy]]){
  files[`word/media/${id}.png`]=bytes;rels=rels.replace('</Relationships>',`<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${id}.png"/></Relationships>`);
 }
 files['word/_rels/document.xml.rels']=strToU8(rels);
 let types=strFromU8(files['[Content_Types].xml']);
 if(!/Extension="png"/.test(types))types=types.replace('</Types>','<Default Extension="png" ContentType="image/png"/></Types>');
 files['[Content_Types].xml']=strToU8(types);
 const numbering=strFromU8(files['word/numbering.xml']);
 files['word/numbering.xml']=strToU8(numbering.replace('</w:numbering>','<w:abstractNum w:abstractNumId="997"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="360"/></w:tabs><w:ind w:left="360" w:hanging="180"/></w:pPr><w:rPr><w:rFonts w:ascii="Noto Sans" w:hAnsi="Noto Sans"/></w:rPr></w:lvl></w:abstractNum><w:num w:numId="997"><w:abstractNumId w:val="997"/></w:num></w:numbering>'));
 // La plantilla aporta solo formato y membrete. No heredar autores ni rutas locales.
 files['docProps/core.xml']=strToU8('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>IMAI '+esc(f.period)+'</dc:title><dc:description>Nota de trabajo a partir del archivo recibido</dc:description></cp:coreProperties>');
 return zipSync(files,{level:6});
}
