import ast,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
import notas_bcmm as N
import notas_bcmm_word as V
import build_trade_notes as R
ROOT=Path(__file__).resolve().parents[1]
class PDF:
    def __init__(self,pages,words):self.pages=[SimpleNamespace(extract_text=lambda p=p:p,extract_words=lambda:words) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

def fixture(monkeypatch,key='BCMM'):
    f=json.loads((ROOT/'tests/fixtures/bcmm2026_10.json').read_text());pages=f['pages'];words=f['history_words']
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages,words));return pages,words

def test_complete_edition_nominal_flows_and_separate_balances(monkeypatch):
    fixture(monkeypatch);f=N.extract(b'fixture');assert f['period']=='Sep 26' and f['bulletin']=='638/26'
    assert len(f['pages'])==9 and len(f['rows'])==19 and len(f['history'])==9 and len(f['markets'])==7 and len(f['adjusted'])==14
    assert N.row(f,'exports')['amount']==77796.6 and N.row(f,'imports')['amount']==78402.7
    assert N.row(f,'balance')['amount']==-606.1 and N.row(f,'balance')['ytd']==9254.2 and N.row(f,'balance')['ytd_yoy'] is None
    assert f['balances'][0]['current']==1069 and f['balances'][0]['previous']==3751
    assert V.rate(f,'exports')==-2.45 and V.rate(f,'imports')==1.02 and V.rate(f,'capital')==5.19
    assert V.rate(f,'non_automotive')==-4.74 and V.rate(f,'automotive')==2.14
    assert N.row(f,'consumption_oil')['amount']==1842.9 and N.row(f,'intermediate_oil')['amount']==3314.6
    assert N.history(f,'exports')['values'][:2]==[617771,664267]
    assert f['markets'][1]['share']==84.8 and f['markets'][1]['values'][-2:]==[43.5,32.9]
    assert V.tables(f)[1][-1][2]=='—'

@pytest.mark.parametrize('case',['pages','edition','period','row','balance','market','adjusted','method','cover','months','missing_rate','status','oil','columns'])
def test_changed_source_rejected(monkeypatch,case):
    p,w=fixture(monkeypatch)
    if case=='pages':p.pop()
    elif case=='edition':p[3]=p[3].replace('638/26','999/26')
    elif case=='period':p[0]=p[0].replace('Enero-septiembre de 2026','Enero-agosto de 2026')
    elif case=='row':p[0]=p[0].replace('No automotrices 56 338.7','Automotrices 56 338.7')
    elif case=='balance':p[0]=p[0].replace('-606.1 -75.6','-906.1 -75.6')
    elif case=='market':p[2]=p[2].replace('Exportaciones no petroleras a distintos mercados','Exportaciones totales a distintos mercados')
    elif case=='adjusted':p[4]=p[4].replace('II. CIFRAS DESESTACIONALIZADAS','II. CIFRAS ORIGINALES')
    elif case=='method':p[8]=p[8].replace('X-13ARIMA-SEATS','OTRO')
    elif case=='cover':p[0]=p[0].replace('▲ 37.9 %','▲ 99.9 %')
    elif case=='months':
        for word in w:
            if word['text']=='jul.':word['text']='jun.'
    elif case=='missing_rate':p[6]=p[6].replace('5.19 % en las de bienes de capital','sin dato en las de bienes de capital')
    elif case=='status':p[0]=p[0].replace('1/ Cifras oportunas','1/ Cifras definitivas')
    elif case=='oil':p[4]=p[4].replace('3 098 mdd','3 998 mdd')
    else:
        for word in w:
            if word['text']=='627':word['x0']=425;word['x1']=435
    with pytest.raises(ValueError):N.extract(b'fixture')

