"""Motor del validador de reglas administrativas.

Responsabilidades:
  * Conexión al GeoPackage y DDL de la tabla `qa_errores`.
  * Descubrimiento automático de reglas desde `qa/reglas/*.py`.
  * Ejecución filtrada por categoría o severidad.
  * Reporte de progreso a través de un objeto `feedback` opcional
    (compatible con `QgsProcessingFeedback` y con un fallback a stdout).

Cómo agregar una regla nueva:
  1. Editar (o crear) un archivo en `qa/reglas/` cuyo nombre identifique
     la categoría: `numero_predial.py`, `direccion.py`, etc.
  2. Dentro, agregar un dict a la lista `REGLAS` con los campos:
       id, descripcion, severidad, sql.
     El campo `categoria` se infiere del nombre del archivo (puede
     sobreescribirse si la regla pertenece a otra agrupación).
  3. El SQL debe SELECT (tabla, t_id, clave_negocio, mensaje,
     valor_actual, valor_esperado) en ese orden. Cada fila = un error.
  4. Re-correr el algoritmo. No hay nada más que tocar.
"""

from __future__ import annotations

import csv
import importlib.util
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


# --------- Configuración ----------------------------------------------------

TOLERANCIA_AREA_PORCENTAJE = 0.05
TOLERANCIA_AREA_ABSOLUTA_M2 = 2.0
TOLERANCIA_AREA_UMBRAL_M2 = 500.0

DEPARTAMENTO_ESPERADO = "25"
MUNICIPIO_ESPERADO = "506"


# --------- Localización de archivos ----------------------------------------

DIR_QA = Path(__file__).resolve().parent
DIR_REGLAS = DIR_QA / "reglas"


def gpkg_path_desde_proyecto() -> Path:
    """Heurística: busca `captura_*.gpkg` en el directorio padre de `qa/`."""
    raiz = DIR_QA.parent
    candidatos = sorted(raiz.glob("captura_*.gpkg"))
    if not candidatos:
        raise FileNotFoundError(f"No se encontró captura_*.gpkg en {raiz}")
    return candidatos[0]


# --------- Conexión y DDL ---------------------------------------------------

def connect(gpkg: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(gpkg))
    con.execute("PRAGMA foreign_keys = ON")
    return con


DDL_QA_ERRORES = """
CREATE TABLE IF NOT EXISTS qa_errores (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    regla_id          TEXT NOT NULL,
    regla_descripcion TEXT NOT NULL,
    categoria         TEXT NOT NULL,
    severidad         TEXT NOT NULL,
    tabla             TEXT NOT NULL,
    t_id              INTEGER,
    clave_negocio     TEXT,
    mensaje           TEXT,
    valor_actual      TEXT,
    valor_esperado    TEXT,
    fecha_validacion  TEXT NOT NULL
)
"""


def ensure_qa_table(con: sqlite3.Connection) -> None:
    con.execute(DDL_QA_ERRORES)
    cur = con.execute(
        "SELECT 1 FROM gpkg_contents WHERE table_name = 'qa_errores'"
    )
    if cur.fetchone() is None:
        con.execute(
            """
            INSERT INTO gpkg_contents
                (table_name, data_type, identifier, description, last_change)
            VALUES
                ('qa_errores', 'attributes', 'qa_errores',
                 'Errores de validación de reglas administrativas',
                 datetime('now'))
            """
        )
    con.commit()


# --------- Carga de insumo R1 (CSV) ----------------------------------------

