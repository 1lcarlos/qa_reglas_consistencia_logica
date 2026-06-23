"""Reglas de cardinalidad y consistencia entre cca_terreno y cca_predio.

Categoría: `terreno`.

R-25 (texto original):
  Los predios asociados a condiciones NPH (0) / PH.Matriz (1) /
  Condominio.Matriz (3) / Condominio.Unidad_Predial (4) / Via (8) /
  Bien_Uso_Publico (10) / Parque_Cementerio.Matriz (6), deben estar
  representados por UN ÚNICO elemento en cca_terreno excepto los que
  tienen novedad de Cancelación / Cancelacion_por_Desenglobe /
  Cancelacion_por_Englobe. Y todo cca_terreno debe estar asociado a un
  cca_predio con esas condiciones SIN novedad de cancelación.

Códigos de tipo_novedad en cca_estructuranovedadnumeropredial:
    6  = Cancelacion.Cancelacion
    7  = Cancelacion.Desenglobe
    8  = Cancelacion.Englobe
    9  = Cancelacion.Fuerza_Mayor
    10 = Cancelacion.Causa_Natural
    11 = Cancelacion.Cambio_Entidad_Administrativa
    12 = Cancelacion.Doble_Inscripcion

Para el chequeo de "novedad de cancelación" consideramos tipo_novedad >= 6
(todos los códigos de la familia Cancelacion.*).
"""

# Condiciones que exigen UN cca_terreno y exactamente uno.
# (excluimos PH.Unidad_Predial=2 porque no tiene terreno propio).
CONDICIONES_CON_TERRENO = "('0','1','3','4','6','8','10')"


REGLAS = [
    {
        "id": "R-25-A",
        "descripcion": (
            "Cada predio con condición NPH/PH.Matriz/Condominio.*/Via/"
            "Bien_Uso_Publico/Parque_Cementerio.Matriz debe tener exactamente "
            "un cca_terreno asociado (excepto si tiene novedad de cancelación)"
        ),
        "severidad": "error",
        "sql": f"""
            WITH conteos AS (
                SELECT p.T_Id, p.numero_predial_nacional, p.condicion_predio,
                       (SELECT COUNT(*) FROM cca_terreno t WHERE t.predio = p.T_Id) AS n_terreno,
                       (SELECT COUNT(*) FROM cca_estructuranovedadnumeropredial nv
                         WHERE nv.cca_predio_novedad_numero_predial = p.T_Id
                           AND nv.tipo_novedad IN ('6','7','8','9','10','11','12')) AS n_cancel
                FROM cca_predio p
                WHERE p.condicion_predio IN {CONDICIONES_CON_TERRENO}
            )
            SELECT 'cca_predio', T_Id, numero_predial_nacional,
                   CASE WHEN n_terreno = 0
                          THEN 'Predio sin cca_terreno asociado'
                        ELSE 'Predio con ' || n_terreno || ' terrenos asociados'
                   END,
                   CAST(n_terreno AS TEXT),
                   '1'
            FROM conteos
            WHERE n_terreno <> 1
              AND n_cancel = 0
        """,
    },
    {
        "id": "R-25-B",
        "descripcion": (
            "Todo cca_terreno debe estar asociado a un cca_predio con "
            "condición admisible y sin novedad de cancelación"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_terreno', t.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN p.T_Id IS NULL
                       THEN 'Terreno sin cca_predio asociado'
                     WHEN p.condicion_predio NOT IN {CONDICIONES_CON_TERRENO}
                       THEN 'Terreno asociado a predio con condición no admisible: ' || p.condicion_predio
                     ELSE 'Terreno asociado a predio con novedad de cancelación'
                   END,
                   COALESCE(p.condicion_predio, 'NULL'),
                   'predio con condición admisible y sin cancelación'
            FROM cca_terreno t
            LEFT JOIN cca_predio p ON p.T_Id = t.predio
            WHERE p.T_Id IS NULL
               OR p.condicion_predio NOT IN {CONDICIONES_CON_TERRENO}
               OR EXISTS (
                   SELECT 1 FROM cca_estructuranovedadnumeropredial nv
                   WHERE nv.cca_predio_novedad_numero_predial = p.T_Id
                     AND nv.tipo_novedad IN ('6','7','8','9','10','11','12')
               )
        """,
    },
]