def test_layout_normalizes_fallback_fonts_without_changing_template(monkeypatch,tmp_path):
    import notas_layout as L
    from docx.oxml.ns import qn
    template=ROOT/'data/source/notas_machote/_PLANTILLA_NOTAS_VISUAL.docx';before=template.read_bytes()
    monkeypatch.setattr(L.W,'fonts',lambda:None);x=L.Layout(template,tmp_path/'test.docx')
    for fonts in x.doc.styles.element.iter(qn('w:rFonts')):
        assert all(fonts.get(qn('w:'+slot))=='Noto Sans' for slot in ['ascii','hAnsi','eastAsia','cs'])
        assert not any(attr.endswith('Theme') for attr in fonts.attrib)
    assert template.read_bytes()==before

@pytest.mark.parametrize('key',['BCMM'])
def test_word_tables_all_cotejadas_including_hero(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key);d=Document()
    for data in V.tables(f):
        t=d.add_table(rows=0,cols=len(data[0]))
        for row in data:
            for c,v in zip(t.add_row().cells,row):c.text=v
    candidate=SimpleNamespace(tables=d.tables,inline_shapes=[1,2]);V.validate(f,candidate)
    candidate.tables[0].rows[1].cells[0].text='Índice 9999'
    with pytest.raises(ValueError):V.validate(f,candidate)

@pytest.mark.parametrize('key',['BCMM'])
def test_strict_source_allowlist(key):
    directory,name=N.PRODUCTS[key];url=f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{directory}/{name}2026_10.pdf'
    assert R.allowed(url,key)
    for bad in [url+'?x=evil',url+'#x',url.replace('www.inegi.org.mx','example.com'),url.replace('https:','http:'),url.replace(name+'2026','otro2026')]:assert not R.allowed(bad,key)
    assert not R.allowed(url,'EMIM')

@pytest.mark.parametrize('case',['disabled','source_error','local_pdf','pause'])
def test_publication_preserves_previous_word(monkeypatch,tmp_path,case):
    for name in ['data/indicadores.json','data/notas/estado.json','config/notas_automaticas.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    dest=tmp_path/'downloads/indicadores/BCMM/nota/BCMM_nota.docx';dest.parent.mkdir(parents=True);dest.write_bytes(b'previous-word')
    cfg=json.loads((tmp_path/'config/notas_automaticas.json').read_text())
    if case=='disabled':
        cfg['enabled']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        monkeypatch.setattr(R,'download',lambda *a:pytest.fail('No descargar cuando está pausado'))
        assert R.run('BCMM',tmp_path,True)['status']=='deshabilitada'
    elif case=='local_pdf':assert R.run('BCMM',tmp_path,True,Path('/tmp/local.pdf'))['status']=='error'
    elif case=='source_error':
        monkeypatch.setattr(R,'download',lambda *a:(_ for _ in ()).throw(ValueError('Fuente incorrecta')))
        assert R.run('BCMM',tmp_path,True)['status']=='error'
    else:
        cfg['auto_publish']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        fixture(monkeypatch,'BCMM');monkeypatch.setattr(R,'download',lambda *a:b'fixture')
        template=tmp_path/cfg['template'];template.parent.mkdir(parents=True);shutil.copyfile(ROOT/cfg['template'],template)
        for name in ['build_trade_notes.py','notas_bcmm.py','notas_bcmm_word.py','notas_layout.py','notas_word.py','build_auto_notes.py']:
            p=tmp_path/'scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
        monkeypatch.setattr(R.V,'build',lambda *a:shutil.copyfile(template,a[-1]))
        monkeypatch.setattr(R.W,'render',lambda *a:(None,[1,2]));monkeypatch.setattr(R.V,'validate',lambda *a:None)
        monkeypatch.setattr(R.A,'publish',lambda *a:pytest.fail('Publicación deshabilitada'))
        assert R.run('BCMM',tmp_path,True)['status']=='validada_sin_publicar'
    assert dest.read_bytes()==b'previous-word'

def test_workflow_python_311_compatibility():
    for name in ['build_trade_notes.py','notas_bcmm.py','notas_bcmm_word.py','notas_layout.py']:
        ast.parse((ROOT/'scripts'/name).read_text(),feature_version=(3,11))
