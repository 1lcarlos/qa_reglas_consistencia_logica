"""Reglas físicas (RF-01 a RF-21).

Categoría: `fisicas`.

Validan coherencia de unidades de construcción, áreas, usos,
plantas, y su relación con la condición y destinación del predio.

Dominios clave:
    condicion_predio:  2=PH.Unidad_Predial, 4=Condominio.Unidad_Predial
    tipo_construccion: 0=Residencial, 1=Comercial, 2=Industrial,
                       3=Institucional, 4=Anexo
    uso_unidad_construccion:
        Residencial (0-14), Comercial (15-38), Industrial (39-42),
        Institucional (44-66), Anexo (67-101)
    Usos PH (con sufijo _en_PH o _En_PH) + Depositos_Lockers:
        0,5,7,8,9,12,14,16,18,22,25,28,31,36,38,40,42,55

Nota: RF-20 y RF-21 usan ST_Area() que solo funciona con SpatiaLite
(disponible en QGIS). Desde consola pura, esas reglas reportarán
error de SQL, lo cual es manejado por el motor.
"""

from helpers import (
    TOLERANCIA_AREA_PORCENTAJE as _PCT,
    TOLERANCIA_AREA_ABSOLUTA_M2 as _ABS,
    TOLERANCIA_AREA_UMBRAL_M2 as _UMBRAL,
)

USOS_PH = "('0','5','7','8','9','12','14','16','18','22','25','28','31','36','38','40','42','55')"

USOS_RESIDENCIAL = "('0','1','2','3','4','5','6','7','8','9','10','11','12','13','14')"
USOS_COMERCIAL = "('15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38')"
USOS_INDUSTRIAL = "('39','40','41','42','43')"
USOS_INSTITUCIONAL = "('44','45','46','47','48','49','50','51','52','53','54','55','56','57','58','59','60','61','62','63','64','65','66')"
USOS_ANEXO = "('67','68','69','70','71','72','73','74','75','76','77','78','79','80','81','82','83','84','85','86','87','88','89','90','91','92','93','94','95','96','97','98','99','100','101')"


def _fuera_tol(cap: str, esp: str) -> str:
    return (
        f"ABS(COALESCE({cap}, 0) - COALESCE({esp}, 0)) > "
        f"CASE WHEN COALESCE({esp}, 0) > {_UMBRAL} "
        f"THEN {_PCT} * COALESCE({esp}, 0) ELSE {_ABS} END"
    )


