"""Utilidades compartidas del pipeline de datos."""
from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
DATA_FILE = DATA_DIR / "indicadores.json"
BACKUP_DIR = DATA_DIR / "_backup"
OVERRIDES_FILE = DATA_DIR / "overrides.json"
META_FILE = CONFIG_DIR / "indicadores_meta.json"

# Estados honestos permitidos (deben coincidir con ESTADOS en assets/js/config.js).
EST_AUTO = "actualizado automáticamente"
EST_BACKUP = "dato de respaldo vigente"
EST_TOKEN = "pendiente de token"
EST_SERIE = "pendiente de confirmar serie"
EST_ERROR = "error de fuente"
EST_REVIEW = "dato en revisión"
EST_PARTIAL = "actualización parcial"
EST_NA = "no disponible"


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
    # Idempotencia: limpia las anotaciones de calidad de los indicadores que
    # tocan los overrides antes de reaplicarlas (evita duplicados entre corridas).
    for rule in ov.get("overrides", []):
        ind = payload["indicators"].get(rule["indicator"])
        if ind is not None:
            ind["data_quality"] = []
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


def _has_real_data(ind: dict) -> bool:
    for o in ind.get("observations", []) or []:
        if any(v is not None for v in o.get("values", [])):
            return True
    return False


def apply_profile(payload: dict, meta_file: Path = META_FILE) -> list[str]:
    """Aplica el perfil V3: crea scaffolds (indicadores sin observaciones aún),
    fija el orden principal/complementario y asigna estados HONESTOS por
    indicador según haya token, serie confirmada y datos reales.

    No inventa cifras: los scaffolds quedan con observations=[] y estado
    'pendiente de token'/'no disponible'. Devuelve un log de cambios.
    """
    log: list[str] = []
    if not meta_file.exists():
        return log
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    inds = payload["indicators"]

    # 1) Alta de scaffolds ausentes (sin cifras).
    for key, sc in meta.get("scaffolds", {}).items():
        if key not in inds:
            inds[key] = {
                "key": key, "nombre": sc["nombre"], "descripcion": sc.get("descripcion", ""),
                "frecuencia": sc.get("frecuencia"), "unidad": sc.get("unidad"),
                "ajuste_estacional": sc.get("ajuste_estacional"), "grupo": sc.get("grupo"),
                "publicacion": sc.get("publicacion"), "proximo": sc.get("proximo"),
                "fuente": sc.get("fuente", {}), "columns": sc.get("columns", []),
                "observations": [], "last_observation": None,
                "last_updated": None, "last_checked": None,
                "requiere_token": sc.get("requiere_token"),
                "serie_confirmada": sc.get("serie_confirmada", False),
                "clasificacion": sc.get("clasificacion", "principal"),
            }
            log.append(f"scaffold creado: {key}")

    # 2) Metadatos de perfil para indicadores existentes.
    profile = {**meta.get("profile", {})}
    for key, sc in meta.get("scaffolds", {}).items():
        profile.setdefault(key, {"requiere_token": sc.get("requiere_token"),
                                 "serie_confirmada": sc.get("serie_confirmada", False),
                                 "clasificacion": sc.get("clasificacion", "principal")})
    for key, prof in profile.items():
        ind = inds.get(key)
        if not ind:
            continue
        ind["requiere_token"] = prof.get("requiere_token")
        ind["serie_confirmada"] = prof.get("serie_confirmada", False)
        ind["clasificacion"] = prof.get("clasificacion", "principal")

    # 3) Estado honesto por indicador.
    for key, ind in inds.items():
        token = ind.get("requiere_token")
        token_present = bool(token) and bool(os.environ.get(f"{token}_TOKEN"))
        from_api = ind.get("source_origin") == "api"
        has_data = _has_real_data(ind)
        in_review = bool(ind.get("data_quality"))

        if from_api and ind.get("serie_confirmada"):
            estado, origen = EST_AUTO, "api"
        elif has_data and in_review:
            estado, origen = EST_REVIEW, "respaldo"
        elif has_data:
            estado, origen = EST_BACKUP, "respaldo"
        elif token and not token_present:
            estado, origen = EST_TOKEN, "pendiente"
        elif token and not ind.get("serie_confirmada"):
            estado, origen = EST_SERIE, "pendiente"
        else:
            estado, origen = EST_NA, "pendiente"

        ind["estado"] = estado
        ind["origen_dato"] = origen
        ind["fecha_publicacion"] = ind.get("publicacion")
        ind["periodo_referencia"] = ind.get("last_observation")
        ind["fecha_consulta"] = ind.get("last_checked")

    # 4) Orden: principales (según perfil) y luego complementarios.
    principal = [k for k in meta.get("principal", []) if k in inds]
    complementario = [k for k in meta.get("complementario", []) if k in inds]
    rest = [k for k in inds if k not in principal and k not in complementario]
    payload["order"] = principal + complementario + rest
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
        dq = ind.get("data_quality") or []
        rows.append({
            "indicador": ind.get("nombre"), "clave": key,
            "clasificacion": ind.get("clasificacion", "principal"),
            "fuente": ind.get("fuente", {}).get("nombre"),
            "serie": ind.get("fuente", {}).get("serie"),
            "frecuencia": ind.get("frecuencia"), "unidad": ind.get("unidad"),
            "ajuste_estacional": ind.get("ajuste_estacional"),
            "ultima_observacion": ind.get("last_observation"),
            "periodo_referencia": ind.get("periodo_referencia") or ind.get("last_observation"),
            "fecha_publicacion": ind.get("fecha_publicacion") or ind.get("publicacion"),
            "fecha_consulta": ind.get("last_checked"),
            "fecha_actualizacion_archivo": ind.get("last_updated"),
            "metodo_actualizacion": ind.get("fuente", {}).get("metodo"),
            "estado": ind.get("estado", EST_NA),
            "origen_dato": ind.get("origen_dato"),
            "requiere_token": ind.get("requiere_token"),
            "serie_confirmada": bool(ind.get("serie_confirmada")),
            "usa_respaldo": ind.get("origen_dato") == "respaldo",
            "revision_detectada": bool(dq),
            "error": ind.get("error"),
            "observaciones": "; ".join(d.get("reason", "") for d in dq),
        })
    (DATA_DIR / "manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "indicadores": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def today_iso() -> str:
    return date.today().isoformat()