def cargar_r1(con: sqlite3.Connection, csv_path: str | Path) -> int:
    """Crea la tabla auxiliar `_r1_predios` y la puebla desde un CSV.

    El CSV debe tener al menos una columna cuyo nombre contenga
    'predial' (case-insensitive). Se toma la primera que coincida.
    Retorna la cantidad de filas cargadas.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo R1 no encontrado: {path}")

    con.execute("DROP TABLE IF EXISTS _r1_predios")
    con.execute(
        "CREATE TABLE _r1_predios (numero_predial TEXT PRIMARY KEY)"
    )

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        col = None
        for nombre in reader.fieldnames or []:
            if "predial" in nombre.lower():
                col = nombre
                break
        if col is None:
            raise ValueError(
                f"No se encontró columna con 'predial' en {path}. "
                f"Columnas disponibles: {reader.fieldnames}"
            )
        filas = 0
        for row in reader:
            valor = (row[col] or "").strip()
            if valor:
                con.execute(
                    "INSERT OR IGNORE INTO _r1_predios VALUES (?)", (valor,)
                )
                filas += 1
    con.commit()
    return filas


def limpiar_r1(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS _r1_predios")
    con.commit()


def reset_qa_table(con: sqlite3.Connection,
                   categorias: Iterable[str] | None = None) -> None:
    """Limpia qa_errores. Si se pasa `categorias`, solo borra las filas
    de esas categorías; útil cuando el usuario re-valida un subconjunto."""
    if categorias is None:
        con.execute("DELETE FROM qa_errores")
    else:
        placeholders = ",".join("?" * len(list(categorias)))
        con.execute(
            f"DELETE FROM qa_errores WHERE categoria IN ({placeholders})",
            list(categorias),
        )
    con.commit()


# --------- Descubrimiento de reglas ----------------------------------------

@dataclass
class Regla:
    id: str
    descripcion: str
    severidad: str           # 'error' | 'advertencia'
    sql: str
    categoria: str           # se infiere del nombre del archivo
    fuente: str = ""         # ruta del archivo, útil para mensajes
    parametros: dict = field(default_factory=dict)


def _cargar_modulo(path: Path):
    """Importa un .py por ruta absoluta sin tocar sys.modules globalmente."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {path}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def descubrir_reglas(dir_reglas: Path | str | None = None) -> list[Regla]:
    """Recorre `<dir_reglas>/*.py` y consolida todas las listas REGLAS.

    Si `dir_reglas` es None, usa `DIR_REGLAS` (autodetectada relativa a
    `helpers.py`). Para usos desde Processing Toolbox, pasa la ruta
    explícita seleccionada por el usuario."""
    target = Path(dir_reglas) if dir_reglas else DIR_REGLAS
    if not target.exists():
        return []
    # garantizamos que el directorio esté en sys.path para que las reglas
    # puedan hacer `from helpers import ...` y `from <archivo> import ...`
    parent = str(target.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    reglas: list[Regla] = []
    for archivo in sorted(target.glob("*.py")):
        if archivo.name.startswith("_"):
            continue
        modulo = _cargar_modulo(archivo)
        items = getattr(modulo, "REGLAS", None)
        if not items:
            continue
        categoria_default = archivo.stem
        for d in items:
            reglas.append(
                Regla(
                    id=d["id"],
                    descripcion=d["descripcion"],
                    severidad=d.get("severidad", "error"),
                    sql=d["sql"],
                    categoria=d.get("categoria", categoria_default),
                    fuente=str(archivo),
                    parametros=d.get("parametros", {}),
                )
            )
    return reglas


def descubrir_categorias(dir_reglas: Path | str | None = None) -> list[str]:
    """Lista categorías disponibles, en orden alfabético, para mostrarlas
    en el diálogo del algoritmo de Processing."""
    return sorted({r.categoria for r in descubrir_reglas(dir_reglas)})


# --------- Ejecutor --------------------------------------------------------

INSERT_ERROR_SQL = """
INSERT INTO qa_errores
    (regla_id, regla_descripcion, categoria, severidad,
     tabla, t_id, clave_negocio, mensaje, valor_actual, valor_esperado,
     fecha_validacion)
VALUES
    (:regla_id, :regla_descripcion, :categoria, :severidad,
     :tabla, :t_id, :clave_negocio, :mensaje, :valor_actual, :valor_esperado,
     :fecha_validacion)
"""


class _Feedback:
    """Fallback minimal cuando no hay QgsProcessingFeedback (consola)."""
    def isCanceled(self): return False
    def setProgress(self, _): pass
    def pushInfo(self, s): print(s)
    def pushWarning(self, s): print("WARN:", s)
    def reportError(self, s, *args, **kwargs): print("ERROR:", s)


def correr_regla(con: sqlite3.Connection, regla: Regla) -> int:
    ahora = datetime.now().isoformat(timespec="seconds")
    sql = regla.sql.format(**regla.parametros) if regla.parametros else regla.sql
    cur = con.execute(sql)
    filas = cur.fetchall()
    if not filas:
        return 0
    payload = [
        {
            "regla_id": regla.id,
            "regla_descripcion": regla.descripcion,
            "categoria": regla.categoria,
            "severidad": regla.severidad,
            "tabla": tabla,
            "t_id": t_id,
            "clave_negocio": clave,
            "mensaje": mensaje,
            "valor_actual": valor_act,
            "valor_esperado": valor_esp,
            "fecha_validacion": ahora,
        }
        for (tabla, t_id, clave, mensaje, valor_act, valor_esp) in filas
    ]
    con.executemany(INSERT_ERROR_SQL, payload)
    con.commit()
    return len(filas)


def run_rules(gpkg: Path,
              categorias: Iterable[str] | None = None,
              severidades: Iterable[str] | None = None,
              dir_reglas: Path | str | None = None,
              r1_csv: Path | str | None = None,
              feedback=None) -> dict:
    """Punto de entrada único. Lo usan el toolbox y el script de consola.

    Devuelve un dict con: total, errores, advertencias, por_regla.

    Parámetros opcionales:
        r1_csv: ruta a un CSV con números prediales del Registro 1
                (insumo inicial/periódico). Requerido para las reglas
                de la categoría 'novedades' que cruzan contra el R1.
    """
    fb = feedback or _Feedback()
    reglas = descubrir_reglas(dir_reglas)
    if categorias:
        cats = set(categorias)
        reglas = [r for r in reglas if r.categoria in cats]
    if severidades:
        sevs = set(severidades)
        reglas = [r for r in reglas if r.severidad in sevs]

    if not reglas:
        fb.pushWarning("No hay reglas para ejecutar con los filtros indicados.")
        return {"total": 0, "errores": 0, "advertencias": 0, "por_regla": []}

    fb.pushInfo(f"GeoPackage: {gpkg}")
    fb.pushInfo(f"Reglas a evaluar: {len(reglas)}")

    con = connect(Path(gpkg))
    try:
        ensure_qa_table(con)

        if r1_csv:
            try:
                n_r1 = cargar_r1(con, r1_csv)
                fb.pushInfo(f"R1 cargado: {n_r1} predios desde {r1_csv}")
            except (FileNotFoundError, ValueError) as exc:
                fb.reportError(f"Error cargando R1: {exc}")

        # solo borramos lo que vamos a recomputar, para corridas parciales
        cats_a_limpiar = sorted({r.categoria for r in reglas})
        reset_qa_table(con, categorias=cats_a_limpiar)

        por_regla: list[tuple[str, str, str, int]] = []
        for i, r in enumerate(reglas, start=1):
            if fb.isCanceled():
                fb.pushWarning("Cancelado por el usuario.")
                break
            try:
                n = correr_regla(con, r)
            except sqlite3.Error as exc:
                fb.reportError(f"[{r.id}] SQL falló: {exc}")
                n = -1
            por_regla.append((r.id, r.categoria, r.severidad, n))
            estado = "OK" if n == 0 else ("ERR" if n < 0 else "FAIL")
            fb.pushInfo(f"  {estado:<4} {r.id:<8} {r.severidad:<12} "
                        f"violaciones={n:<5}  {r.descripcion}")
            fb.setProgress(int(100 * i / len(reglas)))

        errores = sum(n for _, _, sev, n in por_regla if sev == "error" and n > 0)
        adv = sum(n for _, _, sev, n in por_regla if sev == "advertencia" and n > 0)
        total = errores + adv

        fb.pushInfo("")
        fb.pushInfo(f"Total errores:      {errores}")
        fb.pushInfo(f"Total advertencias: {adv}")
        fb.pushInfo(f"Total violaciones:  {total}")
        return {
            "total": total,
            "errores": errores,
            "advertencias": adv,
            "por_regla": por_regla,
        }
    finally:
        limpiar_r1(con)
        con.close()
