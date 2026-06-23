"""Reglas estructurales para PH y Condominio (R-26 a R-44).

Categoría: `ph_condominio`.

Las reglas chequean:
  * Coeficientes de copropiedad (R-26, R-27).
  * Que solo matrices tengan campos PH/Condo diligenciados (R-28).
  * Mínimo de unidades para constituir PH/Condominio (R-29).
  * Unidades huérfanas, sin matriz asociada (R-30).
  * Áreas totales y conteos para PH.Matriz (R-31 a R-36).
  * Áreas totales y conteos para Condominio.Matriz (R-37 a R-44).

Tolerancias paramétricas (configurables en `qa/helpers.py`):
  * Si área esperada > UMBRAL_M2 (500):  ±PORCENTAJE * esperada (5%).
  * Si área esperada ≤ UMBRAL_M2:        ±ABSOLUTA_M2 (2 m²).

Códigos de condicion_predio relevantes:
    1 = PH.Matriz
    2 = PH.Unidad_Predial
    3 = Condominio.Matriz
    4 = Condominio.Unidad_Predial
"""

from helpers import (
    TOLERANCIA_AREA_PORCENTAJE as _PCT,
    TOLERANCIA_AREA_ABSOLUTA_M2 as _ABS,
    TOLERANCIA_AREA_UMBRAL_M2 as _UMBRAL,
)


def _fuera_tol(cap: str, esp: str) -> str:
    """Fragmento SQL booleano: True si |cap - esp| supera la tolerancia."""
    return (
        f"ABS(COALESCE({cap}, 0) - COALESCE({esp}, 0)) > "
        f"CASE WHEN COALESCE({esp}, 0) > {_UMBRAL} "
        f"THEN {_PCT} * COALESCE({esp}, 0) ELSE {_ABS} END"
    )


# Subconsultas reutilizables
# --------------------------------------------------------------------
# Área geográfica del terreno del propio predio matriz
_AREA_TERRENO_MATRIZ = "(SELECT COALESCE(SUM(t.AREA),0) FROM cca_terreno t WHERE t.predio = p.T_Id)"

# Suma de áreas geográficas de los terrenos de las unidades hijas
_AREA_TERRENOS_HIJAS = """
    (SELECT COALESCE(SUM(t.AREA),0)
       FROM cca_predio h
       JOIN cca_terreno t ON t.predio = h.T_Id
      WHERE h.numero_predial_matriz = p.numero_predial_nacional)
"""

# Suma de áreas construidas declaradas de UCs asociadas al propio matriz
_AREA_CONSTR_MATRIZ = """
    (SELECT COALESCE(SUM(c.area_construida),0)
       FROM cca_unidadconstruccion u
       JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
      WHERE u.predio = p.T_Id)
"""

# Suma de áreas construidas declaradas de UCs asociadas a unidades hijas
_AREA_CONSTR_HIJAS = """
    (SELECT COALESCE(SUM(c.area_construida),0)
       FROM cca_predio h
       JOIN cca_unidadconstruccion u ON u.predio = h.T_Id
       JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
      WHERE h.numero_predial_matriz = p.numero_predial_nacional)
"""

# Conteo de unidades prediales asociadas al matriz
_NUM_UNIDADES_HIJAS = """
    (SELECT COUNT(*) FROM cca_predio h
      WHERE h.numero_predial_matriz = p.numero_predial_nacional)
"""

# Máximo número de torre (posiciones 25-26 del número predial de cada unidad)
_MAX_TORRE_HIJAS = """
    (SELECT MAX(CAST(substr(h.numero_predial_nacional, 25, 2) AS INTEGER))
       FROM cca_predio h
      WHERE h.numero_predial_matriz = p.numero_predial_nacional)
"""


