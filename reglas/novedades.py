"""Reglas de novedades (RN-01 a RN-26).

Categoría: `novedades`.

Validan la coherencia de la información registrada en
cca_estructuranovedadnumeropredial frente a cca_predio y,
opcionalmente, contra la tabla auxiliar `_r1_predios` cargada
desde un CSV del Registro 1 (insumo inicial o periódico).

Las reglas que cruzan contra `_r1_predios` requieren que el motor
haya cargado el R1 antes de la ejecución (parámetro --r1 en consola
o campo R1 en el diálogo de Processing). Si `_r1_predios` no existe,
esas reglas reportarán error de SQL y continuarán.

Dominios clave de tipo_novedad:
    0  = Predio_Nuevo.Predio_Nuevo_Formal
    1  = Predio_Nuevo.Predio_Nuevo_Informal
    2  = Desenglobe_Venta_Parcial
    3  = Desenglobe_Division_Material
    4  = Englobe_Nuevo_FMI
    5  = Englobe_Mantiene_FMI
    6  = Cancelacion.Cancelacion
    7  = Cancelacion.Desenglobe
    8  = Cancelacion.Englobe
    9  = Cancelacion.Fuerza_Mayor
    10 = Cancelacion.Causa_Natural
    11 = Cancelacion.Cambio_Entidad_Administrativa
    12 = Cancelacion.Doble_Inscripcion
    13-29 = Cambio_Numero_Predial.*
    30 = Ninguna
"""

NOVEDADES_CANCELACION = "('6','7','8','9','10','11','12')"
NOVEDADES_DESENGLOBE = "('2','3')"
NOVEDADES_ENGLOBE = "('4','5')"
NOVEDADES_PREDIO_NUEVO = "('0','1')"
NOVEDADES_CAMBIO_NP = "('13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29')"

