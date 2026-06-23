"""Reglas de coherencia entre destinación económica y unidades de construcción.

Categoría: `destinacion_uso`.

Códigos de destinacion_economica (proyecto QGIS):
    5  = Comercial
    7  = Educativo
    9  = Habitacional
    10 = Industrial
    16 = Institucional
    18 = Lote_Urbanizable_No_Urbanizado
    19 = Lote_Urbanizado_No_Construido
    20 = Lote_No_Urbanizable
    24 = Salubridad

Nota sobre "Lote_Rural" (regla 22): el modelo cca_predio del proyecto QGIS
no incluye un código explícito 'Lote_Rural'. R-22 queda como
no-implementada hasta que se aclare la equivalencia con el equipo del
proyecto. R-21 se aplica únicamente sobre Lote_Urbanizado_No_Construido.
"""

REGLAS = [
    {
        "id": "R-21",
        "descripcion": (
            "Predios con destinación Lote_Urbanizado_No_Construido no deben "
            "tener unidades de construcción asociadas"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Lote_Urbanizado_No_Construido con ' ||
                   (SELECT COUNT(*) FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id) ||
                   ' unidad(es) de construcción asociada(s)',
                   CAST((SELECT COUNT(*) FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id) AS TEXT),
                   '0'
            FROM cca_predio p
            WHERE p.destinacion_economica = '19'
              AND EXISTS (SELECT 1 FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id)
        """,
    },
    {
        "id": "R-23",
        "descripcion": (
            "Predios con destinación Comercial, Educativo, Habitacional, "
            "Industrial, Institucional o Salubridad deben tener al menos "
            "una unidad de construcción asociada"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Destinación que exige unidad de construcción no tiene ninguna asociada',
                   '0',
                   '>=1'
            FROM cca_predio p
            WHERE p.destinacion_economica IN ('5', '7', '9', '10', '16', '24')
              AND NOT EXISTS (
                  SELECT 1 FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id
              )
        """,
    },
]
