# Guía de actualización, tokens y rollback

## 1. Tokens (INEGI y Banxico)

Ambos son **gratuitos**:
- INEGI (BIE): https://www.inegi.org.mx/servicios/api_indicadores.html
- Banxico (SIE): https://www.banxico.org.mx/SieAPIRest/service/v1/token

### Local (`.env`)
```bash
cp .env.example .env
# edita .env:
# INEGI_TOKEN=xxxxxxxx
# BANXICO_TOKEN=yyyyyyyy
```
`.env` está en `.gitignore` y **nunca** debe subirse.

### GitHub Actions (Secrets)
Repositorio → **Settings → Secrets and variables → Actions → New repository secret**:
- `INEGI_TOKEN`
- `BANXICO_TOKEN`

El workflow `update-data.yml` los lee vía `secrets.INEGI_TOKEN` / `secrets.BANXICO_TOKEN`.

## 2. Confirmar IDs de series de INEGI

Los IDs del BIE se dejaron en `null` en `config/series.json` para no consultar una serie
equivocada. Con el token ya cargado:
1. Ubica el ID de cada serie en el catálogo del BIE (PIB, IGAE, IMAI, INPC, ENOE, balanza,
   consumo, y el desglose de producción industrial: manufacturas, construcción, minería, energía).
2. Colócalos en `config/series.json` (campo `serie`, y `confirmar: false`).
3. Completa la normalización por indicador en `scripts/sources/inegi.py` (mapear la
   respuesta del BIE al esquema `observations`), validando contra datos reales.

## 3. Actualizar datos

```bash
python scripts/build_data.py            # online (usa tokens si existen)
python scripts/build_data.py --offline  # sin red
python scripts/fetch_news.py            # noticias (a prueba de fallos)
python scripts/build_excel.py           # regenerar Excel
python scripts/validate.py              # ver validaciones
python -m pytest -q                     # pruebas
```

Sin tokens, el pipeline **conserva la última versión válida**, registra advertencias en
`data/update_log.json` y no publica una versión incompleta como si estuviera completa.

## 4. Corregir un dato de calidad (p. ej. IMAI/Consumo feb-2026)

Edita `data/overrides.json` y agrega/actualiza una regla:
```json
{ "indicator": "IMAI", "period": "Feb 26 P", "column": 0,
  "status": "corregido", "value": 101.2,
  "reason": "Valor oficial confirmado en INEGI BIE",
  "source_checked": "INEGI BIE", "date_flagged": "2026-08-01" }
```
Luego ejecuta `build_data.py` y `build_excel.py`. Ver [`REPORTE_IMAI_CONSUMO.md`](REPORTE_IMAI_CONSUMO.md).

## 5. Rollback

El dashboard original queda intacto para revertir en cualquier momento:

- **A nivel de sitio**: la rama `backup/dashboard-original` contiene el estado original.
  Para revertir la publicación, apunta GitHub Pages a esa rama o restaura `index.html`
  desde ella:
  ```bash
  git checkout backup/dashboard-original -- index.html
  ```
  También existe una copia en [`legacy/dashboard-original.html`](legacy/dashboard-original.html).

- **A nivel de datos**: cada corrida respalda el estado previo en `data/_backup/` y mantiene
  `data/_backup/last_valid.json`. Para restaurar:
  ```bash
  python -c "import sys; sys.path.insert(0,'scripts'); import lib_data as L; print('restaurado', L.restore_last_valid())"
  ```

- **A nivel de repositorio**: revertir el merge del PR con `git revert -m 1 <commit>`.

## 6. Programación automática

`update-data.yml` corre en días hábiles (13:00 UTC) y por `workflow_dispatch`.
`deploy-pages.yml` publica a GitHub Pages al hacer push a `main`.
