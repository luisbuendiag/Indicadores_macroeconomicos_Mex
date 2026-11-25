# Piloto de datos compartidos con MacroMéxico

El piloto usa la edición pública de MacroMéxico como insumo para las series de PIBT, FIX y remesas. Se ejecuta fuera del ciclo de publicación del dashboard institucional. No requiere tokens de acceso a las fuentes económicas ni credenciales de Supabase.

```sh
python scripts/pilot_shared_data.py --institucional data/indicadores.json --salida /tmp/institucional-piloto.json
```

El comando coteja la huella de la edición y los dos archivos con el comprobante publicado. Exige consulta válida de los tres indicadores, el mismo corte y coincidencia de esquema, fuente e historial completo, incluida la serie mensual auxiliar del FIX. Si ocurre una diferencia, sale con error y no abre el archivo de salida. Sin `--salida` imprime el resultado de la comparación.

La edición candidata toma las series del origen comercial y conserva la configuración, métricas y archivos institucionales. La IED conserva su fuente y su corte. El objetivo del piloto es probar que ambas publicaciones pueden utilizar un insumo común sin perder cobertura. La paridad estricta sirve para esta prueba. El uso en corridas programadas requiere comprobar cómo se aceptan cortes nuevos y revisiones oficiales sin retroceder, y cómo se conservan los horarios de publicación de ambos sitios.


## Simular una actualización

```sh
python scripts/pilot_shared_data.py --institucional data/indicadores.json --estado-institucional data/update_health.json
```

Este modo emite una decisión por indicador. Si ambas ediciones coinciden, informa equivalencia. Con una consulta comercial posterior a la última consulta institucional, acepta periodos nuevos o revisiones si coinciden el esquema y la fuente, se conserva todo el historial y ningún valor publicado se sustituye por un nulo. Cualquier corte atrasado o serie incompatible conserva la versión institucional para ese indicador. Los indicadores restantes se evalúan de forma independiente. La simulación no genera productos ni modifica el flujo de publicación.
