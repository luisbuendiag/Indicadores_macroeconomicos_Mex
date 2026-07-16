# Fuentes de datos y viabilidad de automatización — `DATA_SOURCES.md`

> **Fase 2 del brief.** Documenta la fuente oficial de cada indicador, su método de actualización y la viabilidad de automatización. Complementa `AUDITORIA_DASHBOARD.md`.
> **Fecha:** 2026-07-16

---

## 0. APIs oficiales evaluadas (verificadas en esta auditoría)

| Fuente | Endpoint base | Token | Formato | Verificado |
|--------|---------------|-------|---------|------------|
| **INEGI — BIE (Banco de Indicadores)** | `https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/{serie}/es/0700/false/BIE/2.0/{token}?type=json` | Gratuito ([registro](https://www.inegi.org.mx/app/desarrolladores/generatoken/Usuarios/token_Verify)) | JSON/XML | ✅ HTTP 200 |
| **Banco de México — SIE API** | `https://www.banxico.org.mx/SieAPIRest/service/v1/series/{ids}/datos` (header `Bmx-Token`) | Gratuito ([registro](https://www.banxico.org.mx/SieAPIRest/service/v1/token)) | JSON/XML | ✅ alcanzable (400 sin token) |
| **World Bank Indicators API** | `https://api.worldbank.org/v2/country/MEX/indicator/{id}?format=json` | No requiere | JSON | ✅ HTTP 200 (dato 2024 devuelto) |
| **OECD SDMX API** | `https://sdmx.oecd.org/public/rest/data/...` | No requiere | SDMX-JSON/CSV | Documentada (comparativo desempleo) |
| **DataMéxico** | `https://api.datamexico.org/` | No requiere | JSON | Complementaria |

> **Nota:** los identificadores de serie INEGI/Banxico listados abajo son los candidatos conocidos; cada uno se **verificará contra la API en la Fase 3** antes de fijarlo en el pipeline, comparando el último dato de la API con el `window.MACRO` actual.

---

## 1. Matriz de indicadores

| Indicador | Hoja de Excel | Fuente | Serie (candidata) | Frecuencia | Método de actualización | Última observación (actual) | Rezago | Notas metodológicas |
|-----------|---------------|--------|-------------------|------------|-------------------------|-----------------------------|--------|---------------------|
| **PIB** (millones de pesos, prec. 2018) | PIB | INEGI (SCNM) | BIE serie PIB trimestral, prec. constantes | Trimestral | INEGI BIE API | 1T-26 P | ~50 días | Serie original; P=preliminar, R=revisada |
| **PIB por actividad** (primarias/secundarias/terciarias) | PIB Sectorial | INEGI (SCNM) | BIE series por gran división | Trimestral | INEGI BIE API | 1T-26 P | ~50 días | Serie original a prec. 2018 |
| **IGAE** (índice 2018=100 + secundarias + terciarias) | IGAE | INEGI | BIE IGAE (global/secund./terc.) | Mensual | INEGI BIE API | Abr-26 P | ~55 días | Serie original; base 2018=100 |
| **IMAI** (índice 2018=100 + var. mensual) | IMAI | INEGI | BIE IMAI | Mensual | INEGI BIE API | Abr-26 P | ~40 días | Serie original; base 2018=100 |
| **Exportaciones** | Exportaciones | INEGI (Balanza) | BIE balanza — exportaciones | Mensual | INEGI BIE API | May-26 O | ~30–45 días | mdd; O=oportuna |
| **Importaciones** | Balanza comercial | INEGI (Balanza) | BIE balanza — importaciones | Mensual | INEGI BIE API | May-26 O | ~30–45 días | mdd |
| **Balanza comercial** (saldo X−M) | Balanza comercial | INEGI | derivado (X − M) | Mensual | Calculado | May-26 O | ~30–45 días | mdd |
| **Consumo privado** (índice 2018=100) | Consumo Privado | INEGI | BIE IMCP | Mensual | INEGI BIE API | Mar-26 P | ~70 días | Serie original; base 2018=100 |
| **IED** (total + 3 componentes) | IED | Secretaría de Economía (RNIE) | Portal RNIE / DataMéxico | Trimestral | Descarga oficial / DataMéxico | 1T-26 | ~45 días | mdd; componentes: nuevas inversiones, reinversión, cuentas entre compañías |
| **Tasa de desocupación** | Tasa de desocupación | INEGI (ENOE/ENOEN) | BIE tasa de desocupación nacional | Mensual | INEGI BIE API | May-26 | ~25–30 días | % de la PEA. **Corregir atribución** (hoy enlaza a OCDE) |
| **Inflación general (INPC)** | INPC (Inflación) | INEGI | BIE INPC var. anual | Mensual | INEGI BIE API | May-26 | ~9 días | Var. anual % |
| **Inflación subyacente** | INPC (Inflación) | INEGI | BIE subyacente | Mensual | INEGI BIE API | May-26 | ~9 días | Var. anual % |
| **Inflación no subyacente** | INPC (Inflación) | INEGI | BIE no subyacente | Mensual | INEGI BIE API | May-26 | ~9 días | Var. anual % |

*(Las columnas "Última observación" reflejan el estado actual del `window.MACRO` embebido; el pipeline las actualizará y registrará en `manifest.json` con fecha de consulta.)*

---

## 2. Indicadores adicionales — clasificación

Según su utilidad para la **Secretaría de Economía** (foco: industria, comercio exterior, inversión, nearshoring):

### Esenciales (incorporar en V2)
- **Inflación subyacente y no subyacente** — ya en los datos, solo falta exponerlas como KPIs propios.
- **Tipo de cambio (FIX)** — Banxico SIE `SF43718`. Diario. Alta relevancia para comercio/inversión.
- **Tasa de referencia (objetivo Banxico)** — Banxico SIE `SF61745`. Contexto financiero directo.
- **Producción industrial por componente** (manufacturas, construcción, minería, electricidad) — INEGI, desglose del IMAI. El brief lo pide (secciones D).

### Recomendables (fase posterior cercana)
- **Empleo formal IMSS** (asegurados) — mensual, señal de mercado laboral formal.
- **Inversión fija bruta** — INEGI, complementa IED.
- **Exportaciones manufactureras / no petroleras** — INEGI balanza, clave para nearshoring.
- **Reservas internacionales** — Banxico SIE.
- **Confianza empresarial / del consumidor** — INEGI.

### Complementarios (si hay tiempo/valor)
- **Comercio con EE.UU.** (participación) — INEGI/DataMéxico.
- **Producción automotriz** — INEGI/AMIA.
- **Indicadores estatales / actividad regional (ITAEE)** — INEGI; requiere mapas.
- **Ventas minoristas (ANTAD/EMEC)** — INEGI.
- **Salarios reales** — INEGI/CONASAMI.

### Prescindibles (por ahora)
- Indicadores adelantados compuestos y matrices de riesgo elaboradas: alto esfuerzo, valor marginal frente al núcleo. Se dejan como *pendientes*.

---

## 3. Viabilidad de automatización — resumen

| Indicador/grupo | ¿Automatizable? | Cómo | Costo |
|-----------------|-----------------|------|-------|
| PIB, PIB sectorial, IGAE, IMAI, Consumo, Balanza, Desocupación, INPC | ✅ Sí | INEGI BIE API (token gratuito) | $0 |
| Tipo de cambio, tasa de referencia, reservas | ✅ Sí | Banxico SIE API (token gratuito) | $0 |
| IED | ⚠️ Parcial | RNIE publica archivos trimestrales; DataMéxico como alternativa. Puede requerir descarga programada del archivo oficial. | $0 |
| Comparativos internacionales (OCDE desempleo, PIB) | ✅ Sí | World Bank / OECD (sin token) | $0 |
| Noticias/eventos | ⚠️ Limitado | RSS oficiales + calendarios (sin API de pago) | $0 |

**Conclusión:** la automatización del **núcleo (11 de 13 indicadores mínimos) es viable y gratuita** vía INEGI BIE + cálculo derivado. IED es el único con posible fricción (descarga de archivo en lugar de API limpia). No se requiere ningún servicio de pago.

---

## 4. Requisitos para arrancar el pipeline

1. **Token INEGI BIE** (gratuito) → como *GitHub Secret* `INEGI_TOKEN`.
2. **Token Banxico SIE** (gratuito) → como *GitHub Secret* `BANXICO_TOKEN`.
3. Confirmar identificadores de serie exactos (Fase 3, contra la API).
4. Definir ventana histórica objetivo por serie (p. ej. desde 2018 o 2015 para mejor contexto).

> Los tokens **nunca** se guardan en el repositorio; solo como secretos de GitHub Actions y variables locales en `.env` (git-ignorado).
