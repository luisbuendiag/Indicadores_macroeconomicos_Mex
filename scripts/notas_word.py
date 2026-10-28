"""Word nativo y render del piloto: plantilla de solo lectura y QA por página."""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pdfplumber
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as ALIGN
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from notas_imoam import number, paragraphs, period_text


def interval_plot(facts: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = os.environ.get('NOTES_FONT_FILE')
    if font:
        font_manager.fontManager.addfont(font)
    # No sustituciones silenciosas en gráficas institucionales.
    font_manager.findfont('Noto Sans', fallback_to_default=False)
    with plt.rc_context({'font.family':'Noto Sans','font.size':9}):
        fig,ax=plt.subplots(figsize=(6,1.15))
        lo,hi,center=[facts['values'][i]*100 for i in (4,5,3)]
        ax.errorbar(center,0,xerr=[[center-lo],[hi-center]],fmt='o',color='#10312B',ecolor='#246454',capsize=7,linewidth=2)
        ax.axvline(0,color='#999999',linestyle='--',linewidth=1)
        pad=max((hi-lo)*.15,.3);ax.set_xlim(min(lo,0)-pad,max(hi,0)+pad)
        ax.set_yticks([]);ax.set_xlabel('Variación anual estimada (%) e intervalo de confianza al 95%')
        ax.set_xticks(sorted(set([lo,0,hi])));ax.set_xticklabels([f'{v:.1f}%' for v in sorted(set([lo,0,hi]))])
        for spine in ax.spines.values():spine.set_visible(False)
        fig.tight_layout();fig.savefig(out,dpi=300,facecolor='white');plt.close(fig)


def build(facts: dict, url: str, template: Path, out: Path) -> str:
    plot=out.parent/'intervalo.png';interval_plot(facts,plot)
    doc=Document(template)
    for child in list(doc._element.body):
        if child.tag!=qn('w:sectPr'):doc._element.body.remove(child)
    # Formato base sin depender del estilo del texto de muestra de la plantilla.
    for name in ('Normal','Title','Heading 1'):
        s=doc.styles[name];s.font.name='Noto Sans';s.font.size=Pt(11)
        p=s.paragraph_format;p.space_before=Pt(0);p.space_after=Pt(0);p.line_spacing=1
    settings=doc.settings.element
    for n in settings.findall('.//'+qn('w:useFELayout')):n.getparent().remove(n)
    compat=settings.find(qn('w:compat'))
    if compat is None:compat=OxmlElement('w:compat');settings.append(compat)
    for n in list(compat):
        if n.get(qn('w:name'))=='compatibilityMode':compat.remove(n)
    mode=OxmlElement('w:compatSetting');mode.set(qn('w:name'),'compatibilityMode');mode.set(qn('w:uri'),'http://schemas.microsoft.com/office/word');mode.set(qn('w:val'),'15');compat.append(mode)
    def paragraph(text,size=11,bold=False,color='000000',align=ALIGN.JUSTIFY,style=None):
        p=doc.add_paragraph(style=style);p.alignment=align
        pf=p.paragraph_format;pf.space_before=Pt(0);pf.space_after=Pt(0);pf.line_spacing=1;pf.widow_control=True
        r=p.add_run(text);r.font.name='Noto Sans';r.font.size=Pt(size);r.font.bold=bold;r.font.color.rgb=RGBColor.from_string(color)
        return p
    paragraph('',8)
    paragraph('Indicador Mensual Oportuno de la Actividad Manufacturera',12,True,'10312B',ALIGN.CENTER,'Title')
    year,month,day=map(int,facts['publication_date'].split('-'))
    from sources.inegi_bulletin import MESES_NOMBRE
    p=paragraph(f'{day} de {MESES_NOMBRE[month-1]} de {year}',11,True,'999999',ALIGN.CENTER)
    borders=OxmlElement('w:pBdr');bottom=OxmlElement('w:bottom')
    for key,val in [('val','single'),('sz','8'),('space','1'),('color','246454')]:bottom.set(qn('w:'+key),val)
    borders.append(bottom);p._p.get_or_add_pPr().append(borders)
    texts=[]
    for heading,text in paragraphs(facts):
        paragraph('',6.5)
        h=paragraph(heading,11,True,'246454');h.paragraph_format.keep_with_next=True
        paragraph(text);texts.append(heading+'\n'+text)
        if heading=='Incertidumbre de la estimación':
            p=doc.add_paragraph();p.alignment=ALIGN.CENTER;p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
            p.add_run().add_picture(str(plot),width=Inches(5.65))
    paragraph('',6.5)
    for source in [f'Fuente: INEGI. Boletín {facts["bulletin"] or "IMOAM"}. Periodo de referencia: {period_text(facts["ym"])}.',url]:
        p=paragraph(source,8,False,'666666');p.runs[0].italic=True
    doc.core_properties.title='IMOAM — '+period_text(facts['ym'])
    doc.core_properties.subject='Nota económica ejecutiva basada en boletín oficial INEGI'
    doc.save(out)
    return '\n\n'.join(texts)


def binary(name: str, env: str) -> str:
    path=os.environ.get(env) or shutil.which(name)
    if not path:raise RuntimeError(f'Falta herramienta de render: {name}')
    return path


def raster(pdf: Path, prefix: Path, dpi=120) -> list[Path]:
    subprocess.run([binary('pdftoppm','NOTES_PDFTOPPM'),'-r',str(dpi),'-png',str(pdf),str(prefix)],check=True,capture_output=True,timeout=120)
    pages=sorted(prefix.parent.glob(prefix.name+'-*.png'))
    if not pages:raise ValueError('Render sin imágenes')
    return pages


def render(docx: Path, max_pages=2) -> tuple[Path,list[Path]]:
    docx.with_suffix('.pdf').unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='notes-lo-') as profile:
        subprocess.run([binary('soffice','NOTES_SOFFICE'),'-env:UserInstallation='+Path(profile).as_uri(),'--headless','--convert-to','pdf','--outdir',str(docx.parent),str(docx)],check=True,capture_output=True,timeout=120)
    pdf=docx.with_suffix('.pdf')
    if not pdf.exists():raise ValueError('No se generó el PDF de revisión')
    with pdfplumber.open(pdf) as d:
        if not 1<=len(d.pages)<=max_pages:raise ValueError('Extensión de la nota fuera del límite')
        for page in d.pages:
            if len(page.extract_text() or '')<100:raise ValueError('Página vacía o ilegible')
            if any(c['x0']<0 or c['x1']>page.width+1 or c['top']<0 or c['bottom']>page.height+1 for c in page.chars):
                raise ValueError('Texto fuera de la página')
        fonts={c['fontname'] for pg in d.pages for c in pg.chars if c['text'].strip()}
        if not any('NotoSans' in n.replace('-','') for n in fonts):
            raise ValueError('Render sin Noto Sans; revisar fuentes instaladas')
    return pdf,raster(pdf,docx.parent/'nota-pagina')
