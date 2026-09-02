"""Regenera solo el indicador IED en data/indicadores.json.

Usar mientras build_data.py completo sigue colgándose en conectores de red locales.
El pipeline de CI volverá a ejecutar build_data y refrescará estados/calendario.
"""
from __future__ import annotations

import json
from pathlib import Path

import lib_data as L
import lib_metrics
from sources import ied

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    payload = L.load_data()
    res = ied.fetch()
    if not res.ok:
        print("ERROR:", res.warnings)
        return 1

    from build_data import merge_indicator
    merge_indicator(payload, "IED", res.data["IED"])

    # Recomputar métricas compartidas mínimas sin tocar otros indicadores
    kpicfg, _ = lib_metrics._kpicfg_and_colors()
    ied_metrics = lib_metrics._ied_metrics(payload["indicators"]["IED"], kpicfg)
    if ied_metrics:
        payload["indicators"]["IED"].setdefault("metrics", {})
        for key in ("kpi", "yoy", "annualVar", "resumen", "analysis"):
            if ied_metrics.get(key) is not None:
                payload["indicators"]["IED"]["metrics"][key] = ied_metrics[key]
        # Asegurar que las métricas estructuradas del conector se conservan
        for key in ("acumulado", "flujo_trimestral", "composicion_tipo", "composicion_pais",
                    "composicion_sector", "composicion_entidad", "componentes_acumulado",
                    "componentes_flujo", "corte_referencia", "source_mode"):
            if key in payload["indicators"]["IED"]["metrics"]:
                payload["indicators"]["IED"]["metrics"].setdefault(key, payload["indicators"]["IED"]["metrics"][key])
        # Quitar campos antiguos genéricos si existen y ya no aplican
        payload["indicators"]["IED"]["metrics"].pop("main", None)

    # Estado honesto: el dato de 2T-26 ya fue publicado (24 ago 2026)
    payload["indicators"]["IED"]["estado"] = "ACTUALIZADO"
    payload["indicators"]["IED"]["periodo_referencia"] = payload["indicators"]["IED"].get("periodo_referencia") or "Ene-Jun 26"

    # Guardar
    L.save_data(payload)
    print("OK: IED actualizado en data/indicadores.json")
    print("  last_observation:", payload["indicators"]["IED"]["last_observation"])
    print("  acumulado:", payload["indicators"]["IED"].get("metrics", {}).get("acumulado"))
    print("  flujo:", payload["indicators"]["IED"].get("metrics", {}).get("flujo_trimestral"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
