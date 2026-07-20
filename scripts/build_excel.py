"""Genera downloads/Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx.

Parte del Excel base (data/source/Indicadores_base.xlsx), conserva sus hojas
originales SIN alterarlas innecesariamente y agrega tres hojas nuevas:
  - "Síntesis de coyuntura"
  - "Metodología y fuentes"
  - "Control de actualizaciones"

No usa rutas locales ni fórmulas frágiles: los cálculos se resuelven con
fórmulas de Excel autocontenidas cuando aportan (promedios, máximos), sobre
rangos internos del propio libro.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import lib_data as L

ROOT = Path(__file__).resolve().parents[1]
BASE_XLSX = ROOT / "data" / "source" / "Indicadores_base.xlsx"
OUT_DIR = ROOT / "downloads"
OUT_XLSX = OUT_DIR / "Indicadores_Macroeconomicos_Mexico_Actualizado.xlsx"

DKGREEN = "FF002F2A"
GREEN = "FF1E5B4F"
GOLD = "FFA57F2C"
LINE = "FFE6E0D2"
PAPER = "FFF7F5EF"

TITLE = Font(name="Calibri", size=15, bold=True, color=DKGREEN)
H = Font(name="Calibri", size=11, bold=True, color="FFFFFFFF")
LBL = Font(name="Calibri", size=10, bold=True, color=DKGREEN)
TXT = Font(name="Calibri", size=10, color="FF161A1D")
MUT = Font(name="Calibri", size=9, color="FF6C6F6A", italic=True)
HEAD_FILL = PatternFill("solid", fgColor=DKGREEN)
BAND_FILL = PatternFill("solid", fgColor=PAPER)
THIN = Side(style="thin", color=LINE)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def _style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = H
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = BORDER


def _autow(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def add_resumen(wb, payload, manifest):
    ws = wb.create_sheet("Síntesis de coyuntura", 0)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Indicadores macroeconómicos de México — Síntesis de coyuntura"
    ws["A1"].font = TITLE
    ws["A2"] = f"Generado: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}"
    ws["A2"].font = MUT
    headers = ["Indicador", "Fuente", "Frecuencia", "Última observación", "Último valor", "Variación", "Unidad"]
    r0 = 4
    for i, h in enumerate(headers, start=1):
        ws.cell(row=r0, column=i, value=h)
    _style_header(ws, r0, len(headers))
    order = payload.get("order") or list(payload["indicators"].keys())
    r = r0 + 1
    for key in order:
        ind = payload["indicators"].get(key)
        if not ind:
            continue
        obs = ind["observations"]
        last = obs[-1] if obs else {"values": [None]}
        val = last["values"][0] if last["values"] else None
        var = last["values"][1] if len(last.get("values", [])) > 1 else None
        row_vals = [ind.get("nombre"), ind.get("fuente", {}).get("nombre"), ind.get("frecuencia"),
                    ind.get("last_observation"), val, var, ind.get("unidad")]
        for i, v in enumerate(row_vals, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = TXT
            cell.border = BORDER
            if r % 2 == 0:
                cell.fill = BAND_FILL
        r += 1
    ws["A" + str(r + 1)] = ("Nota: cifras oficiales sujetas a revisión. Análisis por reglas deterministas; "
                            "no se atribuye causalidad. La fuente de la tasa de desocupación es INEGI/ENOE. "
                            "Los indicadores en estado 'pendiente de token' o 'dato de respaldo' no se "
                            "presentan como actualización automática (ver 'Control de actualizaciones').")
    ws["A" + str(r + 1)].font = MUT
    ws["A" + str(r + 1)].alignment = WRAP
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 2, end_column=7)
    _autow(ws, [42, 30, 14, 20, 16, 14, 30])


def add_metodologia(wb, payload):
    ws = wb.create_sheet("Metodología y fuentes")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Metodología y fuentes"
    ws["A1"].font = TITLE
    headers = ["Indicador", "Fuente oficial", "Serie", "Unidad", "Ajuste estacional",
               "Frecuencia", "Método de actualización", "Enlace"]
    r0 = 3
    for i, h in enumerate(headers, start=1):
        ws.cell(row=r0, column=i, value=h)
    _style_header(ws, r0, len(headers))
    order = payload.get("order") or list(payload["indicators"].keys())
    r = r0 + 1
    for key in order:
        ind = payload["indicators"].get(key)
        if not ind:
            continue
        f = ind.get("fuente", {})
        vals = [ind.get("nombre"), f.get("nombre"), f.get("serie") or "—", ind.get("unidad"),
                ind.get("ajuste_estacional"), ind.get("frecuencia"), f.get("metodo"), f.get("link")]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = TXT
            cell.border = BORDER
            cell.alignment = WRAP
            if r % 2 == 0:
                cell.fill = BAND_FILL
        r += 1
    _autow(ws, [40, 34, 12, 26, 18, 14, 26, 40])


def _next_pub_map(calendar):
    """clave -> primera publicación con estatus 'próximo' (fecha y periodo)."""
    out = {}
    items = sorted((calendar or {}).get("items", []), key=lambda x: x.get("fecha_iso", ""))
    for it in items:
        if it.get("estatus") == "próximo" and it.get("clave") not in out:
            out[it["clave"]] = it
    return out


def add_control(wb, payload, manifest, log, calendar=None):
    ws = wb.create_sheet("Control de actualizaciones")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Control de actualizaciones"
    ws["A1"].font = TITLE
    ws["A2"] = (f"Última corrida del pipeline: {log.get('finished_at', '—')} · "
                f"resultado: {log.get('result', '—')} · modo: {log.get('mode', '—')}")
    ws["A2"].font = MUT
    headers = ["Indicador", "Clasificación", "Estado", "Origen del dato", "Requiere token",
               "Serie confirmada", "Última observación", "Periodo de referencia",
               "Fecha de publicación", "Próxima publicación (calendario)", "Fecha de consulta",
               "Actualización archivo", "Revisión detectada", "Observaciones de calidad"]
    nextpub = _next_pub_map(calendar)
    r0 = 4
    for i, h in enumerate(headers, start=1):
        ws.cell(row=r0, column=i, value=h)
    _style_header(ws, r0, len(headers))
    rows = {m["clave"]: m for m in manifest.get("indicadores", [])}
    order = payload.get("order") or list(payload["indicators"].keys())
    r = r0 + 1
    for key in order:
        m = rows.get(key)
        if not m:
            continue
        np = nextpub.get(key)
        np_txt = f"{np['fecha_publicacion']} · {np['periodo_referencia']}" if np else "—"
        vals = [m["indicador"], m.get("clasificacion"), m.get("estado"), m.get("origen_dato"),
                m.get("requiere_token") or "—", "Sí" if m.get("serie_confirmada") else "No",
                m["ultima_observacion"], m.get("periodo_referencia"), m.get("fecha_publicacion"),
                np_txt, m["fecha_consulta"], m["fecha_actualizacion_archivo"],
                "Sí" if m["revision_detectada"] else "No", m["observaciones"]]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = TXT
            cell.border = BORDER
            cell.alignment = WRAP
            if m["revision_detectada"]:
                cell.fill = PatternFill("solid", fgColor="FFF6E2E8")
            elif r % 2 == 0:
                cell.fill = BAND_FILL
        r += 1
    # Advertencias del pipeline
    r += 2
    ws.cell(row=r, column=1, value="Advertencias del pipeline:").font = LBL
    for w in log.get("warnings", []):
        r += 1
        ws.cell(row=r, column=1, value="• " + w).font = MUT
    _autow(ws, [40, 15, 26, 14, 14, 15, 18, 18, 26, 28, 16, 18, 16, 50])


# Hojas de datos a crear para indicadores nuevos que no existen en el libro base.
NEW_SHEETS = {
    "IMFBCF": "Formación bruta capital fijo",
    "IOAE": "IOAE",
    "EMIM": "EMIM (Manufactura)",
}


def add_indicator_sheets(wb, payload):
    """Crea hojas de datos para los indicadores principales nuevos. Si aún no
    tienen observaciones (scaffold pendiente de token), la hoja queda con los
    encabezados y una nota honesta, sin cifras inventadas."""
    for key, sheet_name in NEW_SHEETS.items():
        ind = payload["indicators"].get(key)
        if not ind or sheet_name in wb.sheetnames:
            continue
        ws = wb.create_sheet(sheet_name)
        ws.sheet_view.showGridLines = False
        ws["A1"] = ind.get("nombre")
        ws["A1"].font = TITLE
        ws["A2"] = (f"Fuente: {ind.get('fuente', {}).get('nombre', '—')} · "
                    f"Frecuencia: {ind.get('frecuencia', '—')} · Unidad: {ind.get('unidad', '—')} · "
                    f"Estado: {ind.get('estado', '—')}")
        ws["A2"].font = MUT
        cols = ind.get("columns", [])
        headers = ["Periodo"] + [c["label"] for c in cols]
        r0 = 4
        for i, h in enumerate(headers, start=1):
            ws.cell(row=r0, column=i, value=h)
        _style_header(ws, r0, len(headers))
        obs = ind.get("observations", []) or []
        if not obs:
            note = ("Sin observaciones cargadas todavía. "
                    f"Se activará al configurar {ind.get('requiere_token', 'el token')}_TOKEN "
                    "y confirmar la serie oficial. No se muestran cifras estimadas ni inventadas.")
            ws.cell(row=r0 + 1, column=1, value=note).font = MUT
            ws.merge_cells(start_row=r0 + 1, start_column=1, end_row=r0 + 2, end_column=max(2, len(headers)))
            ws.cell(row=r0 + 1, column=1).alignment = WRAP
        else:
            r = r0 + 1
            for o in obs:
                ws.cell(row=r, column=1, value=o["period"]).font = TXT
                for i, v in enumerate(o["values"], start=2):
                    ws.cell(row=r, column=i, value=v).font = TXT
                r += 1
        _autow(ws, [16] + [22] * len(cols))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = L.load_data()
    manifest = json.loads((L.DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    log_path = L.DATA_DIR / "update_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}

    if BASE_XLSX.exists():
        wb = openpyxl.load_workbook(BASE_XLSX)
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

    cal_path = L.DATA_DIR / "calendario_publicaciones.json"
    calendar = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else {}

    # No alterar las hojas originales: sólo agregamos hojas nuevas.
    for name in ("Resumen ejecutivo", "Síntesis de coyuntura", "Metodología y fuentes", "Control de actualizaciones"):
        if name in wb.sheetnames:
            wb.remove(wb[name])
    for name in NEW_SHEETS.values():
        if name in wb.sheetnames:
            wb.remove(wb[name])
    add_indicator_sheets(wb, payload)
    add_metodologia(wb, payload)
    add_control(wb, payload, manifest, log, calendar)
    add_resumen(wb, payload, manifest)  # queda como primera hoja (índice 0)

    wb.save(OUT_XLSX)
    print(f"OK: {OUT_XLSX.relative_to(ROOT)} ({OUT_XLSX.stat().st_size} bytes) · hojas: {wb.sheetnames}")


if __name__ == "__main__":
    main()
