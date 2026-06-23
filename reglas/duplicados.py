"""Reglas de unicidad: número predial y matrícula inmobiliaria.

Categoría: `duplicados`.
"""

REGLAS = [
    {
        "id": "R-17",
        "descripcion": "Los registros de número predial no deben tener duplicados",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'numero_predial_nacional duplicado',
                   p.numero_predial_nacional,
                   'único'
            FROM cca_predio p
            WHERE p.numero_predial_nacional IS NOT NULL
              AND p.numero_predial_nacional IN (
                   SELECT numero_predial_nacional FROM cca_predio
                   WHERE numero_predial_nacional IS NOT NULL
                   GROUP BY numero_predial_nacional
                   HAVING COUNT(*) > 1
              )
        """,
    },
    {
        "id": "R-18",
        "descripcion": "folio_matricula no debe estar asociado a más de un número predial",
        # La regla original indica "pueden existir excepciones".
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'folio_matricula compartido por varios predios',
                   p.folio_matricula,
                   'único o justificar excepción'
            FROM cca_predio p
            WHERE p.folio_matricula IS NOT NULL
              AND TRIM(p.folio_matricula) <> ''
              AND p.folio_matricula IN (
                   SELECT folio_matricula FROM cca_predio
                   WHERE folio_matricula IS NOT NULL
                     AND TRIM(folio_matricula) <> ''
                   GROUP BY folio_matricula
                   HAVING COUNT(*) > 1
              )
        """,
    },
]
