"""Utilidades compartidas del pipeline de datos."""
from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "indicadores.json"
BACKUP_DIR = DATA_DIR / "_backup"
OVERRIDES_FILE = DATA_DIR / "overrides.json"


def load_env(dotenv: Path | None = None) -> None:
    """Carga variables desde un archivo .env local (sin sobrescribir las ya
    presentes en el entorno). No falla si el archivo no existe."""
    path = dotenv or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def load_data(path: Path = DATA_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_data(payload: dict, path: Path = DATA_FILE) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def backup_current() -> Path | None:
    """Respalda data/indicadores.json antes de reemplazarlo (último dato válido)."""
    if not DATA_FILE.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = BACKUP_DIR / f"indicadores_{ts}.json"
    dst.write_text(DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    # conserva además un "last_valid" estable
    (BACKUP_DIR / "last_valid.json").write_text(DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def restore_last_valid() -> bool:
    lv = BACKUP_DIR / "last_valid.json"
    if lv.exists():
        DATA_FILE.write_text(lv.read_text(encoding="utf-8"), encoding="utf-8")
        return True
    return False


def apply_overrides(payload: dict, overrides_file: Path = OVERRIDES_FILE) -> list[str]:
    """Aplica correcciones/anotaciones de calidad. Devuelve el log de cambios."""
    log: list[str] = []
    if not overrides_file.exists():
        return log
    ov = json.loads(overrides_file.read_text(encoding="utf-8"))
    for rule in ov.get("overrides", []):
        ind = payload["indicators"].get(rule["indicator"])
        if not ind:
            continue
        for o in ind["observations"]:
            if o["period"] == rule["period"]:
                col = rule["column"]
                if 0 <= col < len(o["values"]):
                    before = o["values"][col]
                    o["values"][col] = rule.get("value")
                    log.append(f"{rule['indicator']} {rule['period']} col{col}: {before} -> {rule.get('value')} ({rule.get('status')})")
                ind.setdefault("data_quality", []).append({
                    "period": rule["period"], "column": col,
                    "status": rule.get("status"), "reason": rule.get("reason"),
                })
    return log


def write_csvs(payload: dict) -> None:
    csv_dir = DATA_DIR / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for key, ind in payload["indicators"].items():
        with (csv_dir / f"{key}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["periodo"] + [c["label"] for c in ind["columns"]])
            for o in ind["observations"]:
                w.writerow([o["period"]] + ["" if v is None else v for v in o["values"]])


def write_manifest(payload: dict) -> None:
    order = payload.get("order") or list(payload["indicators"].keys())
    rows = []
    for key in order:
        ind = payload["indicators"].get(key)
        if not ind:
            continue
        rows.append({
            "indicador": ind.get("nombre"), "clave": key,
            "fuente": ind.get("fuente", {}).get("nombre"),
            "serie": ind.get("fuente", {}).get("serie"),
            "frecuencia": ind.get("frecuencia"), "unidad": ind.get("unidad"),
            "ajuste_estacional": ind.get("ajuste_estacional"),
            "ultima_observacion": ind.get("last_observation"),
            "fecha_consulta": ind.get("last_checked"),
            "fecha_actualizacion_archivo": ind.get("last_updated"),
            "metodo_actualizacion": ind.get("fuente", {}).get("metodo"),
            "estatus": ind.get("estatus", "ok"),
            "revision_detectada": bool(ind.get("data_quality")),
            "observaciones": "; ".join(d.get("reason", "") for d in ind.get("data_quality", [])),
        })
    (DATA_DIR / "manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "indicadores": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def today_iso() -> str:
    return date.today().isoformat()