REGLAS = [
    # ------------------------------------------------------------------
    # COEFICIENTES (R-26, R-27)
    # ------------------------------------------------------------------
    {
        "id": "R-26",
        "descripcion": (
            "La sumatoria de coeficiente_copropiedad de las unidades prediales "
            "asociadas a una matriz PH/Condominio debe ser 1"
        ),
        "severidad": "error",
        "sql": """
            WITH suma AS (
                SELECT m.T_Id AS matriz_tid,
                       m.numero_predial_nacional AS matriz_np,
                       m.condicion_predio,
                       (SELECT COALESCE(SUM(h.coeficiente_copropiedad), 0)
                          FROM cca_predio h
                         WHERE h.numero_predial_matriz = m.numero_predial_nacional
                           AND h.condicion_predio IN ('2','4')) AS suma_coef,
                       (SELECT COUNT(*) FROM cca_predio h
                         WHERE h.numero_predial_matriz = m.numero_predial_nacional
                           AND h.condicion_predio IN ('2','4')) AS n_unidades
                FROM cca_predio m
                WHERE m.condicion_predio IN ('1','3')
            )
            SELECT 'cca_predio', matriz_tid, matriz_np,
                   'Suma de coeficientes de unidades = ' || ROUND(suma_coef, 4),
                   ROUND(suma_coef, 4),
                   '1.0'
            FROM suma
            WHERE n_unidades > 0
              AND ABS(suma_coef - 1.0) > 0.001
        """,
    },
    {
        "id": "R-27",
        "descripcion": (
            "La sumatoria de area_coeficiente de las unidades prediales debe "
            "igualar el área de terreno del predio matriz"
        ),
        "severidad": "advertencia",  # aplican excepciones Res. 1040
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.condicion_predio,
                       (SELECT COALESCE(SUM(h.area_coeficiente),0)
                          FROM cca_predio h
                         WHERE h.numero_predial_matriz = p.numero_predial_nacional
                           AND h.condicion_predio IN ('2','4')) AS suma_areacoef,
                       {_AREA_TERRENO_MATRIZ} AS area_terreno_geo
                FROM cca_predio p
                WHERE p.condicion_predio IN ('1','3')
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Suma area_coeficiente vs área terreno matriz fuera de tolerancia',
                   printf('suma=%s | geo=%s', ROUND(suma_areacoef,3), ROUND(area_terreno_geo,3)),
                   ROUND(area_terreno_geo, 3)
            FROM calc
            WHERE {_fuera_tol("suma_areacoef", "area_terreno_geo")}
        """,
    },
    # ------------------------------------------------------------------
    # PRESENCIA / AUSENCIA DE CAMPOS PH/Condo (R-28)
    # ------------------------------------------------------------------
    {
        "id": "R-28",
        "descripcion": (
            "Solo los predios PH.Matriz o Condominio.Matriz deben tener "
            "diligenciados los campos PH/Condo (área totales, num. torres, etc.); "
            "en los demás esos campos deben estar nulos"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Predio no-matriz con campos PH/Condo diligenciados',
                   printf('aTT=%s aTTP=%s aTC=%s torres=%s u_priv=%s',
                          COALESCE(CAST(area_total_terreno AS TEXT),'NULL'),
                          COALESCE(CAST(area_total_terreno_privada AS TEXT),'NULL'),
                          COALESCE(CAST(area_total_construida AS TEXT),'NULL'),
                          COALESCE(CAST(numero_torres AS TEXT),'NULL'),
                          COALESCE(CAST(total_unidades_privadas AS TEXT),'NULL')),
                   'todos NULL'
            FROM cca_predio
            WHERE condicion_predio NOT IN ('1', '3')
              AND ( area_total_terreno IS NOT NULL
                 OR area_total_terreno_privada IS NOT NULL
                 OR area_total_construida IS NOT NULL
                 OR area_total_construida_privada IS NOT NULL
                 OR area_total_construida_comun IS NOT NULL
                 OR numero_torres IS NOT NULL
                 OR total_unidades_privadas IS NOT NULL )
        """,
    },
    # ------------------------------------------------------------------
    # CARDINALIDAD (R-29, R-30)
    # ------------------------------------------------------------------
    {
        "id": "R-29",
        "descripcion": (
            "Una matriz PH/Condominio no puede tener una sola unidad "
            "predial asociada"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', m.T_Id, m.numero_predial_nacional,
                   'Matriz PH/Condominio con solo 1 unidad asociada',
                   '1',
                   '>=2'
            FROM cca_predio m
            WHERE m.condicion_predio IN ('1','3')
              AND ( SELECT COUNT(*) FROM cca_predio h
                     WHERE h.numero_predial_matriz = m.numero_predial_nacional
                       AND h.condicion_predio IN ('2','4') ) = 1
        """,
    },
    {
        "id": "R-30",
        "descripcion": (
            "Una unidad PH/Condominio debe tener un predio matriz existente "
            "y con condición coherente"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', u.T_Id, u.numero_predial_nacional,
                   CASE
                     WHEN u.numero_predial_matriz IS NULL
                          OR TRIM(u.numero_predial_matriz) = ''
                       THEN 'Unidad sin numero_predial_matriz diligenciado'
                     WHEN NOT EXISTS (
                          SELECT 1 FROM cca_predio m
                           WHERE m.numero_predial_nacional = u.numero_predial_matriz)
                       THEN 'numero_predial_matriz no existe en cca_predio'
                     ELSE 'numero_predial_matriz existe pero su condicion_predio no es matriz coherente'
                   END,
                   COALESCE(u.numero_predial_matriz, 'NULL'),
                   CASE u.condicion_predio
                     WHEN '2' THEN 'matriz con condicion=1 (PH.Matriz)'
                     WHEN '4' THEN 'matriz con condicion=3 (Condominio.Matriz)'
                   END
            FROM cca_predio u
            WHERE u.condicion_predio IN ('2','4')
              AND (
                   u.numero_predial_matriz IS NULL
                OR TRIM(u.numero_predial_matriz) = ''
                OR NOT EXISTS (
                       SELECT 1 FROM cca_predio m
                        WHERE m.numero_predial_nacional = u.numero_predial_matriz
                          AND ( (u.condicion_predio='2' AND m.condicion_predio='1')
                             OR (u.condicion_predio='4' AND m.condicion_predio='3') )
                   )
              )
        """,
    },
    # ------------------------------------------------------------------
    # ÁREAS PH.Matriz (R-31 a R-36)
    # ------------------------------------------------------------------
    {
        "id": "R-31-A",
        "descripcion": (
            "PH.Matriz: area_total_terreno debe corresponder al área "
            "geográfica del predio matriz"
        ),
        "severidad": "advertencia",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'area_total_terreno difiere del área geográfica del matriz',
                   COALESCE(CAST(p.area_total_terreno AS TEXT),'NULL'),
                   CAST(ROUND({_AREA_TERRENO_MATRIZ}, 3) AS TEXT)
            FROM cca_predio p
            WHERE p.condicion_predio = '1'
              AND {_fuera_tol("p.area_total_terreno", _AREA_TERRENO_MATRIZ)}
        """,
    },
    # R-31-B (PH.Matriz: area_total_terreno_común = área geográfica del matriz)
    # no se implementa: en el modelo cca_predio no existe una columna separada
    # "area_total_terreno_comun". La cobertura semántica se da vía R-31-A + R-31-C.
    {
        "id": "R-31-C",
        "descripcion": "PH.Matriz: area_total_terreno_privada debe ser 0",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_terreno_privada debe ser 0 en PH.Matriz',
                   COALESCE(CAST(area_total_terreno_privada AS TEXT),'NULL'),
                   '0'
            FROM cca_predio
            WHERE condicion_predio = '1'
              AND area_total_terreno_privada IS NOT NULL
              AND area_total_terreno_privada <> 0
        """,
    },
    {
        "id": "R-32",
        "descripcion": (
            "PH.Matriz: area_total_construida = suma de áreas de unidades "
            "de construcción de las unidades + del propio matriz"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida,
                       ({_AREA_CONSTR_HIJAS} + {_AREA_CONSTR_MATRIZ}) AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '1'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida difiere de la suma de UCs (privadas + matriz)',
                   COALESCE(CAST(area_total_construida AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida", "esperado")}
        """,
    },
    {
        "id": "R-33",
        "descripcion": (
            "PH.Matriz: area_total_construida_privada = suma de áreas de "
            "unidades de construcción asociadas a las unidades prediales"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida_privada,
                       {_AREA_CONSTR_HIJAS} AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '1'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida_privada difiere de la suma de UCs de unidades',
                   COALESCE(CAST(area_total_construida_privada AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida_privada", "esperado")}
        """,
    },
    {
        "id": "R-34",
        "descripcion": (
            "PH.Matriz: area_total_construida_comun = suma de áreas de UCs "
            "del propio predio matriz"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida_comun,
                       {_AREA_CONSTR_MATRIZ} AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '1'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida_comun difiere de la suma de UCs del matriz',
                   COALESCE(CAST(area_total_construida_comun AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida_comun", "esperado")}
        """,
    },
    {
        "id": "R-35",
        "descripcion": (
            "PH.Matriz: numero_torres = MAX(posiciones 25-26 del número "
            "predial de las unidades asociadas)"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'numero_torres no coincide con el máximo de las posiciones 25-26 de las unidades',
                   COALESCE(CAST(p.numero_torres AS TEXT),'NULL'),
                   COALESCE(CAST({_MAX_TORRE_HIJAS} AS TEXT),'NULL')
            FROM cca_predio p
            WHERE p.condicion_predio = '1'
              AND COALESCE(p.numero_torres, -1) <> COALESCE({_MAX_TORRE_HIJAS}, -1)
        """,
    },
    {
        "id": "R-36",
        "descripcion": "PH.Matriz: total_unidades_privadas = conteo de unidades asociadas",
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'total_unidades_privadas no coincide con el conteo real de unidades',
                   COALESCE(CAST(p.total_unidades_privadas AS TEXT),'NULL'),
                   CAST({_NUM_UNIDADES_HIJAS} AS TEXT)
            FROM cca_predio p
            WHERE p.condicion_predio = '1'
              AND COALESCE(p.total_unidades_privadas, -1) <> {_NUM_UNIDADES_HIJAS}
        """,
    },
    # ------------------------------------------------------------------
    # ÁREAS Condominio.Matriz (R-37 a R-44)
    # ------------------------------------------------------------------
    {
        "id": "R-37",
        "descripcion": (
            "Condominio.Matriz: area_total_terreno = suma del área geográfica "
            "del terreno del matriz + áreas geográficas de los terrenos de las unidades"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_terreno,
                       ({_AREA_TERRENO_MATRIZ} + {_AREA_TERRENOS_HIJAS}) AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '3'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_terreno difiere de (terreno matriz + terrenos unidades)',
                   COALESCE(CAST(area_total_terreno AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_terreno", "esperado")}
        """,
    },
    {
        "id": "R-38",
        "descripcion": (
            "Condominio.Matriz: area_total_terreno_privada = suma de áreas "
            "geográficas de los terrenos de las unidades privadas"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_terreno_privada,
                       {_AREA_TERRENOS_HIJAS} AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '3'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_terreno_privada difiere de la suma de terrenos de unidades',
                   COALESCE(CAST(area_total_terreno_privada AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_terreno_privada", "esperado")}
        """,
    },
    # R-39 (Condominio.Matriz: area_total_terreno_comun = área geográfica del
    # matriz) no se implementa por el mismo motivo que R-31-B: no existe esa
    # columna separada en cca_predio. La validación equivalente queda
    # cubierta por R-37 + R-38.
    {
        "id": "R-40",
        "descripcion": (
            "Condominio.Matriz: area_total_construida = suma de UCs asociadas "
            "a las unidades prediales + al predio matriz"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida,
                       ({_AREA_CONSTR_HIJAS} + {_AREA_CONSTR_MATRIZ}) AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '3'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida difiere de la suma de UCs (unidades + matriz)',
                   COALESCE(CAST(area_total_construida AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida", "esperado")}
        """,
    },
    {
        "id": "R-41",
        "descripcion": (
            "Condominio.Matriz: area_total_construida_privada = suma de UCs "
            "asociadas a las unidades prediales"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida_privada,
                       {_AREA_CONSTR_HIJAS} AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '3'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida_privada difiere de la suma de UCs de unidades',
                   COALESCE(CAST(area_total_construida_privada AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida_privada", "esperado")}
        """,
    },
    {
        "id": "R-42",
        "descripcion": (
            "Condominio.Matriz: area_total_construida_comun = suma de UCs "
            "asociadas al propio Condominio.Matriz"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH calc AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.area_total_construida_comun,
                       {_AREA_CONSTR_MATRIZ} AS esperado
                FROM cca_predio p
                WHERE p.condicion_predio = '3'
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'area_total_construida_comun difiere de la suma de UCs del matriz',
                   COALESCE(CAST(area_total_construida_comun AS TEXT),'NULL'),
                   CAST(ROUND(esperado, 3) AS TEXT)
            FROM calc
            WHERE {_fuera_tol("area_total_construida_comun", "esperado")}
        """,
    },
    {
        "id": "R-43",
        "descripcion": "Condominio.Matriz: numero_torres debe ser 0",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'numero_torres debe ser 0 en Condominio.Matriz',
                   COALESCE(CAST(numero_torres AS TEXT),'NULL'),
                   '0'
            FROM cca_predio
            WHERE condicion_predio = '3'
              AND numero_torres IS NOT NULL
              AND numero_torres <> 0
        """,
    },
    {
        "id": "R-44",
        "descripcion": (
            "Condominio.Matriz: total_unidades_privadas = conteo de unidades asociadas"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'total_unidades_privadas no coincide con el conteo real de unidades',
                   COALESCE(CAST(p.total_unidades_privadas AS TEXT),'NULL'),
                   CAST({_NUM_UNIDADES_HIJAS} AS TEXT)
            FROM cca_predio p
            WHERE p.condicion_predio = '3'
              AND COALESCE(p.total_unidades_privadas, -1) <> {_NUM_UNIDADES_HIJAS}
        """,
    },
]
