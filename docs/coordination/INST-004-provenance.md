# INST-004: éxito de Actions y vigencia de datos

Complemento local de solo lectura al recolector del PR #23. No modifica el recolector, el workflow de auditoría, el watchdog, la publicación ni los cortes. Vincula cada fila del informe a una corrida exacta mediante el ID, ruta, resultado, intento y hora de conclusión, y registra el SHA del código de esa corrida. No atribuye ese SHA a los archivos publicados. El corte se evalúa por separado con la política de vigencia del dashboard y una hora de observación explícita.

```sh
node --test tests/audit_actions_provenance.test.mjs
node scripts/audit_actions_provenance.mjs informe.json metadata.json salud.json config/update_policy.json 2026-11-27T08:00:00Z
```

El JSON de metadatos debe contener `runs`, con los metadatos de GitHub de las corridas presentes en el informe. El archivo de salud debe corresponder por URL a una corrida institucional de actualización presente en el informe. El complemento se ejecuta sin conexión y no obtiene los insumos por sí mismo. No extender el acceso del recolector ni programar otro job para producirlos.
