"""Validador de Reglas Administrativas - Algoritmo de Processing.

DISEÑO DE CARGA:
  QGIS suele COPIAR los scripts añadidos a la Caja de herramientas a
  `~/QGIS3/profiles/default/processing/scripts/`. Eso hace que `__file__`
  apunte a la copia, no al original. Y peor: Python puede tener cacheada
  una versión vieja de `helpers` en `sys.modules` de corridas previas.

  Para evitar ambos problemas, este script NO importa `helpers` a nivel
  de módulo. En su lugar, lo carga dinámicamente por ruta absoluta cada
  vez que se ejecuta, derivando la ubicación de `helpers.py` desde la
  carpeta de reglas que escoge el usuario (helpers.py es hermano de
  reglas/). Esto:
    * Garantiza versión fresca (no cache).
    * No depende de `__file__`.
    * Funciona aunque QGIS copie el script a su carpeta interna.

INSTALACIÓN (una sola vez):
  1. Procesos -> Caja de herramientas (Ctrl+Alt+T).
  2. Ícono Python ("Scripts") -> "Añadir script a la caja de herramientas".
  3. Seleccionar este archivo.
  4. Aparece bajo "QA Catastral" -> "Validar reglas administrativas".

USO:
  Doble clic. El diálogo pide:
    * GeoPackage de captura (.gpkg).
    * Carpeta de reglas (qa/reglas) - autodetecta si puede; si no, navega
      manualmente. helpers.py se espera al lado (../helpers.py).
    * Categorías a evaluar (vacío = todas).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
)
from qgis.PyQt.QtCore import QCoreApplication


# ----------------------------------------------------------------------
# Carga dinámica del motor (helpers.py)
# ----------------------------------------------------------------------

def _load_helpers_from(helpers_path: Path) -> ModuleType:
    """Carga `helpers.py` desde una ruta absoluta y lo deja en sys.modules
    como `helpers` (sobrescribiendo cualquier versión cacheada). También
    deja la carpeta padre en sys.path para que las reglas puedan hacer
    `from helpers import ...`.
    """
    # invalidar cualquier helpers cacheado de corridas previas
    for nombre in ("helpers", "qa_helpers"):
        if nombre in sys.modules:
            del sys.modules[nombre]
    spec = importlib.util.spec_from_file_location("helpers", helpers_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo construir spec para {helpers_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["helpers"] = mod
    spec.loader.exec_module(mod)
    parent = str(helpers_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return mod


def _autodetect_helpers() -> Path | None:
    try:
        c = Path(__file__).resolve().parent / "helpers.py"
        return c if c.exists() else None
    except Exception:
        return None


def _autodetect_rules_dir() -> str:
    try:
        c = Path(__file__).resolve().parent / "reglas"
        if c.exists() and any(c.glob("*.py")):
            return str(c)
    except Exception:
        pass
    return ""


def _autodetect_gpkg() -> str:
    try:
        raiz = Path(__file__).resolve().parent.parent
        for c in sorted(raiz.glob("captura_*.gpkg")):
            return str(c)
    except Exception:
        pass
    return ""


# ----------------------------------------------------------------------
# Algoritmo
# ----------------------------------------------------------------------

class ValidarReglasAdministrativasAlgorithm(QgsProcessingAlgorithm):
    INPUT_GPKG = "INPUT_GPKG"
    RULES_DIR = "RULES_DIR"
    INPUT_R1 = "INPUT_R1"
    CATEGORIAS = "CATEGORIAS"
    OUT_ERRORES = "OUT_ERRORES"
    OUT_ADVERTENCIAS = "OUT_ADVERTENCIAS"
    OUT_RESUMEN = "OUT_RESUMEN"

    def __init__(self):
        super().__init__()
        self._categorias_init: list[str] = []

    # ---- metadatos -----------------------------------------------------

    def tr(self, s: str) -> str:
        return QCoreApplication.translate("ValidarReglasAdministrativas", s)

    def createInstance(self):
        return ValidarReglasAdministrativasAlgorithm()

    def name(self) -> str:
        return "validar_reglas_administrativas"

    def displayName(self) -> str:
        return self.tr("Validar reglas administrativas")

    def group(self) -> str:
        return self.tr("QA Catastral")

    def groupId(self) -> str:
        return "qa_catastral"

    def shortHelpString(self) -> str:
        return self.tr(
            "Aplica el catálogo de reglas administrativas sobre el GeoPackage "
            "de captura y registra cada violación en la tabla `qa_errores`.\n\n"
            "PARÁMETROS:\n"
            "  • GeoPackage: el .gpkg a validar.\n"
            "  • Carpeta de reglas: directorio con los .py del catálogo. Se "
            "espera que `helpers.py` exista en la carpeta padre (estructura "
            "estándar: qa/helpers.py + qa/reglas/<categoria>.py).\n"
            "  • CSV del Registro 1 (opcional): archivo CSV con los números "
            "prediales del insumo inicial o periódico. Requerido para las "
            "reglas de novedades que cruzan contra el R1.\n"
            "  • Categorías: subconjunto a evaluar (vacío = todas).\n\n"
            "Si cambias la carpeta de reglas en el diálogo, el algoritmo "
            "carga `helpers.py` fresco desde la nueva ubicación, evitando "
            "problemas de caché y de copias internas de QGIS."
        )

    # ---- parámetros ----------------------------------------------------

    def initAlgorithm(self, config=None):
        # 1. GeoPackage
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_GPKG,
                self.tr("GeoPackage de captura (.gpkg)"),
                extension="gpkg",
                defaultValue=_autodetect_gpkg(),
            )
        )

        # 2. Carpeta de reglas
        default_rules = _autodetect_rules_dir()
        self.addParameter(
            QgsProcessingParameterFile(
                self.RULES_DIR,
                self.tr("Carpeta de reglas (qa/reglas)"),
                behavior=QgsProcessingParameterFile.Folder,
                defaultValue=default_rules,
            )
        )

        # 3. CSV del Registro 1 (opcional)
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_R1,
                self.tr("CSV del Registro 1 (opcional, para reglas de novedades)"),
                extension="csv",
                optional=True,
            )
        )

        # 4. Multi-select de categorías (se llena con autodetección si es
        # posible, sino con un placeholder). En processAlgorithm se tolera
        # cualquier desfase si el usuario apunta a otra carpeta.
        self._categorias_init = []
        helpers_path = _autodetect_helpers()
        if helpers_path and default_rules:
            try:
                h = _load_helpers_from(helpers_path)
                self._categorias_init = h.descubrir_categorias(default_rules)
            except Exception:
                self._categorias_init = []

        opciones = self._categorias_init or [self.tr("(se descubren al ejecutar)")]
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CATEGORIAS,
                self.tr("Categorías a evaluar (vacío = todas)"),
                options=opciones,
                allowMultiple=True,
                defaultValue=list(range(len(self._categorias_init))),
                optional=True,
            )
        )

        self.addOutput(QgsProcessingOutputNumber(
            self.OUT_ERRORES, self.tr("Errores detectados")))
        self.addOutput(QgsProcessingOutputNumber(
            self.OUT_ADVERTENCIAS, self.tr("Advertencias detectadas")))
        self.addOutput(QgsProcessingOutputString(
            self.OUT_RESUMEN, self.tr("Resumen")))

    # ---- ejecución -----------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        # GeoPackage
        gpkg = self.parameterAsFile(parameters, self.INPUT_GPKG, context)
        if not gpkg or not Path(gpkg).exists():
            raise QgsProcessingException(
                self.tr(f"GeoPackage no encontrado: '{gpkg}'"))

        # Carpeta de reglas
        rules_dir = self.parameterAsFile(parameters, self.RULES_DIR, context)
        if not rules_dir:
            raise QgsProcessingException(self.tr(
                "Debes indicar la carpeta de reglas. Apunta el parámetro "
                "'Carpeta de reglas' a la carpeta `qa/reglas/` del proyecto."
            ))
        rules_path = Path(rules_dir)
        if not rules_path.exists():
            raise QgsProcessingException(self.tr(
                f"La carpeta de reglas no existe: '{rules_path}'"
            ))

        # helpers.py se espera como hermano de la carpeta `reglas/`
        helpers_path = rules_path.parent / "helpers.py"
        if not helpers_path.exists():
            raise QgsProcessingException(self.tr(
                f"No se encontró helpers.py en: '{helpers_path}'\n"
                f"Estructura esperada: <qa>/helpers.py + <qa>/reglas/<cat>.py.\n"
                f"Si tu helpers.py está en otra ruta, copia este script a "
                f"esa carpeta o ajusta la estructura."
            ))

        # Carga fresca del motor desde ruta absoluta (evita el problema de cache)
        feedback.pushInfo(self.tr(f"Cargando motor desde: {helpers_path}"))
        try:
            helpers = _load_helpers_from(helpers_path)
        except Exception as e:
            raise QgsProcessingException(self.tr(
                f"Error al cargar helpers.py: {e}"
            ))

        # Descubrir categorías reales en la carpeta efectiva
        categorias_disponibles = helpers.descubrir_categorias(rules_path)
        if not categorias_disponibles:
            raise QgsProcessingException(self.tr(
                f"No se encontraron reglas en: '{rules_path}'\n"
                f"Verifica que la carpeta contenga archivos .py con una lista REGLAS."
            ))

        feedback.pushInfo(self.tr(f"Carpeta de reglas: {rules_path}"))
        feedback.pushInfo(self.tr(
            f"Categorías encontradas: {', '.join(categorias_disponibles)}"))

        # Filtro de categorías: tolerante a desfases
        idxs = self.parameterAsEnums(parameters, self.CATEGORIAS, context)
        pickeadas_init = [
            self._categorias_init[i] for i in idxs
            if 0 <= i < len(self._categorias_init)
        ]
        pickeadas = [c for c in pickeadas_init if c in categorias_disponibles]
        if not pickeadas:
            if pickeadas_init:
                feedback.pushWarning(self.tr(
                    "Las categorías seleccionadas no existen en la carpeta "
                    "de reglas indicada. Se ejecutarán todas las disponibles."
                ))
            categorias_run = categorias_disponibles
        else:
            categorias_run = pickeadas

        feedback.pushInfo(self.tr(
            f"Categorías a ejecutar: {', '.join(categorias_run)}"))

        # CSV del R1 (opcional)
        r1_csv = self.parameterAsFile(parameters, self.INPUT_R1, context)
        r1_path = Path(r1_csv) if r1_csv and r1_csv.strip() else None
        if r1_path:
            feedback.pushInfo(self.tr(f"CSV del Registro 1: {r1_path}"))

        # Ejecutar
        resumen = helpers.run_rules(
            gpkg=Path(gpkg),
            categorias=categorias_run,
            dir_reglas=rules_path,
            r1_csv=r1_path,
            feedback=feedback,
        )

        feedback.pushInfo("")
        feedback.pushInfo(self.tr(
            "Resultados en la tabla `qa_errores` del GeoPackage. "
            "Si ya está cargada en el proyecto, haz clic derecho -> "
            "Volver a cargar para ver los registros nuevos."
        ))

        return {
            self.OUT_ERRORES: resumen["errores"],
            self.OUT_ADVERTENCIAS: resumen["advertencias"],
            self.OUT_RESUMEN: (
                f"{resumen['total']} violaciones "
                f"({resumen['errores']} errores, {resumen['advertencias']} advertencias)"
            ),
        }
