"""Genera notas individuales (.docx) por indicador.

- Usa plantilla si existe en data/source/plantilla_nota.docx; si no, crea un docx mínimo.
- Solo genera notas para indicadores con datos validados.
- Incorpora portada, resumen, gráfica, tabla reciente, metodología, fuente y enlace.
"""
from __future__ import annotations

import argparse
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # noqa: E402
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

import lib_data as L
from lib_kpicfg import get_cfg
from lib_metrics import annual_var, compute_var, fmt_val, primary_series
from sources import inegi

ROOT = Path(__file__).resolve().parents[1]
PLANTILLA = ROOT / "data" / "source" / "plantilla_nota.docx"
NOTES_DIR = ROOT / "downloads" / "indicadores"


def _period_to_date(period: str):
    ym = inegi.label_to_ym(period)
    if not ym:
        return None
    return datetime.strptime(ym, "%Y-%m").date()


def _prev_valid_i(idxs: list[int], i: int) -> int | None:
    for j in range(i - 1, -1, -1):
        if j in idxs:
            return j
    return None


def _set_run_font(run, size: int = 11, bold: bool = False, color: RGBColor | None = None):
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color


def _add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.name = "Calibri"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    return p


def _add_para(doc: Document, text: str, bold: bool = False, align=None):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    run = p.add_run(text)
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    _set_run_font(run, size=11, bold=bold)
    return p


