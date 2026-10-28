"""Ejecuta la construcción real de las tarjetas IMOAM para detectar errores de render."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_imoam_kpi_container_renders_all_cards():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node no está disponible")
    script = r'''
const fs = require("node:fs");
const assert = require("node:assert/strict");
const source = fs.readFileSync("assets/js/app.js", "utf8");
const body = source.split('} else if (ind.key === "IMOAM") {')[1]
    .split('} else if (ind.key === "IOAE")')[0];
const render = new Function("ind", "k", "el", "fmtVal", "let mini;"+body+"; return mini;");
const mini = render(
    {observations:[{values:[108,105.1,111.1,.019,-.009,.047]}]}, {lastI:0},
    (tag,attrs,...children)=>({tag,attrs,children}), v=>String(v));
assert.equal(mini.attrs.class, "mini-kpis");
assert.equal(mini.children.length, 4);
assert.ok(JSON.stringify(mini).includes("108"));
assert.ok(JSON.stringify(mini).includes("Intervalo de confianza"));
'''
    subprocess.run([node, "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
