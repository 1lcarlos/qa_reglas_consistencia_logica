"""Reglas sobre el número predial nacional y su coherencia con departamento/municipio.

Categoría: `numero_predial` (derivada del nombre de este archivo).

Convenciones:
- substr(np, k, n) extrae n caracteres desde la posición k (1-indexed).
- Códigos de condicion_predio (proyecto QGIS):
    0=NPH, 1=PH.Matriz, 2=PH.Unidad_Predial,
    3=Condominio.Matriz, 4=Condominio.Unidad_Predial,
    5=Mejora, 6=Parque_Cementerio.Matriz, 7=Parque_Cementerio.Unidad_Predial,
    8=Via, 9=Informal, 10=Bien_Uso_Publico.

Cada regla debe SELECT (tabla, t_id, clave_negocio, mensaje, valor_actual, valor_esperado).
"""

# Valores esperados de departamento/municipio. Si en el futuro hay multimunicipio,
# las reglas R-15/R-16 cambiarán para tomar el valor por registro desde
# cca_predio.departamento_municipio (ya lo hacen como fallback).
DEPARTAMENTO_ESPERADO = "25"
MUNICIPIO_ESPERADO = "506"

REGLAS = [
    {
        "id": "R-01",
        "descripcion": "Posiciones 22-30 deben ser '000000000' para condición NPH",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 000000000 para NPH',
                   substr(numero_predial_nacional, 22, 9),
                   '000000000'
            FROM cca_predio
            WHERE condicion_predio = '0'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '000000000'
        """,
    },
    {
        "id": "R-02",
        "descripcion": "Posiciones 22-30 deben ser '300000000' para Bien_Uso_Publico",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 300000000 para Bien de Uso Público',
                   substr(numero_predial_nacional, 22, 9),
                   '300000000'
            FROM cca_predio
            WHERE condicion_predio = '10'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '300000000'
        """,
    },
    {
        "id": "R-03",
        "descripcion": "Posiciones 22-30 deben ser '400000000' para Vía",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 400000000 para Vía',
                   substr(numero_predial_nacional, 22, 9),
                   '400000000'
            FROM cca_predio
            WHERE condicion_predio = '8'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '400000000'
        """,
    },
    {
        "id": "R-04",
        "descripcion": "Posiciones 22-30 deben ser '700000000' para Parque Cementerio",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 700000000 para Parque Cementerio',
                   substr(numero_predial_nacional, 22, 9),
                   '700000000'
            FROM cca_predio
            WHERE condicion_predio IN ('6', '7')
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '700000000'
        """,
    },
    {
        "id": "R-05",
        "descripcion": "Posiciones 22-30 deben ser '200000000' para Informal",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 200000000 para Informal',
                   substr(numero_predial_nacional, 22, 9),
                   '200000000'
            FROM cca_predio
            WHERE condicion_predio = '9'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '200000000'
        """,
    },
    {
        "id": "R-08-A",
        "descripcion": "numero_predial debe tener 30 dígitos en cca_predio",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'numero_predial_nacional debe tener exactamente 30 caracteres',
                   CAST(length(numero_predial_nacional) AS TEXT),
                   '30'
            FROM cca_predio
            WHERE numero_predial_nacional IS NOT NULL
              AND length(numero_predial_nacional) <> 30
        """,
    },
    {
        "id": "R-08-B",
        "descripcion": "numero_predial debe tener 30 dígitos en cca_estructuranovedadnumeropredial",
        "severidad": "error",
        "sql": """
            SELECT 'cca_estructuranovedadnumeropredial', T_Id, numero_predial,
                   'numero_predial debe tener exactamente 30 caracteres',
                   CAST(length(numero_predial) AS TEXT),
                   '30'
            FROM cca_estructuranovedadnumeropredial
            WHERE numero_predial IS NOT NULL
              AND length(numero_predial) <> 30
        """,
    },
    {
        "id": "R-09",
        "descripcion": "Posiciones 14-17 y 18-21 del número predial no pueden ser '0000'",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE
                     WHEN substr(numero_predial_nacional, 14, 4) = '0000'
                          AND substr(numero_predial_nacional, 18, 4) = '0000'
                       THEN 'Posiciones 14-17 y 18-21 son 0000'
                     WHEN substr(numero_predial_nacional, 14, 4) = '0000'
                       THEN 'Posiciones 14-17 son 0000'
                     ELSE 'Posiciones 18-21 son 0000'
                   END,
                   substr(numero_predial_nacional, 14, 4) || '/' ||
                   substr(numero_predial_nacional, 18, 4),
                   '<>0000 / <>0000'
            FROM cca_predio
            WHERE numero_predial_nacional IS NOT NULL
              AND ( substr(numero_predial_nacional, 14, 4) = '0000'
                 OR substr(numero_predial_nacional, 18, 4) = '0000' )
        """,
    },
    {
        "id": "R-10",
        "descripcion": "Posiciones 22-30 deben ser '900000000' para PH.Matriz",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 900000000 para PH.Matriz',
                   substr(numero_predial_nacional, 22, 9),
                   '900000000'
            FROM cca_predio
            WHERE condicion_predio = '1'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '900000000'
        """,
    },
    {
        "id": "R-11",
        "descripcion": "PH.Unidad_Predial: pos 22='9', pos 23-24<>'00', pos 25-26<>'00', pos 27-30<>'0000'",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Patrón inválido en posiciones 22-30 para PH.Unidad_Predial',
                   substr(numero_predial_nacional, 22, 9),
                   '9 + (23-24<>00) + (25-26<>00) + (27-30<>0000)'
            FROM cca_predio
            WHERE condicion_predio = '2'
              AND numero_predial_nacional IS NOT NULL
              AND NOT (
                    substr(numero_predial_nacional, 22, 1) = '9'
                AND substr(numero_predial_nacional, 23, 2) <> '00'
                AND substr(numero_predial_nacional, 25, 2) <> '00'
                AND substr(numero_predial_nacional, 27, 4) <> '0000'
              )
        """,
    },
    {
        "id": "R-12",
        "descripcion": "Posiciones 22-30 deben ser '800000000' para Condominio.Matriz",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 22-30 deben ser 800000000 para Condominio.Matriz',
                   substr(numero_predial_nacional, 22, 9),
                   '800000000'
            FROM cca_predio
            WHERE condicion_predio = '3'
              AND numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 9) <> '800000000'
        """,
    },
    {
        "id": "R-13",
        "descripcion": "Condominio.Unidad_Predial: pos 22-26='80000' y pos 27-30<>'0000'",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Patrón inválido en posiciones 22-30 para Condominio.Unidad_Predial',
                   substr(numero_predial_nacional, 22, 9),
                   '80000 + (27-30<>0000)'
            FROM cca_predio
            WHERE condicion_predio = '4'
              AND numero_predial_nacional IS NOT NULL
              AND NOT (
                    substr(numero_predial_nacional, 22, 5) = '80000'
                AND substr(numero_predial_nacional, 27, 4) <> '0000'
              )
        """,
    },
    {
        "id": "R-14",
        "descripcion": "Posición 22 del número predial no debe ser '1', '5' ni '6'",
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posición 22 contiene un valor prohibido (1, 5 o 6)',
                   substr(numero_predial_nacional, 22, 1),
                   'no ser 1, 5, 6'
            FROM cca_predio
            WHERE numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 22, 1) IN ('1', '5', '6')
        """,
    },
    {
        "id": "R-15",
        "descripcion": "Posiciones 1-2 del número predial deben corresponder al Departamento",
        "categoria": "coherencia_geografica",
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 1-2 no corresponden al Departamento {DEPARTAMENTO_ESPERADO}',
                   substr(numero_predial_nacional, 1, 2),
                   COALESCE(substr(departamento_municipio, 1, 2), '{DEPARTAMENTO_ESPERADO}')
            FROM cca_predio
            WHERE numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 1, 2) <>
                  COALESCE(substr(departamento_municipio, 1, 2), '{DEPARTAMENTO_ESPERADO}')
        """,
    },
    {
        "id": "R-16",
        "descripcion": "Posiciones 3-5 del número predial deben corresponder al Municipio",
        "categoria": "coherencia_geografica",
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   'Posiciones 3-5 no corresponden al Municipio {MUNICIPIO_ESPERADO}',
                   substr(numero_predial_nacional, 3, 3),
                   COALESCE(substr(departamento_municipio, 3, 3), '{MUNICIPIO_ESPERADO}')
            FROM cca_predio
            WHERE numero_predial_nacional IS NOT NULL
              AND substr(numero_predial_nacional, 3, 3) <>
                  COALESCE(substr(departamento_municipio, 3, 3), '{MUNICIPIO_ESPERADO}')
        """,
    },
]
