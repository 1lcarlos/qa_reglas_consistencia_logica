"""Reglas de coherencia entre datos registrales y área registral.

Categoría: `registral`.
"""

REGLAS = [
    {
        "id": "R-24-A",
        "descripcion": (
            "Si Codigo_ORIP y Matricula_Inmobiliaria no están diligenciados, "
            "Area_Registral_M2 debe ser cero"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Sin ORIP ni Matrícula pero con área registral > 0',
                   printf('orip=%s | matricula=%s | area=%s',
                          COALESCE(codigo_orip, ''),
                          COALESCE(folio_matricula, ''),
                          COALESCE(CAST(area_registral_m2 AS TEXT), 'NULL')),
                   'area_registral_m2 = 0'
            FROM cca_predio
            WHERE (codigo_orip IS NULL OR TRIM(codigo_orip) = '')
              AND (folio_matricula IS NULL OR TRIM(folio_matricula) = '')
              AND area_registral_m2 IS NOT NULL
              AND area_registral_m2 > 0
        """,
    },
    {
        "id": "R-24-B",
        "descripcion": (
            "Si Area_Registral_M2 > 0, los campos Codigo_ORIP y "
            "Matricula_Inmobiliaria deben estar diligenciados"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Área registral > 0 pero falta ORIP y/o Matrícula',
                   printf('orip=%s | matricula=%s | area=%s',
                          COALESCE(codigo_orip, ''),
                          COALESCE(folio_matricula, ''),
                          CAST(area_registral_m2 AS TEXT)),
                   'orip y matrícula diligenciados'
            FROM cca_predio
            WHERE area_registral_m2 IS NOT NULL
              AND area_registral_m2 > 0
              AND ( codigo_orip IS NULL OR TRIM(codigo_orip) = ''
                 OR folio_matricula IS NULL OR TRIM(folio_matricula) = '' )
        """,
    },
]
