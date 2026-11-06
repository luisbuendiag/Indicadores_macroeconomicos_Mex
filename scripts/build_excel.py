"""Excel históricos: un mismo modelo para el libro general y los individuales.

No descarga fuentes ni cambia observaciones. Publica un conjunto validado, sin
resúmenes narrativos, y conserva los productos vigentes ante un fallo.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
import hashlib
import json
import math
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import openpyxl
from openpyxl.chart import LineChart, Reference, Series
from openpyxl.chart.axis import DateAxis
from openpyxl.chart.series import SeriesLabel
from openpyxl.chart.data_source import StrRef, StrData, StrVal
from openpyxl.chart.text import RichText
from openpyxl.drawing.text import CharacterProperties, Font as DrawingFont, Paragraph, ParagraphProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.workbook.properties import CalcProperties

import lib_data as L
from lib_kpicfg import get_cfg  # compatibilidad con consumidores existentes
from excel_layout import SHEETS, DERIVED, EXCLUDED, NOTES

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'downloads'
IND_DIR = OUT_DIR / 'indicadores'
OUT_XLSX = OUT_DIR / 'Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx'
FONT = 'Noto Sans'
INK = '161A1D'
GREEN = '1E5B4F'
SIGLA = {'PIBSEC':'PIBT', 'DESOCUP':'ENOE', 'CONSUMO':'IMCP', 'TIPOCAMBIO':'FIX'}
CHARTS = {
 'PIB': [[0],[1,2]], 'PIBSEC': [[5],[6,7]], 'SIC': [[0],[1]], 'IGAE': [[0],[1,2]],
 'IMAI': [[0],[1,2]], 'IMOAM': [[0,1,2],[3,4,5]], 'IOAE': [[0,1,2],[3]],
 'EMIM': [[0],[3,4]], 'EMOE': [[0],[3,4,5,6]], 'DESOCUP': [[0,3],[5]],
 'INPC': [[2,5],[16,17]], 'INPP': [[0,4],[2,6]], 'CONSUMO': [[0],[1,2]],
 'IMFBCF': [[0,3,6],[1,2]], 'BCMM': [[0,1],[2]], 'IED': [[0],[1,2,3]],
 'TIPOCAMBIO': [[0]], 'TASA': [[0]], 'RESERVAS': [[0],[1]],
}


def _period_date(value: str | date) -> date:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    text = str(value).strip()
    try: return date.fromisoformat(text[:10])
    except ValueError: pass
    q = re.match(r'([1-4])T[- ](\d{2}|\d{4})(?:\s|$)', text)
    if q:
        y = int(q[2]); y = y + (1900 if y >= 70 else 2000) if y < 100 else y
        return date(y, (int(q[1])-1)*3+1, 1)
    months = {'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12}
    m = re.match(r'([A-Za-z]{3})\s+(\d{2}|\d{4})(?:\s|$)', text)
    if m and m[1].lower() in months:
        y = int(m[2]); y = y + (1900 if y >= 70 else 2000) if y < 100 else y
        return date(y, months[m[1].lower()], 1)
    raise ValueError(f'Periodo no reconocido: {value!r}')


def _xl_fmt(fmt):
    return {'pct-frac':'0.0%', 'pct-raw':'0.0"%"', 'idx':'#,##0.0', 'emoe':'0.00',
            'usd':'#,##0.0', 'num':'#,##0', 'fx':'0.0000', 'pp':'0.000" p.p."',
            'text':'@', 'bill':'#,##0.0', 'mdd':'#,##0.0', 'mdd-signed':'+#,##0.0;-#,##0.0;0.0'}.get(fmt, '#,##0.0')


def _shift(d, months):
    y,m = divmod(d.year*12+d.month-1-months,12)
    return date(y,m+1,1)


def _number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _records(ind):
    records={}
    for observation in ind.get('observations',[]):
        d=_period_date(observation['period'])
        if d in records: raise ValueError(f"{ind['key']}: periodo duplicado {d}")
        records[d]=observation
    return dict(sorted(records.items()))


def _recipe(key, index, d, records):
    rule=DERIVED.get(key,{}).get(index)
    if not rule: return None
    source,lag,operation=rule
    def val(day):
        v=records.get(day,{}).get('values',[])
        return v[source] if source<len(v) else None
    previous=_shift(d,lag)
    if _number(val(d)) and _number(val(previous)) and (operation=='diff' or val(previous)>0):
        return (source,[d],[previous],operation)
    return None


def _text_properties(size=10):
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=CharacterProperties(
        latin=DrawingFont(typeface=FONT),sz=size*100)))])


class Model:
    def __init__(self):
        self.wb=openpyxl.Workbook(); self.wb.remove(self.wb.active)
        self.wb.calculation=CalcProperties(calcId=191029,fullCalcOnLoad=True,forceFullCalc=True,calcMode='auto')
        self.coords={}; self.headers={}; self.pending=[]; self.coverage=[]; self.chart_plans=[]
        self.numeric_sources=0; self.formulas=0; self.table_id=0

    def sheet(self,name,ind,frequency=None):
        ws=self.wb.create_sheet(name)
        ws.sheet_view.showGridLines=False; ws.sheet_view.zoomScale=90
        ws.freeze_panes=None
        ws.column_dimensions['A'].width=17
        for c in range(2,7): ws.column_dimensions[letter(c)].width=23
        ws.column_dimensions['G'].width=3
        for c in range(8,15): ws.column_dimensions[letter(c)].width=11
        for r in (1,2,3,4,5): ws.merge_cells(start_row=r,start_column=1,end_row=r,end_column=6)
        ws['A1']=ind.get('nombre',ind['key']); ws['A1'].font=Font(name=FONT,size=14,bold=True,color=INK)
        ws.row_dimensions[1].height=42
        source=ind.get('fuente',{}); source_name=source.get('nombre') or 'Fuente oficial'
        ws['A3']=f"Fuente: {source_name}"
        url=source.get('link') or ind.get('url_fuente_oficial') or ind.get('url_boletin_oficial')
        if url: ws['A3'].hyperlink=url
        pub=ind.get('fecha_publicacion') or ind.get('fecha_publicacion_oficial')
        consult=ind.get('fecha_consulta') or ind.get('last_checked') or ind.get('last_updated') or ''
        unit=ind.get('unidad','')
        if ind['key']=='DESOCUP':unit='Personas' if frequency=='Trimestral' else 'Porcentaje'
        if ind['key']=='PIBSEC':unit='Porcentaje' if name=='Variaciones' else 'Millones de pesos de 2018' if name=='Niveles' else 'Millones de pesos de 2018 y porcentaje, según bloque'
        ws['A2']=f"Frecuencia: {frequency or ind.get('frecuencia','')}   Unidad: {unit}"
        ws['A4']=f"Consulta: {consult}"+(f"   Última edición: {pub}" if pub else '')
        ws['A5']=NOTES.get(ind['key'],'')
        for r in (2,3,4,5):
            ws.cell(r,1).font=Font(name=FONT,size=9,color='4C5650')
            ws.row_dimensions[r].height=30 if ws.cell(r,1).value else 8
        for row in ws.iter_rows(min_row=1,max_row=5):
            for cell in row: cell.alignment=Alignment(vertical='center',wrap_text=True)
        ws.print_options.horizontalCentered=False
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0
        return ws

    def block(self,ws,ind,title,indices,row,records=None,columns=None,register=True):
        key=ind['key']; records=records if records is not None else _records(ind)
        by_index={c['index']:c for c in (columns or ind['columns'])}
        indices=[i for i in indices if i in by_index]
        # Cuatro variables por bloque para evitar tablas de 40 columnas.
        for offset in range(0,len(indices),4):
            ids=indices[offset:offset+4]
            data=[]
            for d,o in records.items():
                vals=o.get('values',[])
                values=[vals[i] if i<len(vals) else None for i in ids]
                recipes=[_recipe(key,i,d,records) if v is None else None for i,v in zip(ids,values)] if register else [None]*len(ids)
                if any(v is not None for v in values) or any(recipes): data.append((d,o,values,recipes))
            if not data: continue
            block_title=title+(f' ({offset//4+1})' if len(indices)>4 else '')
            ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=6)
            ws.cell(row,1,block_title).font=Font(name=FONT,size=11,bold=True,color=INK)
            ws.cell(row,1).alignment=Alignment(wrap_text=True,vertical='center'); ws.row_dimensions[row].height=32
            meta_row=row+1
            # Cobertura por serie, registrada fuera del libro descargable.
            coverage=[]
            for i in ids:
                dates=[d for d,o,values,recipes in data if (o.get('values',[None]*(i+1))+[None]*(i+1))[i] is not None]
                if dates:
                    coverage.append({'key':key,'sheet':ws.title,'column':i,'label':by_index[i]['label'],
                                     'first':dates[0].isoformat(),'last':dates[-1].isoformat(),'count':len(dates)})
            self.coverage.extend(coverage)
            ws.merge_cells(start_row=meta_row,start_column=1,end_row=meta_row,end_column=6)
            meta=f"{data[0][0].isoformat()} a {data[-1][0].isoformat()}"
            if any(any(x[3]) for x in data): meta+='   Las celdas con fórmula calculan tasas desde los niveles de esta misma serie.'
            ws.cell(meta_row,1,meta).font=Font(name=FONT,size=9,color='58615B')
            ws.cell(meta_row,1).alignment=Alignment(wrap_text=True,vertical='center');ws.row_dimensions[meta_row].height=28
            header=meta_row+1
            status=any(re.search(r'\s[PR]$',o['period']) for _,o,_,_ in data)
            labels=['Periodo']+[by_index[i]['label'] for i in ids]+(['Carácter publicado'] if status else [])
            for c,label in enumerate(labels,1):
                cell=ws.cell(header,c,label);cell.font=Font(name=FONT,size=10,bold=True,color=INK)
                cell.fill=PatternFill('solid',fgColor='EBEEEB')
                cell.alignment=Alignment(vertical='center',wrap_text=True)
                cell.border=Border(bottom=Side(style='thin',color='CCD2CD'))
            ws.row_dimensions[header].height=44
            for n,(d,o,values,recipes) in enumerate(data,header+1):
                period=ws.cell(n,1,d)
                quarterly='trimestral' in (ind.get('_excel_frequency') or ind.get('frecuencia','')).lower() and key!='DESOCUP'
                if key=='DESOCUP' and ws.title.endswith('Población ocupada'): quarterly=True
                period.number_format=('yyyy' if ind.get('_excel_frequency','').startswith('Anual') else f'"{(d.month-1)//3+1}T "yyyy' if quarterly else 'yyyy-mm-dd' if key in ('TIPOCAMBIO','TASA','RESERVAS') or re.match(r'\d{4}-\d{2}-\d{2}',o['period']) else 'mmm yyyy')
                for c,(i,value,recipe) in enumerate(zip(ids,values,recipes),2):
                    if value is not None and by_index[i].get('fmt')!='text' and not _number(value):
                        raise ValueError(f'{key}: valor no numérico en {by_index[i]["label"]}, {d}')
                    cell=ws.cell(n,c,value)
                    if by_index[i].get('fmt')=='text' and value and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value)):
                        cell.value=date.fromisoformat(value);cell.number_format='yyyy-mm-dd'
                    elif by_index[i].get('fmt')=='text' and str(value).startswith('https://'):
                        cell.hyperlink=value;cell.value='Comunicado oficial'
                    else:
                        cell.number_format=_xl_fmt(by_index[i].get('fmt'))
                        if key.startswith('TASA') and by_index[i].get('fmt')=='pct-raw':cell.number_format='0.00"%"'
                    if _number(value): self.numeric_sources+=1
                    if register:
                        self.coords[(key,i,d)]=(ws.title,cell.coordinate)
                        self.headers[(key,i)]=(ws.title,ws.cell(header,c).coordinate)
                        if recipe: self.pending.append((cell,key,recipe))
                if status:
                    m=re.search(r'\s([PR])$',o['period'])
                    ws.cell(n,len(labels),{'P':'Preliminar','R':'Revisado'}[m[1]] if m else None)
                for cell in ws[n][:len(labels)]:
                    cell.font=Font(name=FONT,size=10,color=INK)
                    cell.alignment=Alignment(vertical='center',horizontal='left' if cell.column==1 else 'right')
                ws.row_dimensions[n].height=18
            self.table_id+=1
            table=Table(displayName=f'Serie{self.table_id}',ref=f'A{header}:{letter(len(labels))}{header+len(data)}')
            table.tableStyleInfo=TableStyleInfo(name='TableStyleLight1',showRowStripes=False,showColumnStripes=False)
            ws.add_table(table)
            row=header+len(data)+4
        return row

    def finish_formulas(self):
        def ref(key,index,d):
            s,c=self.coords[(key,index,d)];return f"'{s.replace(chr(39),chr(39)*2)}'!{c}"
        for cell,key,(source,current,previous,operation) in self.pending:
            keys=[(key,source,d) for d in current+previous]
            if not all(k in self.coords for k in keys): continue
            cur=[ref(key,source,d) for d in current]; prev=[ref(key,source,d) for d in previous]
            a=f"SUM({','.join(cur)})" if len(cur)>1 else cur[0]
            b=f"SUM({','.join(prev)})" if len(prev)>1 else prev[0]
            check=','.join(cur+prev)
            if operation=='diff': result=f'{a}-{b}';valid=f'COUNT({check})={len(keys)}'
            else:
                result=f'({a}/{b}-1)'+('*100' if operation=='pct-raw' else '')
                valid=f'AND(COUNT({check})={len(keys)},{b}>0)'
            cell.value=f'=IF({valid},{result},"")';self.formulas+=1

    def chart(self,key,columns,ws,anchor,frequency):
        maps=[{d:coord for (k,i,d),coord in self.coords.items() if k==key and i==col} for col in columns]
        if any(not m for m in maps): return False
        dates=sorted(set.intersection(*(set(m) for m in maps)))
        if len(dates)<2:return False
        count=260 if frequency=='Diaria' else 156 if frequency=='Semanal' else 40 if frequency=='Trimestral' else 60
        dates=dates[-count:]
        for m in maps:
            rows=[openpyxl.utils.cell.coordinate_from_string(m[d][1])[1] for d in dates]
            if rows!=list(range(rows[0],rows[-1]+1)):return False
        chart=LineChart();chart.width=19;chart.height=10
        first_sheet,first_cell=maps[0][dates[0]];last_cell=maps[0][dates[-1]][1]
        fr=openpyxl.utils.cell.coordinate_from_string(first_cell)[1];lr=openpyxl.utils.cell.coordinate_from_string(last_cell)[1]
        cols={c['index']:c for c in self._indicators[key]['columns']}
        labels=[cols[c]['label'] for c in columns]
        chart.title=labels[0] if len(columns)==1 else ('Estimación e IC 95%' if key in ('IMOAM','IOAE') else ' / '.join(labels))
        chart.x_axis=DateAxis(crossAx=100);chart.x_axis.number_format='yyyy' if frequency.startswith('Anual') else 'mmm-yy';chart.x_axis.tickLblPos='low'
        span=(dates[-1].year-dates[0].year)*12+dates[-1].month-dates[0].month
        chart.x_axis.majorTimeUnit='years' if span>=120 else 'months'
        chart.x_axis.majorUnit=2 if span>=120 else 6 if span>=24 else 3 if span>=6 else 1
        chart.y_axis.crossAx=chart.x_axis.axId
        chart.x_axis.scaling.min=openpyxl.utils.datetime.to_excel(dates[0])
        chart.x_axis.scaling.max=openpyxl.utils.datetime.to_excel(dates[-1])
        chart.x_axis.title=f'{dates[0].isoformat()} a {dates[-1].isoformat()}'
        fmt=cols[columns[0]].get('fmt','num')
        chart.y_axis.numFmt='0.00"%"' if key.startswith('TASA') and fmt=='pct-raw' else _xl_fmt(fmt)
        chart.y_axis.title='Porcentaje' if fmt.startswith('pct') else 'Puntos porcentuales' if fmt=='pp' else 'Pesos por dólar' if fmt=='fx' else 'Millones de dólares' if fmt=='usd' else 'Puntos' if fmt in ('idx','emoe') else 'Nivel'
        if key=='PIBSEC' and columns[0] in (0,1,2,5):chart.y_axis.title='Millones de pesos de 2018'
        if key=='DESOCUP' and columns==[5]:chart.y_axis.title='Personas'
        for n,(column,m) in enumerate(zip(columns,maps)):
            sheet,cell=m[dates[0]];column_letter,rownum=openpyxl.utils.cell.coordinate_from_string(cell)
            ref=Reference(self.wb[sheet],min_col=openpyxl.utils.cell.column_index_from_string(column_letter),min_row=rownum,max_row=rownum+len(dates)-1)
            ser=Series(ref)
            hs,hc=self.headers[(key,column)]
            ser.tx=SeriesLabel(strRef=StrRef(f=f"'{hs.replace(chr(39),chr(39)*2)}'!${re.sub(r'[0-9]','',hc)}${re.sub(r'[^0-9]','',hc)}",strCache=StrData(ptCount=1,pt=[StrVal(idx=0,v=labels[n])])))
            ser.graphicalProperties.line.solidFill=['1E5B4F','7D8780','B2BAB4','4A5550'][n%4]
            ser.graphicalProperties.line.width=22000;ser.marker.symbol='none';ser.smooth=False
            chart.series.append(ser)
        chart.set_categories(Reference(self.wb[first_sheet],min_col=1,min_row=fr,max_row=lr))
        chart.display_blanks='gap';chart.legend.position='b'
        chart.txPr=_text_properties();chart.x_axis.txPr=_text_properties(9);chart.y_axis.txPr=_text_properties(9);chart.legend.txPr=_text_properties(9)
        for title in (chart.title,chart.x_axis.title,chart.y_axis.title):
            if title and title.tx and title.tx.rich:
                for paragraph in title.tx.rich.p:
                    paragraph.pPr=ParagraphProperties(defRPr=CharacterProperties(latin=DrawingFont(typeface=FONT),sz=1000))
                    for run in paragraph.r:run.rPr=CharacterProperties(latin=DrawingFont(typeface=FONT),sz=1000)
        ws.add_chart(chart,anchor)
        return True

    def finish_charts(self):
        for key,ws,frequency,indices,anchors in self.chart_plans:
            count=0;used=set()
            candidates=CHARTS.get(key,[])
            for cols in candidates:
                if not all(c in indices for c in cols):continue
                anchor=anchors[min(count,len(anchors)-1)]
                if count:anchor=f"H{max(int(re.sub(r'[^0-9]', '',anchor)),int(re.sub(r'[^0-9]', '',anchors[0]))+23)}"
                if self.chart(key,cols,ws,anchor,frequency):count+=1;used.update(cols)
                if count==2:break
            if not count and indices:
                for col in indices:
                    if self.chart(key,[col],ws,anchors[0],frequency):break


def _special(ind,name):
    key=ind['key']
    if key=='IED' and name=='Acumulado comparable':
        cut=ind.get('metrics',{}).get('acumulado',{}).get('corte','')
        records={}
        for o in ind.get('observations_acumulado',[]):
            year=int(o['period']); records[date(year,1,1)]={'period':str(year),'values':o['values']}
        columns=[{'index':i,'label':label,'fmt':fmt} for i,(label,fmt) in enumerate([
            ('IED acumulada (mdd)','usd'),('Nuevas inversiones (mdd)','usd'),('Reinversión de utilidades (mdd)','usd'),
            ('Cuentas entre compañías (mdd)','usd'),('Variación anual del acumulado (%)','pct-frac')])]
        return records,columns,f'Acumulado comparable {cut} (millones de dólares y %)', 'Anual al mismo corte'
    if key=='TASA' and name=='Decisiones':
        records={date.fromisoformat(d['announcement_date']):{'period':d['announcement_date'],'values':[
            d.get('effective_date'), d.get('change_bp'),d.get('previous_rate'),d.get('new_rate'),d.get('comunicado_url')]} for d in ind.get('policy_decisions',[])}
        columns=[{'index':i,'label':label,'fmt':fmt} for i,(label,fmt) in enumerate([
            ('Entrada en vigor','text'),('Cambio (pb)','num'),('Tasa previa (%)','pct-raw'),('Nueva tasa (%)','pct-raw'),('Comunicado','text')])]
        return records,columns,'Decisiones por fecha de anuncio', 'Por decisión'
    return None


def build_workbook(indicators,general=False):
    model=Model();model._indicators={i['key']:i for i in indicators}
    for ind in indicators:
        key=ind['key']
        if key in ('PIBSEC','IGAE','IMAI','IMOAM','EMIM','CONSUMO','IMFBCF') and '2018' not in ind.get('unidad',''):
            raise ValueError(f'{key}: cambió o falta la base del índice/precios; revisar antes de exportar')
        specs=SHEETS.get(key,[(key,[(ind.get('nombre',key),[c['index'] for c in ind['columns']])])])
        regular=[(name,groups) for name,groups in specs if groups]
        if general:
            ordinary=[(n,g) for n,g in regular if not (key=='DESOCUP' and n=='Población ocupada')]
            rest=[(n,g) for n,g in regular if (key=='DESOCUP' and n=='Población ocupada')]
            regular=[(SIGLA.get(key,key),[group for _,groups in ordinary for group in groups])]+rest
        for name,groups in regular:
            frequency=('Trimestral' if name=='Población ocupada' else 'Mensual') if key=='DESOCUP' else ind.get('frecuencia','Mensual')
            ws=model.sheet(name,ind,frequency)
            row=7;anchors=[];indices=[]
            for title,ids in groups:
                ids=[i for i in ids if i<len(ind['columns'])]
                if not ids:continue
                anchors.append(f'H{row}');indices.extend(ids)
                row=model.block(ws,ind,title,ids,row)
            model.chart_plans.append((key,ws,frequency,indices,anchors or ['H7']))
        for name,groups in specs:
            if groups:continue
            special=_special(ind,name)
            if not special or not special[0]:continue
            records,columns,title,frequency=special
            sheet_name=f"{SIGLA.get(key,key)} {name}" if general else name
            ws=model.sheet(sheet_name[:31],ind,frequency)
            ws['A5']=title
            alias=f'{key}_{name}'
            special_ind={**ind,'key':alias,'columns':columns,'_excel_frequency':frequency}
            model._indicators[alias]=special_ind
            CHARTS[alias]=[[0],[1,2,3]] if key=='IED' else [[3]]
            model.block(ws,special_ind,title,list(range(len(columns))),7,records,columns)
            numeric_indices=[c['index'] for c in columns if c['fmt']!='text']
            model.chart_plans.append((alias,ws,frequency,numeric_indices,['H7','H30']))
    model.finish_formulas();model.finish_charts()
    return model


def validate_workbook(path):
    wb=openpyxl.load_workbook(path,data_only=False)
    if wb._external_links:raise ValueError(f'{path.name}: vínculos externos')
    report={'sheets':len(wb.worksheets),'charts':0,'formulas':0}
    for ws in wb:
        if ws.freeze_panes or ws.sheet_view.pane:raise ValueError(f'{path.name}: paneles inmovilizados')
        for row in ws:
            for c in row:
                if c.value is None:continue
                if c.data_type=='e':raise ValueError(f'{ws.title}!{c.coordinate}: {c.value}')
                if c.font.name!=FONT:raise ValueError(f'{ws.title}!{c.coordinate}: fuente no homologada')
                if c.data_type=='f':
                    report['formulas']+=1
                    if '#REF!' in c.value:raise ValueError(f'Referencia rota: {c.coordinate}')
        report['charts']+=len(ws._charts)
        for name,table in ws.tables.items():
            # El filtro debe cubrir exactamente el rango de la tabla.
            if not table:raise ValueError(f'Tabla vacía: {name}')
    def bounds(reference):
        sheet,area=reference.rsplit('!',1);sheet=sheet.strip("'").replace("''","'")
        if sheet not in wb.sheetnames:raise ValueError(f'Hoja referenciada inexistente: {sheet}')
        min_col,min_row,max_col,max_row=openpyxl.utils.cell.range_boundaries(area)
        if max_row>wb[sheet].max_row or max_col>wb[sheet].max_column:
            raise ValueError(f'Referencia fuera de los datos: {reference}')
        return max_row-min_row+1
    ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
    with zipfile.ZipFile(path) as z:
        if z.testzip():raise ValueError(f'{path.name}: ZIP corrupto')
        for name in z.namelist():
            if name.startswith('xl/charts/chart') and name.endswith('.xml'):
                xml=ET.fromstring(z.read(name))
                for series in xml.findall('.//c:ser',ns):
                    vals=series.find('c:val/c:numRef/c:f',ns)
                    cats=series.find('c:cat/c:numRef/c:f',ns)
                    if vals is None or cats is None:raise ValueError(f'{name}: gráfica sin referencias reales')
                    if bounds(vals.text)!=bounds(cats.text):raise ValueError(f'{name}: periodos desalineados')
    wb.close();return report


def _save_single(ind,path):
    model=build_workbook([ind]);model.wb.save(path);validate_workbook(path)


# Entradas anteriores conservadas para las integraciones y las pruebas.
def _build_individual_workbook(ind,cfg,kpicfg,out_path):_save_single(ind,out_path)
def _build_pib_workbook(ind,out_path):_save_single(ind,out_path)
def _build_pibsec_workbook(ind,out_path):_save_single(ind,out_path)
def _build_imai_workbook(ind,out_path):_save_single(ind,out_path)
def _build_imfbcf_workbook(ind,out_path):_save_single(ind,out_path)
def _build_bcmm_workbook(ind,out_path):_save_single(ind,out_path)
def build_emim_workbook(ind,out_path):_save_single(ind,out_path)
def _build_desocup_workbook(ind,out_path):_save_single(ind,out_path)
def _build_ied_workbook(ind,out_path):_save_single(ind,out_path)
def _build_tasa_workbook(ind,out_path):_save_single(ind,out_path)


def generate(payload,out_dir=None):
    """Construye y valida todo en staging antes de reemplazar el conjunto vigente."""
    out_dir=Path(out_dir or OUT_DIR);out_dir.mkdir(parents=True,exist_ok=True)
    order=payload.get('order') or list(payload['indicators'])
    missing=[k for k in order if not payload['indicators'].get(k,{}).get('observations')]
    if missing:raise ValueError('Sin historia para: '+', '.join(missing))
    indicators=[payload['indicators'][k] for k in order]
    report={};staged=[]
    with tempfile.TemporaryDirectory(prefix='.excel-',dir=out_dir) as tmp:
        stage=Path(tmp)
        for ind in indicators:
            key=ind['key'];model=build_workbook([ind]);path=stage/f'{key}_datos.xlsx';model.wb.save(path)
            report[key]={**validate_workbook(path),'coverage':model.coverage,'omitted_redundancy':EXCLUDED.get(key,{})}
            staged.append((path,out_dir/'indicadores'/key/path.name))
        master=build_workbook(indicators,general=True);path=stage/OUT_XLSX.name;master.wb.save(path)
        report['general']=validate_workbook(path)
        source_fields=('columns','observations','observations_acumulado','policy_decisions')
        snapshot={i['key']:{f:i.get(f) for f in source_fields} for i in indicators}
        report['general']['input_sha256']=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        staged.append((path,out_dir/path.name))
        for source,target in staged:
            validate_workbook(source)
            report_key='general' if source.name==OUT_XLSX.name else source.stem.removesuffix('_datos')
            report[report_key]['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        previous_path=L.DATA_DIR/'excel'/'estado.json'
        if out_dir==OUT_DIR and previous_path.exists():
            previous=json.loads(previous_path.read_text())
            for key,item in report.items():
                old={(c['key'],c['column']):c for c in previous.get(key,{}).get('coverage',[])}
                for c in item.get('coverage',[]):
                    if (c['key'],c['column']) in old:
                        was=old[c['key'],c['column']]
                        if c['first']>was['first'] or c['last']<was['last'] or c['count']<was['count']:
                            raise ValueError(f'{key}: se acortó la historia de {c["label"]}; se conserva la publicación anterior')
        # Ningún archivo se sustituye si falló alguna generación o validación anterior.
        for source,target in staged:
            target.parent.mkdir(parents=True,exist_ok=True);os.replace(source,target)
    return report


def build_individual_files(payload,pilot=None):
    indicators=payload['indicators']
    for key,ind in indicators.items():
        if pilot and key not in pilot:continue
        if not ind.get('observations'):continue
        path=IND_DIR/key/f'{key}_datos.xlsx';path.parent.mkdir(parents=True,exist_ok=True)
        _save_single(ind,path)
        ind.update(xlsx_disponible=True,xlsx_causa=None,url_excel_individual=f'downloads/indicadores/{key}/{key}_datos.xlsx')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUT_DIR)
    args=parser.parse_args(argv if argv is not None else ([] if 'pytest' in sys.modules else None))
    payload=L.load_data()
    report=generate(payload,args.output_dir)
    if args.output_dir==OUT_DIR:
        before=json.dumps(payload,ensure_ascii=False)
        for key in report:
            if key=='general':continue
            payload['indicators'][key].update(xlsx_disponible=True,xlsx_causa=None,url_excel_individual=f'downloads/indicadores/{key}/{key}_datos.xlsx')
        if json.dumps(payload,ensure_ascii=False)!=before:
            L.DATA_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
        report_path=L.DATA_DIR/'excel'/'estado.json';report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'OK: {len(report)-1} Excel individuales y libro general; '+str(sum(v['charts'] for v in report.values()))+' gráficas nativas.')
    return 0


import sys
if __name__=='__main__':raise SystemExit(main())
