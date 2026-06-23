"""Wrapper de consola que reusa el mismo motor que el algoritmo de Processing.

Útil para desarrollo y para corridas no-interactivas. La UI oficial para
el usuario final es el algoritmo `qa/validador_toolbox.py` cargado en la
Caja de herramientas de QGIS.

Uso:
    python qa/validar.py                       # todas las categorías
    python qa/validar.py numero_predial        # solo una categoría
    python qa/validar.py numero_predial duplicados
    python qa/validar.py --rules-dir=C:/otra/ruta/reglas   # carpeta de reglas distinta
    python qa/validar.py --gpkg=C:/otro.gpkg               # GPKG distinto
    python qa/validar.py --r1=C:/ruta/r1.csv               # CSV del Registro 1
"""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

import helpers  # noqa: E402


def _parse_args(argv: list[str]) -> tuple[Path | None, Path, list[str], Path | None]:
    rules_dir: Path | None = None
    gpkg: Path | None = None
    r1_csv: Path | None = None
    cats: list[str] = []
    for arg in argv[1:]:
        if arg.startswith("--rules-dir="):
            rules_dir = Path(arg.split("=", 1)[1])
        elif arg.startswith("--gpkg="):
            gpkg = Path(arg.split("=", 1)[1])
        elif arg.startswith("--r1="):
            r1_csv = Path(arg.split("=", 1)[1])
        elif arg.startswith("--"):
            print(f"Argumento desconocido: {arg}")
            sys.exit(2)
        else:
            cats.append(arg)
    if gpkg is None:
        gpkg = helpers.gpkg_path_desde_proyecto()
    return rules_dir, gpkg, cats, r1_csv


def main(argv: list[str]) -> int:
    rules_dir, gpkg, cats, r1_csv = _parse_args(argv)
    helpers.run_rules(
        gpkg=gpkg,
        categorias=cats or None,
        dir_reglas=rules_dir,
        r1_csv=r1_csv,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