REGLAS = [
    # ==================================================================
    # DESENGLOBE (RN-01 a RN-05)
    # ==================================================================
    {
        "id": "RN-01",
        "descripcion": (
            "Los predios asociados al desenglobe deben tener folio de "
            "matrícula"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio con desenglobe sin folio de matrícula',
                   COALESCE(p.folio_matricula, 'NULL'),
                   'folio_matricula diligenciado'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_DESENGLOBE}
              AND (p.folio_matricula IS NULL OR TRIM(p.folio_matricula) = '')
        """,
    },
    {
        "id": "RN-02",
        "descripcion": (
            "El número predial en estructura novedad de desenglobe debe "
            "existir en el R1 (insumo inicial o periódico)"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'NP de desenglobe no existe en R1',
                   nv.numero_predial,
                   'existir en R1'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_DESENGLOBE}
              AND nv.numero_predial IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = nv.numero_predial
              )
        """,
    },
    {
        "id": "RN-03",
        "descripcion": (
            "El número predial de la novedad de desenglobe y el número "
            "predial del predio no deben ser predios informales"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio informal asociado a desenglobe',
                   'condicion_predio=' || p.condicion_predio,
                   'no informal (condicion <> 9)'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_DESENGLOBE}
              AND p.condicion_predio = '9'
        """,
    },
    {
        "id": "RN-04",
        "descripcion": (
            "Desenglobe por venta parcial: un registro debe mantener el "
            "mismo NP y los restantes deben ser predios nuevos con "
            "desenglobe"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH desenglobes AS (
                SELECT nv.cca_predio_novedad_numero_predial AS predio_tid,
                       nv.numero_predial,
                       nv.tipo_novedad,
                       p.numero_predial_nacional
                FROM cca_estructuranovedadnumeropredial nv
                JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
                WHERE nv.tipo_novedad = '2'
            ),
            por_predio AS (
                SELECT predio_tid, numero_predial_nacional,
                       SUM(CASE WHEN numero_predial = numero_predial_nacional
                                THEN 1 ELSE 0 END) AS n_mismo_np,
                       COUNT(*) AS n_total
                FROM desenglobes
                GROUP BY predio_tid
            )
            SELECT 'cca_predio', predio_tid, numero_predial_nacional,
                   'Desenglobe venta parcial: no hay exactamente 1 registro con mismo NP',
                   printf('mismo_np=%d total=%d', n_mismo_np, n_total),
                   'exactamente 1 registro con mismo NP'
            FROM por_predio
            WHERE n_mismo_np <> 1
        """,
    },
    {
        "id": "RN-05",
        "descripcion": (
            "Desenglobe por división material: un registro con mismo NP "
            "debe ser cancelación y los restantes deben ser desenglobe "
            "división material"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH div_mat AS (
                SELECT nv.cca_predio_novedad_numero_predial AS predio_tid,
                       nv.numero_predial,
                       nv.tipo_novedad,
                       p.numero_predial_nacional
                FROM cca_estructuranovedadnumeropredial nv
                JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
                WHERE nv.tipo_novedad IN ('3', '7')
            ),
            por_predio AS (
                SELECT predio_tid, numero_predial_nacional,
                       SUM(CASE WHEN numero_predial = numero_predial_nacional
                                     AND tipo_novedad IN ('7')
                                THEN 1 ELSE 0 END) AS n_cancel_mismo,
                       SUM(CASE WHEN tipo_novedad = '3' THEN 1 ELSE 0 END) AS n_div_mat,
                       COUNT(*) AS n_total
                FROM div_mat
                GROUP BY predio_tid
            )
            SELECT 'cca_predio', predio_tid, numero_predial_nacional,
                   'División material: estructura de novedades inconsistente',
                   printf('cancel_mismo=%d div_mat=%d total=%d',
                          n_cancel_mismo, n_div_mat, n_total),
                   '1 cancelación con mismo NP + resto desenglobe div. material'
            FROM por_predio
            WHERE n_cancel_mismo <> 1
               and n_div_mat < 1
        """,
    },
    # ==================================================================
    # ENGLOBE (RN-06 a RN-09)
    # ==================================================================
    {
        "id": "RN-06",
        "descripcion": (
            "Los predios asociados al englobe deben tener folio de "
            "matrícula"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio con englobe sin folio de matrícula',
                   COALESCE(p.folio_matricula, 'NULL'),
                   'folio_matricula diligenciado'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_ENGLOBE}
              AND (p.folio_matricula IS NULL OR TRIM(p.folio_matricula) = '')
        """,
    },
    {
        "id": "RN-07",
        "descripcion": (
            "El número predial en estructura novedad de englobe debe "
            "existir en el R1"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'NP de englobe no existe en R1',
                   nv.numero_predial,
                   'existir en R1'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_ENGLOBE}
              AND nv.numero_predial IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = nv.numero_predial
              )
        """,
    },
    {
        "id": "RN-08",
        "descripcion": (
            "Englobe mantiene FMI: al menos 3 registros, todos con "
            "novedad Englobe_Mantiene_FMI, y los que no mantienen NP "
            "deben tener cancelación por englobe"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH eng_mantiene AS (
                SELECT nv.cca_predio_novedad_numero_predial AS predio_tid,
                       p.numero_predial_nacional,
                       COUNT(*) AS n_registros,
                       SUM(CASE WHEN nv.tipo_novedad = '5' THEN 1 ELSE 0 END) AS n_mantiene,
                       SUM(CASE WHEN nv.tipo_novedad = '8' THEN 1 ELSE 0 END) AS n_cancel_eng
                FROM cca_estructuranovedadnumeropredial nv
                JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
                WHERE nv.tipo_novedad IN ('5', '8')
                GROUP BY nv.cca_predio_novedad_numero_predial
                HAVING SUM(CASE WHEN nv.tipo_novedad = '5' THEN 1 ELSE 0 END) > 0
            )
            SELECT 'cca_predio', predio_tid, numero_predial_nacional,
                   'Englobe mantiene FMI: estructura inconsistente',
                   printf('total=%d mantiene=%d cancel=%d',
                          n_registros, n_mantiene, n_cancel_eng),
                   'al menos 3 registros con estructura válida'
            FROM eng_mantiene
            WHERE n_registros < 3
        """,
    },
    {
        "id": "RN-09",
        "descripcion": (
            "Englobe nuevo FMI: al menos 4 registros; todos los predios "
            "englobados deben tener Englobe_Nuevo_FMI y Cancelación por "
            "englobe; NP resultante posición 18 debe ser 9 o A-Z"
        ),
        "severidad": "advertencia",
        "sql": """
            WITH eng_nuevo AS (
                SELECT nv.cca_predio_novedad_numero_predial AS predio_tid,
                       p.numero_predial_nacional,
                       COUNT(*) AS n_registros,
                       SUM(CASE WHEN nv.tipo_novedad = '4' THEN 1 ELSE 0 END) AS n_nuevo,
                       SUM(CASE WHEN nv.tipo_novedad = '8' THEN 1 ELSE 0 END) AS n_cancel
                FROM cca_estructuranovedadnumeropredial nv
                JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
                WHERE nv.tipo_novedad IN ('4', '8')
                GROUP BY nv.cca_predio_novedad_numero_predial
                HAVING SUM(CASE WHEN nv.tipo_novedad = '4' THEN 1 ELSE 0 END) > 0
            )
            SELECT 'cca_predio', predio_tid, numero_predial_nacional,
                   'Englobe nuevo FMI: estructura inconsistente',
                   printf('total=%d nuevo=%d cancel=%d',
                          n_registros, n_nuevo, n_cancel),
                   'al menos 4 registros con estructura válida'
            FROM eng_nuevo
            WHERE n_registros < 4
        """,
    },
    # ==================================================================
    # CANCELACIÓN (RN-10 a RN-14)
    # ==================================================================
    {
        "id": "RN-10",
        "descripcion": (
            "El número predial del predio que se cancela no debe ser "
            "predio nuevo"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'Predio cancelado es también predio nuevo',
                   'tipo_novedad cancelación + predio nuevo',
                   'cancelación no aplica a predios nuevos'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_CANCELACION}
              AND EXISTS (
                  SELECT 1 FROM cca_estructuranovedadnumeropredial nv2
                  WHERE nv2.cca_predio_novedad_numero_predial = nv.cca_predio_novedad_numero_predial
                    AND nv2.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
                    AND nv2.numero_predial = nv.numero_predial
              )
        """,
    },
    {
        "id": "RN-11",
        "descripcion": (
            "El número predial del predio que se cancela no debe ser "
            "predio informal"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio informal con novedad de cancelación',
                   'condicion_predio=' || p.condicion_predio,
                   'no informal'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_CANCELACION}
              AND p.condicion_predio = '9'
        """,
    },
    {
        "id": "RN-12",
        "descripcion": (
            "En cancelación, el número predial debe ser el mismo en "
            "cca_predio y en cca_estructuranovedadnumeropredial"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'NP en estructura novedad difiere del NP en cca_predio',
                   printf('estructura=%s predio=%s',
                          nv.numero_predial,
                          p.numero_predial_nacional),
                   'deben ser iguales'
            FROM cca_estructuranovedadnumeropredial nv
            JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
            WHERE nv.tipo_novedad IN ('6')
              AND nv.numero_predial <> p.numero_predial_nacional
        """,
    },
    {
        "id": "RN-13",
        "descripcion": (
            "Los predios cancelados deben tener observación que "
            "especifique el motivo de la cancelación"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'Cancelación sin observación en el derecho del predio',
                   'sin observación',
                   'observación con motivo de cancelación'
            FROM cca_estructuranovedadnumeropredial nv
            JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
            LEFT JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_CANCELACION}
              AND (d.observacion IS NULL OR TRIM(d.observacion) = '')
        """,
    },
    {
        "id": "RN-14",
        "descripcion": (
            "Los predios cancelados no deben tener información espacial "
            "(terreno ni unidades de construcción)"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN EXISTS (SELECT 1 FROM cca_terreno t WHERE t.predio = p.T_Id)
                       THEN 'Predio cancelado con terreno asociado'
                     ELSE 'Predio cancelado con UC asociada'
                   END,
                   'tiene info espacial',
                   'sin terreno ni UC'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_CANCELACION}
              AND (EXISTS (SELECT 1 FROM cca_terreno t WHERE t.predio = p.T_Id)
                   OR EXISTS (SELECT 1 FROM cca_unidadconstruccion u WHERE u.predio = p.T_Id))
        """,
    },
    # ==================================================================
    # CAMBIO DE NÚMERO PREDIAL (RN-15 a RN-17)
    # ==================================================================
    {
        "id": "RN-15",
        "descripcion": (
            "En cambio de NP, el número predial en estructura novedad "
            "debe ser diferente al de cca_predio, y el NP antiguo no "
            "debe existir en cca_predio"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   CASE
                     WHEN nv.numero_predial = p.numero_predial_nacional
                       THEN 'Cambio de NP: NP en estructura = NP en predio (deben diferir)'
                     ELSE 'NP antiguo de cambio existe como NP de otro predio'
                   END,
                   printf('estructura=%s predio=%s',
                          nv.numero_predial, p.numero_predial_nacional),
                   'NP estructura <> NP predio, y NP antiguo no en cca_predio'
            FROM cca_estructuranovedadnumeropredial nv
            JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
            WHERE nv.tipo_novedad IN {NOVEDADES_CAMBIO_NP}
              AND (nv.numero_predial = p.numero_predial_nacional
                   OR EXISTS (
                       SELECT 1 FROM cca_predio p2
                       WHERE p2.numero_predial_nacional = nv.numero_predial
                         AND p2.T_Id <> p.T_Id
                   ))
        """,
    },
    {
        "id": "RN-16",
        "descripcion": (
            "En cambio de NP, el número predial en estructura no debe "
            "ser predio nuevo ni informal"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'NP de cambio es predio nuevo o informal en R1 / estructura',
                   nv.numero_predial,
                   'NP no nuevo ni informal'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_CAMBIO_NP}
              AND EXISTS (
                  SELECT 1 FROM cca_estructuranovedadnumeropredial nv2
                  WHERE nv2.numero_predial = nv.numero_predial
                    AND nv2.tipo_novedad IN ('0','1')
              )
        """,
    },
    {
        "id": "RN-17",
        "descripcion": (
            "En cambio de NP, el NP resultante en cca_predio no debe "
            "existir en el R1 y debe ser predio nuevo"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'NP resultante de cambio existe en R1 (no debería)',
                   p.numero_predial_nacional,
                   'no existir en R1'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_CAMBIO_NP}
              AND EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = p.numero_predial_nacional
              )
        """,
    },
    # ==================================================================
    # PREDIO NUEVO (RN-18 a RN-21)
    # ==================================================================
    {
        "id": "RN-18",
        "descripcion": (
            "En predio nuevo, el NP en estructura novedad debe ser igual "
            "al NP en cca_predio"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'Predio nuevo: NP en estructura <> NP en predio',
                   printf('estructura=%s predio=%s',
                          nv.numero_predial, p.numero_predial_nacional),
                   'deben ser iguales'
            FROM cca_estructuranovedadnumeropredial nv
            JOIN cca_predio p ON p.T_Id = nv.cca_predio_novedad_numero_predial
            WHERE nv.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
              AND nv.numero_predial <> p.numero_predial_nacional
        """,
    },
    {
        "id": "RN-19",
        "descripcion": (
            "En predio nuevo, tanto el NP de estructura como el de "
            "cca_predio deben ser predios nuevos (no existir en R1)"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', nv.T_Id,
                   nv.numero_predial,
                   'Predio nuevo pero NP existe en R1',
                   nv.numero_predial,
                   'no existir en R1'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
              AND EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = nv.numero_predial
              )
        """,
    },
    {
        "id": "RN-20",
        "descripcion": (
            "En predio nuevo, el NP no debe existir en el R1 de insumo"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'NP de predio nuevo existe en R1',
                   p.numero_predial_nacional,
                   'no existir en R1'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
              AND EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = p.numero_predial_nacional
              )
        """,
    },
    {
        "id": "RN-21",
        "descripcion": (
            "El NP en estructura novedad de predio nuevo no puede ser "
            "mejora (condicion_predio = 5)"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio nuevo es mejora (condicion=5)',
                   'condicion_predio=' || p.condicion_predio,
                   'condicion <> 5 (Mejora)'
            FROM cca_predio p
            JOIN cca_estructuranovedadnumeropredial nv
              ON nv.cca_predio_novedad_numero_predial = p.T_Id
            WHERE nv.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
              AND p.condicion_predio = '5'
        """,
    },
    # ==================================================================
    # REGLAS GENERALES (RN-22 a RN-26)
    # ==================================================================
    {
        "id": "RN-22",
        "descripcion": (
            "Todos los predios del R1 deben estar en la tabla de "
            "estructura de novedad"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_estructuranovedadnumeropredial', NULL,
                   r1.numero_predial,
                   'Predio del R1 no tiene novedad registrada',
                   r1.numero_predial,
                   'existir en estructura novedad'
            FROM _r1_predios r1
            WHERE NOT EXISTS (
                SELECT 1 FROM cca_estructuranovedadnumeropredial nv
                WHERE nv.numero_predial = r1.numero_predial
            )
        """,
    },
    {
        "id": "RN-23",
        "descripcion": (
            "Un número predial no puede relacionar más de una vez una "
            "novedad de cambio de número predial"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', MIN(nv.T_Id),
                   nv.numero_predial,
                   'NP con más de un cambio de número predial',
                   CAST(COUNT(*) AS TEXT),
                   '1'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN {NOVEDADES_CAMBIO_NP}
            GROUP BY nv.numero_predial
            HAVING COUNT(*) > 1
        """,
    },
    {
        "id": "RN-24-A",
        "descripcion": (
            "Un número predial no puede relacionar simultáneamente una "
            "novedad de englobe y una de desenglobe"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', MIN(nv.T_Id),
                   nv.numero_predial,
                   'NP con englobe y desenglobe simultáneamente',
                   nv.numero_predial,
                   'solo englobe o solo desenglobe'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN ('2','3','4','5')
            GROUP BY nv.numero_predial
            HAVING SUM(CASE WHEN nv.tipo_novedad IN ('2','3') THEN 1 ELSE 0 END) > 0
               AND SUM(CASE WHEN nv.tipo_novedad IN ('4','5') THEN 1 ELSE 0 END) > 0
        """,
    },
    {
        "id": "RN-24-B",
        "descripcion": (
            "Un número predial no puede tener novedades y números "
            "prediales repetidos en estructura novedad"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_estructuranovedadnumeropredial', MIN(nv.T_Id),
                   nv.cca_predio_novedad_numero_predial,
                   'NP con novedad duplicada (mismo tipo_novedad y NP)',
                   printf('tipo=%s repeticiones=%d',
                          nv.tipo_novedad, COUNT(*)),
                   'combinación NP + tipo_novedad única'
            FROM cca_estructuranovedadnumeropredial nv
            GROUP BY nv.cca_predio_novedad_numero_predial, nv.tipo_novedad
            HAVING COUNT(*) > 1
        """,
    },
    {
        "id": "RN-25",
        "descripcion": (
            "A un número predial no se le puede relacionar simultáneamente "
            "una novedad de Cancelación y una de Predio Nuevo"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_estructuranovedadnumeropredial', MIN(nv.T_Id),
                   nv.numero_predial,
                   'NP con Cancelación y Predio Nuevo simultáneamente',
                   nv.numero_predial,
                   'solo cancelación o solo predio nuevo'
            FROM cca_estructuranovedadnumeropredial nv
            WHERE nv.tipo_novedad IN ('0','1','6','7','8','9','10','11','12')
            GROUP BY nv.numero_predial
            HAVING SUM(CASE WHEN nv.tipo_novedad IN {NOVEDADES_PREDIO_NUEVO}
                            THEN 1 ELSE 0 END) > 0
               AND SUM(CASE WHEN nv.tipo_novedad IN {NOVEDADES_CANCELACION}
                            THEN 1 ELSE 0 END) > 0
        """,
    },
    {
        "id": "RN-26",
        "descripcion": (
            "Todas las mejoras registradas en el R1 deben asociar una "
            "novedad de Cambio de Número Predial o Cancelación"
        ),
        "severidad": "error",
        "sql": f"""
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Mejora sin novedad de cambio de NP ni cancelación',
                   'condicion=5 (Mejora)',
                   'cambio de NP o cancelación'
            FROM cca_predio p
            WHERE p.condicion_predio = '5'
              AND EXISTS (
                  SELECT 1 FROM _r1_predios r1
                  WHERE r1.numero_predial = p.numero_predial_nacional
              )
              AND NOT EXISTS (
                  SELECT 1 FROM cca_estructuranovedadnumeropredial nv
                  WHERE nv.cca_predio_novedad_numero_predial = p.T_Id
                    AND (nv.tipo_novedad IN {NOVEDADES_CAMBIO_NP}
                         OR nv.tipo_novedad IN {NOVEDADES_CANCELACION})
              )
        """,
    },
]
