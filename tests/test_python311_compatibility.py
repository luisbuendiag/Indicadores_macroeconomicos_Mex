"""El runner de GitHub usa Python 3.11 aunque el editor use otra versión."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_scripts_and_tests_support_python311():
    for folder in ('scripts','tests'):
        for path in (ROOT/folder).rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'),filename=str(path),feature_version=(3,11))