def _portada(doc: Document, ind: dict, kpi: dict | None):
    _add_para(doc, "NOTA DE INDICADOR", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_para(doc, ind.get("nombre", ind["key"]), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_para(doc, f"Clave: {ind['key']}", align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_para(doc, "")
    meta = [
        ("Periodo de referencia", kpi["ultimoP"] if kpi else (ind.get("last_observation") or "—")),
        ("Fecha de publicación", ind.get("fecha_publicacion") or "—"),
        ("Fuente", ind.get("fuente", {}).get("nombre", "—")),
        ("Unidad", ind.get("unidad", "—")),
        ("Ajuste estacional", ind.get("ajuste_estacional", "—")),
    ]
    for k, v in meta:
        _add_para(doc, f"{k}: {v}")
    doc.add_page_break()


def _add_resumen(doc: Document, resumen: list[str]):
    _add_heading(doc, "Resumen ejecutivo", level=1)
    for b in resumen:
        _add_para(doc, f"• {b}")


def _add_grafica(doc: Document, ind: dict, kpi: dict, cfg: dict) -> bool:
    if not kpi:
        return False
    periods = kpi["periods"]
    series = kpi["series"]
    fechas = [_period_to_date(p) for p in periods]
    x = [d for d, v in zip(fechas, series) if d and v is not None]
    y = [v for v, d in zip(series, fechas) if d and v is not None]
    if len(x) < 2:
        return False

    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(x, y, color="#1e5b4f", linewidth=1.8, marker="o", markersize=3)
    ax.set_title(f"{ind['nombre']} — evolución del nivel", fontsize=11)
    ax.set_ylabel(cfg.get("varLabel", "Nivel"), fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    if (max(x) - min(x)).days > 180:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    _add_heading(doc, "Gráfica", level=1)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(buf, width=Inches(6))
    return True


def _add_tabla_reciente(doc: Document, ind: dict, kpi: dict, cfg: dict):
    _add_heading(doc, "Datos recientes", level=1)
    obs = ind.get("observations", [])
    vals = primary_series(ind, cfg)
    idxs = [i for i, v in enumerate(vals) if v is not None]
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Periodo"
    hdr[1].text = "Nivel"
    hdr[2].text = "Variación mensual / trimestral"
    hdr[3].text = "Variación anual"
    for cell in hdr:
        for run in cell.paragraphs[0].runs:
            run.bold = True
    start = max(0, len(obs) - 12)
    for i in range(start, len(obs)):
        period = obs[i]["period"]
        prev_i = _prev_valid_i(idxs, i)
        var_info = compute_var(ind, cfg, vals, i, prev_i) if i > 0 and prev_i is not None else None
        yoy_info = annual_var(ind, {"lastI": i, "series": vals}, get_cfg("KPICFG")) if vals[i] is not None and i > 0 else None
        row_cells = table.add_row().cells
        row_cells[0].text = period
        row_cells[1].text = fmt_val(vals[i], cfg.get("valFmt")) if vals[i] is not None else "—"
        row_cells[2].text = var_info["text"] if var_info and var_info.get("text") else "—"
        row_cells[3].text = yoy_info["text"] if yoy_info and yoy_info.get("text") else "—"
    doc.add_paragraph()


def _add_metodologia(doc: Document, ind: dict):
    _add_heading(doc, "Metodología y fuente", level=1)
    _add_para(doc, ind.get("descripcion") or ind.get("nombre"))
    _add_para(doc, f"Fuente: {ind.get('fuente', {}).get('nombre', '—')}")
    if ind.get("fuente", {}).get("link"):
        _add_para(doc, f"Enlace: {ind['fuente']['link']}")
    if ind.get("notas"):
        _add_para(doc, "Notas: " + " ".join(ind["notas"]))
    _add_para(doc, f"Generado el {datetime.now(timezone.utc).strftime('%d de %B de %Y a las %H:%M UTC')}.")


def _build_note(ind: dict, kpicfg: dict) -> tuple[Document, bool]:
    if PLANTILLA.exists():
        doc = Document(str(PLANTILLA))
    else:
        doc = Document()
        doc.styles["Normal"].font.name = "Calibri"
        doc.styles["Normal"].font.size = Pt(11)

    metrics = ind.get("metrics", {})
    kpi = metrics.get("kpi")
    resumen = metrics.get("resumen", [])
    cfg = kpicfg.get(ind["key"])
    _portada(doc, ind, kpi)
    if kpi and resumen:
        _add_resumen(doc, resumen)
        _add_tabla_reciente(doc, ind, kpi, cfg)
        _add_grafica(doc, ind, kpi, cfg)
    _add_metodologia(doc, ind)
    return doc, True


def build_notes(payload: dict, pilot: list[str] | None = None) -> dict[str, Path]:
    kpicfg = get_cfg("KPICFG")
    keys = pilot if pilot else list(payload["indicators"].keys())
    generated: dict[str, Path] = {}
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    for key in keys:
        ind = payload["indicators"][key]
        out_dir = NOTES_DIR / key
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{key}_nota.docx"

        if not ind.get("observations"):
            ind["nota_disponible"] = False
            ind["nota_causa"] = "Sin observaciones"
            continue
        if ind.get("estado") not in ("ACTUALIZADO",):
            ind["nota_disponible"] = False
            ind["nota_causa"] = f"Estado del indicador: {ind.get('estado')}. La nota solo se genera para indicadores ACTUALIZADO."
            continue
        if not ind.get("metrics"):
            ind["nota_disponible"] = False
            ind["nota_causa"] = "Sin métricas calculadas"
            continue

        try:
            doc, _ = _build_note(ind, kpicfg)
            doc.save(str(out_path))
            ind["nota_disponible"] = True
            ind["nota_causa"] = None
            ind["url_nota_individual"] = str(out_path.relative_to(ROOT))
            generated[key] = out_path
        except Exception as e:
            ind["nota_disponible"] = False
            ind["nota_causa"] = f"Error al generar nota: {e}"
            ind["url_nota_individual"] = None
    return generated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="Solo IGAE e INPC")
    args = ap.parse_args()

    payload = L.load_data()
    pilot = ["IGAE", "INPC"] if args.pilot else None
    generated = build_notes(payload, pilot=pilot)
    (L.DATA_DIR / "indicadores.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    if generated:
        print(f"OK: {len(generated)} notas generadas:")
        for key, path in generated.items():
            print(f"  {key}: {path.relative_to(ROOT)}")
    else:
        print("No se generaron notas; revisar causas en nota_causa.")


if __name__ == "__main__":
    main()