REGLAS = [
    # ------------------------------------------------------------------
    # PH / CONDOMINIO Y UNIDADES DE CONSTRUCCIÓN (RF-01 a RF-03)
    # ------------------------------------------------------------------
    {
        "id": "RF-01",
        "descripcion": (
            "PH Unidad Predial debe tener unidad de construcción asociada "
            "(excepto parqueaderos/garajes descubiertos o unidades no construidas)"
        ),
        "severidad": "advertencia",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'PH Unidad Predial sin unidad de construcción asociada',
                   '0 UCs',
                   '>=1 UC'
            FROM cca_predio p
            WHERE p.condicion_predio = '2'
              AND NOT EXISTS (
                  SELECT 1 FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id
              )
        """,
    },
    {
        "id": "RF-02",
        "descripcion": (
            "Unidades en PH/Condominio deben relacionar usos específicos "
            "de PH o Depositos_Lockers"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC en PH/Condominio con uso no específico de PH',
                   c.uso_unidad_construccion,
                   'uso PH o Depositos_Lockers'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE p.condicion_predio IN ('2', '4')
              AND c.uso_unidad_construccion NOT IN {USOS_PH}
        """,
    },
    {
        "id": "RF-03",
        "descripcion": (
            "Unidades en predios sin condición PH/Condominio no deben "
            "relacionar usos de PH"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC en predio no-PH/Condo con uso específico de PH',
                   c.uso_unidad_construccion,
                   'uso no-PH'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE p.condicion_predio NOT IN ('2', '4')
              AND c.uso_unidad_construccion IN {USOS_PH}
        """,
    },
    # ------------------------------------------------------------------
    # INTEGRIDAD REFERENCIAL UC (RF-04)
    # ------------------------------------------------------------------
    {
        "id": "RF-04",
        "descripcion": (
            "Cada unidad de construcción debe estar relacionada con un "
            "solo predio"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_unidadconstruccion', u.T_Id,
                   COALESCE(CAST(u.predio AS TEXT), 'NULL'),
                   CASE
                     WHEN u.predio IS NULL
                       THEN 'UC sin predio asociado'
                     WHEN NOT EXISTS (SELECT 1 FROM cca_predio p WHERE p.T_Id = u.predio)
                       THEN 'UC asociada a predio inexistente'
                     ELSE 'Error de integridad'
                   END,
                   COALESCE(CAST(u.predio AS TEXT), 'NULL'),
                   'predio válido'
            FROM cca_unidadconstruccion u
            WHERE u.predio IS NULL
               OR NOT EXISTS (SELECT 1 FROM cca_predio p WHERE p.T_Id = u.predio)
        """,
    },
    # ------------------------------------------------------------------
    # ÁREA MÍNIMA TERRENO (RF-05)
    # ------------------------------------------------------------------
    {
        "id": "RF-05",
        "descripcion": (
            "No deben existir polígonos de terreno menores a 2 m² "
            "(aplican excepciones)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_terreno', t.T_Id,
                   COALESCE(p.numero_predial_nacional, 'SIN PREDIO'),
                   'Terreno con área menor a 2 m²',
                   CAST(ROUND(t.AREA, 4) AS TEXT),
                   '>= 2 m²'
            FROM cca_terreno t
            LEFT JOIN cca_predio p ON p.T_Id = t.predio
            WHERE t.AREA IS NOT NULL
              AND t.AREA < 2.0
        """,
    },
    # ------------------------------------------------------------------
    # IDENTIFICADOR DE UC (RF-06)
    # ------------------------------------------------------------------
    {
        "id": "RF-06",
        "descripcion": (
            "El identificador de UC debe ser único por predio y debe "
            "iniciar en 'A' con continuidad alfabética"
        ),
        "severidad": "error",
        "sql": """
            WITH ids_por_predio AS (
                SELECT u.predio,
                       c.identificador,
                       COUNT(*) AS n
                FROM cca_unidadconstruccion u
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                GROUP BY u.predio, c.identificador
            ),
            primer_id AS (
                SELECT u.predio,
                       MIN(c.identificador) AS primer
                FROM cca_unidadconstruccion u
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                GROUP BY u.predio
            )
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Primer identificador de UC no es A',
                   pi.primer,
                   'A'
            FROM primer_id pi
            JOIN cca_predio p ON p.T_Id = pi.predio
            WHERE pi.primer <> 'A'
        """,
    },
    # ------------------------------------------------------------------
    # COHERENCIA TIPO CONSTRUCCIÓN ↔ USO (RF-07 a RF-11)
    # ------------------------------------------------------------------
    {
        "id": "RF-07",
        "descripcion": (
            "UC tipo Anexo solo debe asociar usos del dominio Anexo"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC tipo Anexo con uso no-Anexo',
                   c.uso_unidad_construccion,
                   'uso Anexo (67-101)'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE c.tipo_construccion = '4'
              AND c.uso_unidad_construccion NOT IN {USOS_ANEXO}
        """,
    },
    {
        "id": "RF-08",
        "descripcion": (
            "UC tipo Comercial solo debe asociar usos del dominio Comercial"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC tipo Comercial con uso no-Comercial',
                   c.uso_unidad_construccion,
                   'uso Comercial (15-38)'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE c.tipo_construccion = '1'
              AND c.uso_unidad_construccion NOT IN {USOS_COMERCIAL}
        """,
    },
    {
        "id": "RF-09",
        "descripcion": (
            "UC tipo Industrial solo debe asociar usos del dominio Industrial"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC tipo Industrial con uso no-Industrial',
                   c.uso_unidad_construccion,
                   'uso Industrial (39-43)'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE c.tipo_construccion = '2'
              AND c.uso_unidad_construccion NOT IN {USOS_INDUSTRIAL}
        """,
    },
    {
        "id": "RF-10",
        "descripcion": (
            "UC tipo Institucional solo debe asociar usos del dominio "
            "Institucional"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC tipo Institucional con uso no-Institucional',
                   c.uso_unidad_construccion,
                   'uso Institucional (44-66)'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE c.tipo_construccion = '3'
              AND c.uso_unidad_construccion NOT IN {USOS_INSTITUCIONAL}
        """,
    },
    {
        "id": "RF-11",
        "descripcion": (
            "UC tipo Residencial solo debe asociar usos del dominio "
            "Residencial"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'UC tipo Residencial con uso no-Residencial',
                   c.uso_unidad_construccion,
                   'uso Residencial (0-14)'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE c.tipo_construccion = '0'
              AND c.uso_unidad_construccion NOT IN {USOS_RESIDENCIAL}
        """,
    },
    # ------------------------------------------------------------------
    # PLANTA DE UBICACIÓN (RF-12)
    # ------------------------------------------------------------------
    {
        "id": "RF-12",
        "descripcion": (
            "La planta de ubicación de la UC no puede ser cero ni negativa"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_unidadconstruccion', u.T_Id,
                   p.numero_predial_nacional,
                   'planta_ubicacion es 0 o negativa',
                   CAST(u.planta_ubicacion AS TEXT),
                   '> 0'
            FROM cca_unidadconstruccion u
            JOIN cca_predio p ON p.T_Id = u.predio
            WHERE u.planta_ubicacion <= 0
        """,
    },
    # ------------------------------------------------------------------
    # DESTINACIÓN VS TIPO CONSTRUCCIÓN PREDOMINANTE (RF-13 a RF-16)
    # ------------------------------------------------------------------
    {
        "id": "RF-13",
        "descripcion": (
            "Predios con destinación Habitacional deben tener al menos "
            "una UC Residencial predominante en área construida"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH areas AS (
                SELECT p.T_Id, p.numero_predial_nacional,
                       SUM(CASE WHEN c.tipo_construccion = '0'
                                THEN c.area_construida ELSE 0 END) AS area_residencial,
                       SUM(c.area_construida) AS area_total,
                       SUM(CASE WHEN c.tipo_construccion = '0' THEN 1 ELSE 0 END) AS n_residencial
                FROM cca_predio p
                JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                WHERE p.destinacion_economica = '9'
                GROUP BY p.T_Id
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE
                     WHEN n_residencial = 0
                       THEN 'Predio Habitacional sin UC Residencial'
                     ELSE 'UC Residencial no predominante en área'
                   END,
                   printf('resid=%s total=%s', ROUND(area_residencial,2), ROUND(area_total,2)),
                   'UC Residencial predominante'
            FROM areas
            WHERE n_residencial = 0
               OR (area_total > 0 AND area_residencial <= area_total * 0.5)
        """,
    },
    {
        "id": "RF-14",
        "descripcion": (
            "Predios con destinación Comercial deben tener al menos una "
            "UC Comercial predominante en área construida"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH areas AS (
                SELECT p.T_Id, p.numero_predial_nacional,
                       SUM(CASE WHEN c.tipo_construccion = '1'
                                THEN c.area_construida ELSE 0 END) AS area_comercial,
                       SUM(c.area_construida) AS area_total,
                       SUM(CASE WHEN c.tipo_construccion = '1' THEN 1 ELSE 0 END) AS n_comercial
                FROM cca_predio p
                JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                WHERE p.destinacion_economica = '5'
                GROUP BY p.T_Id
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE
                     WHEN n_comercial = 0
                       THEN 'Predio Comercial sin UC Comercial'
                     ELSE 'UC Comercial no predominante en área'
                   END,
                   printf('comerc=%s total=%s', ROUND(area_comercial,2), ROUND(area_total,2)),
                   'UC Comercial predominante'
            FROM areas
            WHERE n_comercial = 0
               OR (area_total > 0 AND area_comercial <= area_total * 0.5)
        """,
    },
    {
        "id": "RF-15",
        "descripcion": (
            "Predios con destinación Industrial deben tener al menos una "
            "UC Industrial predominante en área construida"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH areas AS (
                SELECT p.T_Id, p.numero_predial_nacional,
                       SUM(CASE WHEN c.tipo_construccion = '2'
                                THEN c.area_construida ELSE 0 END) AS area_industrial,
                       SUM(c.area_construida) AS area_total,
                       SUM(CASE WHEN c.tipo_construccion = '2' THEN 1 ELSE 0 END) AS n_industrial
                FROM cca_predio p
                JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                WHERE p.destinacion_economica = '10'
                GROUP BY p.T_Id
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE
                     WHEN n_industrial = 0
                       THEN 'Predio Industrial sin UC Industrial'
                     ELSE 'UC Industrial no predominante en área'
                   END,
                   printf('indust=%s total=%s', ROUND(area_industrial,2), ROUND(area_total,2)),
                   'UC Industrial predominante'
            FROM areas
            WHERE n_industrial = 0
               OR (area_total > 0 AND area_industrial <= area_total * 0.5)
        """,
    },
    {
        "id": "RF-16",
        "descripcion": (
            "Predios con destinación Institucional, Educativo o Religioso "
            "deben tener al menos una UC Institucional predominante"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH areas AS (
                SELECT p.T_Id, p.numero_predial_nacional,
                       SUM(CASE WHEN c.tipo_construccion = '3'
                                THEN c.area_construida ELSE 0 END) AS area_instit,
                       SUM(c.area_construida) AS area_total,
                       SUM(CASE WHEN c.tipo_construccion = '3' THEN 1 ELSE 0 END) AS n_instit
                FROM cca_predio p
                JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                WHERE p.destinacion_economica IN ('7', '16', '23')
                GROUP BY p.T_Id
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE
                     WHEN n_instit = 0
                       THEN 'Predio Institucional/Educativo/Religioso sin UC Institucional'
                     ELSE 'UC Institucional no predominante en área'
                   END,
                   printf('instit=%s total=%s', ROUND(area_instit,2), ROUND(area_total,2)),
                   'UC Institucional predominante'
            FROM areas
            WHERE n_instit = 0
               OR (area_total > 0 AND area_instit <= area_total * 0.5)
        """,
    },
    # ------------------------------------------------------------------
    # TOTAL PLANTAS (RF-17)
    # ------------------------------------------------------------------
    {
        "id": "RF-17",
        "descripcion": (
            "total_plantas de la UC debe estar diligenciada y ser mayor "
            "a cero"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'total_plantas es NULL, 0 o negativo',
                   COALESCE(CAST(c.total_plantas AS TEXT), 'NULL'),
                   '> 0'
            FROM cca_caracteristicaucons c
            JOIN cca_unidadconstruccion u ON u.caracteristica = c.T_Id
            JOIN cca_predio p ON p.T_Id = u.predio
            WHERE c.total_plantas IS NULL
               OR c.total_plantas <= 0
        """,
    },
    # ------------------------------------------------------------------
    # ÁREAS PH/CONDOMINIO UNIDAD VS NO-PH (RF-18, RF-19)
    # ------------------------------------------------------------------
    {
        "id": "RF-18",
        "descripcion": (
            "Para PH/Condominio Unidad Predial: area_construida debe ser "
            "0 y area_privada_construida debe ser mayor a 0"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   CASE
                     WHEN COALESCE(c.area_construida, 0) <> 0
                       THEN 'area_construida debe ser 0 en PH/Condo Unidad'
                     ELSE 'area_privada_construida debe ser > 0 en PH/Condo Unidad'
                   END,
                   printf('area_construida=%s area_privada=%s',
                          COALESCE(CAST(c.area_construida AS TEXT), 'NULL'),
                          COALESCE(CAST(c.area_privada_construida AS TEXT), 'NULL')),
                   'area_construida=0, area_privada_construida>0'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE p.condicion_predio IN ('2', '4')
              AND (COALESCE(c.area_construida, 0) <> 0
                   OR c.area_privada_construida IS NULL
                   OR c.area_privada_construida <= 0)
        """,
    },
    {
        "id": "RF-19",
        "descripcion": (
            "Para predios no PH/Condominio Unidad: area_construida debe "
            "ser > 0 y area_privada_construida debe ser NULL"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   CASE
                     WHEN c.area_construida IS NULL OR c.area_construida <= 0
                       THEN 'area_construida debe ser > 0 para no-PH/Condo'
                     ELSE 'area_privada_construida debe ser NULL para no-PH/Condo'
                   END,
                   printf('area_construida=%s area_privada=%s',
                          COALESCE(CAST(c.area_construida AS TEXT), 'NULL'),
                          COALESCE(CAST(c.area_privada_construida AS TEXT), 'NULL')),
                   'area_construida>0, area_privada_construida=NULL'
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE p.condicion_predio NOT IN ('2', '4')
              AND (c.area_construida IS NULL
                   OR c.area_construida <= 0
                   OR c.area_privada_construida IS NOT NULL)
        """,
    },
    # ------------------------------------------------------------------
    # ÁREA CONSTRUIDA VS POLÍGONO (RF-20) — Requiere SpatiaLite
    # ------------------------------------------------------------------
    {
        "id": "RF-20",
        "descripcion": (
            "El area_construida diligenciada debe coincidir con el área "
            "calculada del polígono de la UC (requiere SpatiaLite)"
        ),
        "severidad": "advertencia",
        "sql": f"""
            SELECT 'cca_caracteristicaucons', c.T_Id,
                   p.numero_predial_nacional,
                   'area_construida difiere del área geográfica del polígono UC',
                   printf('declarada=%s geo=%s',
                          CAST(ROUND(c.area_construida,3) AS TEXT),
                          CAST(ROUND(ST_Area(u.geometria),3) AS TEXT)),
                   CAST(ROUND(ST_Area(u.geometria),3) AS TEXT)
            FROM cca_predio p
            JOIN cca_unidadconstruccion u ON u.predio = p.T_Id
            JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
            WHERE u.geometria IS NOT NULL
              AND p.condicion_predio NOT IN ('2','4')
              AND {_fuera_tol("c.area_construida", "ST_Area(u.geometria)")}
        """,
    },
    # ------------------------------------------------------------------
    # SUMA ÁREAS POR IDENTIFICADOR (RF-21) — Requiere SpatiaLite
    # ------------------------------------------------------------------
    {
        "id": "RF-21",
        "descripcion": (
            "La suma de áreas de polígonos por identificador debe coincidir "
            "con area_construida (o area_privada_construida en PH/Condo)"
        ),
        "severidad": "advertencia",
        "sql": f"""
            WITH suma_geo AS (
                SELECT u.predio, c.identificador,
                       SUM(ST_Area(u.geometria)) AS area_geo,
                       MAX(c.area_construida) AS area_declarada,
                       MAX(c.area_privada_construida) AS area_privada
                FROM cca_unidadconstruccion u
                JOIN cca_caracteristicaucons c ON c.T_Id = u.caracteristica
                WHERE u.geometria IS NOT NULL
                GROUP BY u.predio, c.identificador
            )
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Suma polígonos UC (' || sg.identificador || ') difiere del área declarada',
                   printf('geo=%s decl=%s',
                          CAST(ROUND(sg.area_geo,3) AS TEXT),
                          CAST(ROUND(
                              CASE WHEN p.condicion_predio IN ('2','4')
                                   THEN COALESCE(sg.area_privada, 0)
                                   ELSE COALESCE(sg.area_declarada, 0)
                              END, 3) AS TEXT)),
                   CAST(ROUND(sg.area_geo,3) AS TEXT)
            FROM suma_geo sg
            JOIN cca_predio p ON p.T_Id = sg.predio
            WHERE {_fuera_tol(
                "sg.area_geo",
                "CASE WHEN p.condicion_predio IN ('2','4') "
                "THEN COALESCE(sg.area_privada,0) "
                "ELSE COALESCE(sg.area_declarada,0) END"
            )}
        """,
    },
]
