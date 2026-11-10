"""Histórico estatal acumulado RNIE; el corte procede de celdas, no del nombre."""
import argparse,hashlib,io,json,math,re,urllib.request
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse
import openpyxl
ROOT=Path(__file__).resolve().parents[1]
PAGE='https://www.gob.mx/se/acciones-y-programas/competitividad-y-normatividad-inversion-extranjera-directa'
URL='https://www.gob.mx/cms/uploads/attachment/file/1100602/2026_2T_Flujos_EF_AC_5.xlsx'
STATES=['Aguascalientes','Baja California','Baja California Sur','Campeche','Chiapas','Chihuahua','Ciudad de México','Coahuila de Zaragoza','Colima','Durango','Guanajuato','Guerrero','Hidalgo','Jalisco','Estado de México','Michoacán de Ocampo','Morelos','Nayarit','Nuevo León','Oaxaca','Puebla','Querétaro','Quintana Roo','San Luis Potosí','Sinaloa','Sonora','Tabasco','Tamaulipas','Tlaxcala','Veracruz de Ignacio de la Llave','Yucatán','Zacatecas']
def num(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def parse(content,url=URL):
 w=openpyxl.load_workbook(io.BytesIO(content),read_only=True,data_only=True)
 try:
  s=w['EF por Tipo de Inversión'];rows=list(s.values)
  if 'acumulados desde el inicio' not in str(rows[0][0]) or 'millones de dólares' not in str(rows[0][0]) or 'cifras actualizadas' not in str(rows[0][0]):raise ValueError('Concepto o unidad no reconocido')
  found={str(r[0]).strip():r for r in rows[5:] if str(r[0]).strip() in STATES}
  if len(found)!=32:raise ValueError('Faltan entidades')
  if sum(str(r[0]).strip() in STATES for r in rows[5:])!=32:raise ValueError('Entidades duplicadas')
  periods=[];year=None
  for c in range(1,len(rows[3])):
   if isinstance(rows[2][c],(int,float)):year=int(rows[2][c])
   q=rows[3][c]
   if not year or q not in (1,2,3,4):raise ValueError('Encabezado no reconocido')
   values={state:found[state][c] for state in STATES};total=rows[4][c]
   if not num(total) or any(not num(v) for v in values.values()):raise ValueError('Totales estatales incompletos o confidenciales')
   if abs(sum(values.values())-total)>0.05:raise ValueError('Los estados no concilian con el total')
   periods.append(dict(year=year,quarter=int(q),period=f'{int(q)}T-{year}',label=f'Ene-{["Mar","Jun","Sep","Dic"][int(q)-1]} {year}',total=total,values=values))
  keys=[(r['year'],r['quarter']) for r in periods]
  if keys!=sorted(set(keys)):raise ValueError('Periodos duplicados o desordenados')
  return dict(source_url=url,source_page=PAGE,source_sha256=hashlib.sha256(content).hexdigest(),unit='Millones de dólares corrientes',basis='Acumulado desde enero, cifras actualizadas',periods=periods)
 finally:w.close()
def ranking(data):
 last=data['periods'][-1];prior=next((r for r in data['periods'] if r['year']==last['year']-1 and r['quarter']==last['quarter']),None)
 def ranks(p):return {s:1+sum(v>x for v in p['values'].values()) for s,x in p['values'].items()}
 current=ranks(last);previous=ranks(prior) if prior else {}
 return dict(period=last['period'],label=last['label'],comparison=prior['label'] if prior else None,total=last['total'],rows=[dict(state=s,amount=v,share=v/last['total'] if last['total'] else None,rank=current[s],previous_rank=previous.get(s),change=previous[s]-current[s] if s in previous else None) for s,v in sorted(last['values'].items(),key=lambda r:(-r[1],r[0]))])
def allowed(url):
 u=urlparse(url);return u.scheme=='https' and u.hostname=='www.gob.mx' and u.port in (None,443) and not u.username and not u.password and not u.query and not u.fragment and (u.path==urlparse(PAGE).path or bool(re.fullmatch(r'/cms/uploads/attachment/file/\d+/[^/]*Flujos_EF_AC[^/]*\.xlsx',u.path)))
def get(url):
 if not allowed(url):raise ValueError('Fuente no permitida')
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   if not allowed(newurl):raise ValueError('Redirección no permitida')
   return super().redirect_request(req,fp,code,msg,headers,newurl)
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.build_opener(Redirect()).open(req,timeout=30) as r:
  b=r.read(40_000_001)
  if not allowed(r.url) or len(b)>40_000_000:raise ValueError('Respuesta no válida')
  return b
class Links(HTMLParser):
 def __init__(self):super().__init__();self.urls=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   u=urljoin(PAGE,dict(attrs).get('href',''))
   if allowed(u) and u.endswith('.xlsx'):self.urls.append(u)
def refresh(root=ROOT,local=None):
 path=root/'data/ied_estatal.json';old=json.loads(path.read_text()) if path.exists() else None
 now=datetime.now(timezone.utc).isoformat();errors=[];data=None
 if local:data=parse(local.read_bytes())
 else:
  urls=[old['source_url'] if old else URL]
  try:
   p=Links();p.feed(get(PAGE).decode('utf-8'));urls=list(dict.fromkeys(p.urls+urls))
  except Exception as e:errors.append(type(e).__name__)
  candidates=[]
  for u in urls:
   try:candidates.append(parse(get(u),u))
   except Exception as e:errors.append(type(e).__name__)
  if candidates:data=max(candidates,key=lambda d:(d['periods'][-1]['year'],d['periods'][-1]['quarter']))
  if old and data and (data['periods'][-1]['year'],data['periods'][-1]['quarter'])<(old['periods'][-1]['year'],old['periods'][-1]['quarter']):data=None;errors.append('Descarga anterior al histórico conservado')
 if old and data:
  old_keys={(r['year'],r['quarter']) for r in old['periods']}
  new_keys={(r['year'],r['quarter']) for r in data['periods']}
  if not old_keys.issubset(new_keys):data=None;errors.append('La descarga recorta la historia; se conserva la anterior')
 if data:data.update(ranking=ranking(data),validated_at=now)
 else:data=old
 if not data:raise ValueError('Sin base estatal validada')
 data.update(last_checked=now,download_status='archivo_aportado' if local else 'ok' if not errors else 'conservado' if not candidates else 'parcial',download_errors=errors)
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
 print('IED estatal:',data['ranking']['label'],len(data['ranking']['rows']),'entidades;',data['download_status'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--import-file',type=Path);a=p.parse_args();refresh(local=a.import_file)

def add_excel_sheets(wb,data,general=False):
    """Dos hojas: histórico íntegro y ranking con fórmulas editables."""
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter as col
    from openpyxl.chart import BarChart,Reference
    prefix='IED ' if general else ''
    history=wb.create_sheet(prefix+'Historia estatal');rank=wb.create_sheet(prefix+'Ranking estatal')
    history.append(['IED estatal acumulada · millones de dólares corrientes'])
    history.append(['Fuente: Secretaría de Economía / RNIE · '+data['source_url']])
    history.merge_cells('A1:AH1');history.merge_cells('A2:AH2')
    history.append(['Periodo','Total nacional']+STATES)
    for p in data['periods']:history.append([p['label'],p['total']]+[p['values'][s] for s in STATES])
    last=data['periods'][-1];last_row=len(data['periods'])+3
    prior=next((i+4 for i,p in enumerate(data['periods']) if (p['year'],p['quarter'])==(last['year']-1,last['quarter'])),None)
    rank.append(['IED por entidad federativa · '+last['label']]);rank.append(['Comparación: mismo acumulado del año anterior; cifras actualizadas'])
    rank.merge_cells('A1:F1');rank.merge_cells('A2:F2')
    rank.append(['Entidad','IED (mdd)','Participación','Posición','Posición anterior','Cambio de posición'])
    ordered=data['ranking']['rows']
    for i,r in enumerate(ordered,4):
        c=col(STATES.index(r['state'])+3);h="'"+history.title+"'!"
        rank.append([r['state'],f'={h}{c}{last_row}',f'=B{i}/{h}$B${last_row}',f'=COUNTIF({h}$C${last_row}:$AH${last_row},\">\"&B{i})+1',f'=COUNTIF({h}$C${prior}:$AH${prior},\">\"&{h}{c}{prior})+1' if prior else None,f'=E{i}-D{i}' if prior else None])
    for ws in (history,rank):
        ws.sheet_view.showGridLines=False
        ws.column_dimensions['A'].width=42 if ws==rank else 22
        for c in range(2,ws.max_column+1):ws.column_dimensions[col(c)].width=23
        for row in ws:
            for cell in row:
                cell.font=Font(name='Noto Sans',size=10,bold=cell.row in (1,3));cell.alignment=Alignment(vertical='center',wrap_text=cell.row in (1,3))
                if cell.row==3:cell.fill=PatternFill('solid',fgColor='EEEEEE')
                if cell.row>=4 and cell.column>1:cell.number_format='#,##0.00' if ws==history or cell.column==2 else '0.0%' if cell.column==3 else '0'
        ws.row_dimensions[1].height=30;ws.row_dimensions[3].height=35
        ws.auto_filter.ref=f'A3:{col(ws.max_column)}{ws.max_row}'
    chart=BarChart();chart.type='bar';chart.title='Primeras diez entidades · '+last['label'];chart.x_axis.title='Millones de dólares';chart.x_axis.scaling.min=0;chart.y_axis.reverseOrder=True;chart.add_data(Reference(rank,min_col=2,min_row=3,max_row=13),titles_from_data=True);chart.set_categories(Reference(rank,min_col=1,min_row=4,max_row=13));chart.height=11;chart.width=22;chart.legend=None;rank.add_chart(chart,'H4')
