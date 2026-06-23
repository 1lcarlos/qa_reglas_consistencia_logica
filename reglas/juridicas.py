"""Reglas jurídicas (RJ-01 a RJ-31).

Categoría: `juridicas`.

Validan coherencia entre derechos, interesados, agrupaciones, fuentes
administrativas y la información registral del predio.

Dominios clave:
    tipo_derecho:    0=Dominio, 1=Ocupacion, 2=Posesion
    tipo_predio:     0=Baldio, 1=Fiscal_Patrimonial, 2=Uso_Publico,
                     3=Presunto_Baldio, 4=Privado
    tipo_interesado: 0=Persona_Natural, 1=Persona_Juridica
    tipo_documento:  0=CC, 1=CE, 2=NIT, 3=Pasaporte, 4=RC, 5=TI,
                     6=Secuencial, 7=Sin_Informacion
    tipo_agrupacion: 0=Grupo_Civil, 1=Grupo_Empresarial, 2=Grupo_Etnico,
                     3=Grupo_Mixto
    grupo_etnico:    0=Indigena … 5=Afrocolombiano, 6=Ninguno
"""

REGLAS = [
    # ------------------------------------------------------------------
    # FECHA DE INICIO DE TENENCIA (RJ-01)
    # ------------------------------------------------------------------
    {
        "id": "RJ-01",
        "descripcion": (
            "La fecha de inicio de tenencia del derecho debe ser mayor a "
            "cero y menor a la fecha de visita al predio"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_derechocatastral', d.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN d.fecha_inicio_derecho IS NULL
                          OR TRIM(d.fecha_inicio_derecho) = ''
                       THEN 'Fecha inicio de tenencia vacía'
                     WHEN d.fecha_inicio_derecho >= p.fecha_visita_predio
                       THEN 'Fecha inicio de tenencia >= fecha de visita'
                     ELSE 'Fecha inicio de tenencia inválida'
                   END,
                   COALESCE(d.fecha_inicio_derecho, 'NULL'),
                   'entre 0 y ' || COALESCE(p.fecha_visita_predio, 'sin_visita')
            FROM cca_derechocatastral d
            JOIN cca_predio p ON p.T_Id = d.predio
            WHERE p.fecha_visita_predio IS NOT NULL
              AND ( d.fecha_inicio_derecho IS NULL
                 OR TRIM(d.fecha_inicio_derecho) = ''
                 OR d.fecha_inicio_derecho >= p.fecha_visita_predio )
        """,
    },
    # ------------------------------------------------------------------
    # FMI Y DERECHO (RJ-02-A, RJ-02-B)
    # ------------------------------------------------------------------
    {
        "id": "RJ-02-A",
        "descripcion": (
            "Predio formal privado con Derecho de Dominio debe tener "
            "Matrícula Inmobiliaria"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio privado formal con Dominio sin matrícula inmobiliaria',
                   COALESCE(p.folio_matricula, 'NULL'),
                   'folio_matricula diligenciado'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE p.tipo_predio = '4'
              AND p.condicion_predio <> '9'
              AND d.tipo_derecho = '0'
              AND (p.folio_matricula IS NULL OR TRIM(p.folio_matricula) = '')
        """,
    },
    {
        "id": "RJ-02-B",
        "descripcion": (
            "Predio informal con Posesión u Ocupación no debe tener "
            "Matrícula Inmobiliaria (aplican excepciones)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio informal con Posesión/Ocupación tiene matrícula inmobiliaria',
                   p.folio_matricula,
                   'sin matrícula'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE p.condicion_predio = '9'
              AND d.tipo_derecho IN ('1', '2')
              AND p.folio_matricula IS NOT NULL
              AND TRIM(p.folio_matricula) <> ''
        """,
    },
    # ------------------------------------------------------------------
    # COHERENCIA TIPO PREDIO ↔ TIPO DERECHO (RJ-03 a RJ-05)
    # ------------------------------------------------------------------
    {
        "id": "RJ-03",
        "descripcion": (
            "Predios con derecho de Posesión deben ser tipo de predio Privado"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio con Posesión pero tipo_predio no es Privado',
                   COALESCE(p.tipo_predio, 'NULL'),
                   '4 (Privado)'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE d.tipo_derecho = '2'
              AND (p.tipo_predio IS NULL OR p.tipo_predio <> '4')
        """,
    },
    {
        "id": "RJ-04",
        "descripcion": (
            "Predios con tipo Privado no deben tener derecho de Ocupación"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio Privado con derecho de Ocupación',
                   'tipo_predio=4, tipo_derecho=1',
                   'tipo_derecho <> 1 (Ocupación)'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE p.tipo_predio = '4'
              AND d.tipo_derecho = '1'
        """,
    },
    {
        "id": "RJ-05",
        "descripcion": (
            "Predios de tipo público no pueden tener derecho de Posesión"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio público con derecho de Posesión',
                   'tipo_predio=' || p.tipo_predio || ', tipo_derecho=2',
                   'tipo_derecho <> 2 (Posesión)'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE p.tipo_predio IN ('0', '1', '2', '3')
              AND d.tipo_derecho = '2'
        """,
    },
    # ------------------------------------------------------------------
    # INTERESADOS EN PREDIOS ESPECIALES (RJ-06, RJ-08, RJ-09)
    # ------------------------------------------------------------------
    {
        "id": "RJ-06",
        "descripcion": (
            "En predios baldíos con Dominio, el interesado debe ser la "
            "Nación, Municipio o Agencia Nacional de Tierras"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio baldío con Dominio: interesado no es Nación/Municipio/ANT',
                   COALESCE(i.razon_social, i.nombre_interesado, 'NULL'),
                   'Nación / Municipio / Agencia Nacional de Tierras'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            LEFT JOIN cca_interesado i ON i.T_Id = d.interesado
            LEFT JOIN cca_interesado_agrupacion ia
                ON ia.agrupacion = d.agrupacion
            LEFT JOIN cca_interesado i2 ON i2.T_Id = ia.interesado
            WHERE p.tipo_predio = '0'
              AND d.tipo_derecho = '0'
              AND NOT (
                  UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%NACION%'
                  OR UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%MUNICIPIO%'
                  OR UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%AGENCIA NACIONAL DE TIERRAS%'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM cca_interesado_agrupacion ia2
                  JOIN cca_interesado i3 ON i3.T_Id = ia2.interesado
                  WHERE ia2.agrupacion = d.agrupacion
                    AND (UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                             LIKE '%NACION%'
                         OR UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                             LIKE '%MUNICIPIO%'
                         OR UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                             LIKE '%AGENCIA NACIONAL DE TIERRAS%')
              )
        """,
    },
    {
        "id": "RJ-07",
        "descripcion": (
            "Si el predio es Privado colectivo (agrupación étnica), el "
            "interesado debe tener grupo_etnico diligenciado y distinto "
            "de Ninguno"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_interesado', i.T_Id, p.numero_predial_nacional,
                   'Interesado en agrupación étnica sin grupo_etnico válido',
                   COALESCE(i.grupo_etnico, 'NULL'),
                   'grupo_etnico diligenciado y <> 6 (Ninguno)'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            JOIN cca_agrupacioninteresados a ON a.T_Id = d.agrupacion
            JOIN cca_interesado_agrupacion ia ON ia.agrupacion = a.T_Id
            JOIN cca_interesado i ON i.T_Id = ia.interesado
            WHERE a.tipo_agrupacion = '2'
              AND (i.grupo_etnico IS NULL OR i.grupo_etnico = '6')
        """,
    },
    {
        "id": "RJ-08",
        "descripcion": (
            "En predios presuntos baldíos con Ocupación, el interesado NO "
            "debe ser la Nación, Municipio o Agencia Nacional de Tierras"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio presunto baldío con Ocupación: interesado es entidad pública',
                   COALESCE(i.razon_social, i.nombre_interesado, 'SIN INTERESADO DIRECTO'),
                   'interesado diferente a Nación/Municipio/ANT'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            LEFT JOIN cca_interesado i ON i.T_Id = d.interesado
            WHERE p.tipo_predio = '3'
              AND d.tipo_derecho = '1'
              AND (
                  UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%NACION%'
                  OR UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%MUNICIPIO%'
                  OR UPPER(COALESCE(i.razon_social, i.nombre_interesado, ''))
                      LIKE '%AGENCIA NACIONAL DE TIERRAS%'
              )

            UNION ALL

            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio presunto baldío con Ocupación: interesado en agrupación es entidad pública',
                   COALESCE(i3.razon_social, i3.nombre_interesado, 'NULL'),
                   'interesado diferente a Nación/Municipio/ANT'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            JOIN cca_interesado_agrupacion ia ON ia.agrupacion = d.agrupacion
            JOIN cca_interesado i3 ON i3.T_Id = ia.interesado
            WHERE p.tipo_predio = '3'
              AND d.tipo_derecho = '1'
              AND (
                  UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                      LIKE '%NACION%'
                  OR UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                      LIKE '%MUNICIPIO%'
                  OR UPPER(COALESCE(i3.razon_social, i3.nombre_interesado, ''))
                      LIKE '%AGENCIA NACIONAL DE TIERRAS%'
              )
        """,
    },
    {
        "id": "RJ-09",
        "descripcion": (
            "Predios públicos (fiscales/patrimoniales o de uso público) con "
            "Dominio: el interesado debe ser Persona Jurídica"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   'Predio público con Dominio: interesado no es Persona Jurídica',
                   COALESCE(i.tipo_interesado, 'NULL'),
                   '1 (Persona_Juridica)'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            LEFT JOIN cca_interesado i ON i.T_Id = d.interesado
            WHERE p.tipo_predio IN ('1', '2')
              AND d.tipo_derecho = '0'
              AND d.interesado IS NOT NULL
              AND (i.tipo_interesado IS NULL OR i.tipo_interesado <> '1')
        """,
    },
    # ------------------------------------------------------------------
    # VÍA / USO PÚBLICO (RJ-10)
    # ------------------------------------------------------------------
    {
        "id": "RJ-10",
        "descripcion": (
            "Predios de vía o uso público deben tener tipo_predio Uso_Publico "
            "y tipo de derecho Dominio"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN p.tipo_predio IS NULL OR p.tipo_predio <> '2'
                       THEN 'tipo_predio debe ser 2 (Uso_Publico)'
                     ELSE 'tipo_derecho debe ser 0 (Dominio)'
                   END,
                   'tipo_predio=' || COALESCE(p.tipo_predio,'NULL')
                       || ' tipo_derecho=' || COALESCE(d.tipo_derecho,'NULL'),
                   'tipo_predio=2, tipo_derecho=0'
            FROM cca_predio p
            LEFT JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE p.condicion_predio IN ('8', '10')
              AND (p.tipo_predio IS NULL
                   OR p.tipo_predio <> '2'
                   OR d.T_Id IS NULL
                   OR d.tipo_derecho <> '0')
        """,
    },
    # ------------------------------------------------------------------
    # COHERENCIA TEMPORAL FMI (RJ-11, RJ-12)
    # ------------------------------------------------------------------
    {
        "id": "RJ-11",
        "descripcion": (
            "Para predios con FMI, la fecha de inicio de tenencia debe ser "
            ">= la fecha del documento fuente (título)"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_derechocatastral', d.T_Id, p.numero_predial_nacional,
                   'fecha_inicio_derecho anterior a fecha del documento fuente',
                   d.fecha_inicio_derecho,
                   f.fecha_fuente
            FROM cca_derechocatastral d
            JOIN cca_predio p ON p.T_Id = d.predio
            JOIN cca_fuenteadministrativa f ON f.T_Id = d.fuente
            WHERE p.folio_matricula IS NOT NULL
              AND TRIM(p.folio_matricula) <> ''
              AND d.fecha_inicio_derecho IS NOT NULL
              AND f.fecha_fuente IS NOT NULL
              AND d.fecha_inicio_derecho < f.fecha_fuente
        """,
    },
    {
        "id": "RJ-12-A",
        "descripcion": (
            "Si el predio tiene FMI, debe tener fuente administrativa con "
            "fecha, tipo, número y ente emisor diligenciados"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_derechocatastral', d.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN d.fuente IS NULL
                       THEN 'Derecho sin fuente administrativa asociada'
                     WHEN f.fecha_fuente IS NULL OR TRIM(f.fecha_fuente) = ''
                       THEN 'Fuente sin fecha_fuente'
                     WHEN f.tipo_fuente IS NULL
                       THEN 'Fuente sin tipo_fuente'
                     WHEN f.nombre_fuente IS NULL OR TRIM(f.nombre_fuente) = ''
                       THEN 'Fuente sin nombre_fuente (número)'
                     WHEN f.ente_emisor IS NULL OR TRIM(f.ente_emisor) = ''
                       THEN 'Fuente sin ente_emisor'
                     ELSE 'Fuente incompleta'
                   END,
                   printf('fuente=%s tipo=%s nombre=%s ente=%s fecha=%s',
                          COALESCE(CAST(d.fuente AS TEXT), 'NULL'),
                          COALESCE(f.tipo_fuente, 'NULL'),
                          COALESCE(f.nombre_fuente, 'NULL'),
                          COALESCE(f.ente_emisor, 'NULL'),
                          COALESCE(f.fecha_fuente, 'NULL')),
                   'todos diligenciados'
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            LEFT JOIN cca_fuenteadministrativa f ON f.T_Id = d.fuente
            WHERE p.folio_matricula IS NOT NULL
              AND TRIM(p.folio_matricula) <> ''
              AND (d.fuente IS NULL
                   OR f.fecha_fuente IS NULL OR TRIM(f.fecha_fuente) = ''
                   OR f.tipo_fuente IS NULL
                   OR f.nombre_fuente IS NULL OR TRIM(f.nombre_fuente) = ''
                   OR f.ente_emisor IS NULL OR TRIM(f.ente_emisor) = '')
        """,
    },
    {
        "id": "RJ-12-B",
        "descripcion": (
            "La fecha del documento fuente no puede ser posterior a la "
            "fecha de levantamiento (visita al predio)"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_fuenteadministrativa', f.T_Id, p.numero_predial_nacional,
                   'Fecha del documento fuente posterior a la fecha de visita',
                   f.fecha_fuente,
                   p.fecha_visita_predio
            FROM cca_predio p
            JOIN cca_derechocatastral d ON d.predio = p.T_Id
            JOIN cca_fuenteadministrativa f ON f.T_Id = d.fuente
            WHERE p.folio_matricula IS NOT NULL
              AND TRIM(p.folio_matricula) <> ''
              AND f.fecha_fuente IS NOT NULL
              AND p.fecha_visita_predio IS NOT NULL
              AND f.fecha_fuente > p.fecha_visita_predio
        """,
    },
    # ------------------------------------------------------------------
    # TIPO DOCUMENTO DEL INTERESADO (RJ-13 a RJ-16)
    # ------------------------------------------------------------------
    {
        "id": "RJ-13",
        "descripcion": (
            "Persona Jurídica solo debe tener tipo de documento NIT o "
            "Secuencial"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(razon_social, nombre_interesado, 'SIN NOMBRE'),
                   'Persona Jurídica con tipo_documento no válido',
                   tipo_documento,
                   '2 (NIT) o 6 (Secuencial)'
            FROM cca_interesado
            WHERE tipo_interesado = '1'
              AND tipo_documento NOT IN ('2', '6')
        """,
    },
    {
        "id": "RJ-14",
        "descripcion": (
            "Persona Natural solo debe tener tipo de documento CC, CE, "
            "Pasaporte, RC, TI o Secuencial"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, 'SIN NOMBRE'),
                   'Persona Natural con tipo_documento no válido',
                   tipo_documento,
                   '0(CC), 1(CE), 3(Pasaporte), 4(RC), 5(TI) o 6(Secuencial)'
            FROM cca_interesado
            WHERE tipo_interesado = '0'
              AND tipo_documento NOT IN ('0', '1', '3', '4', '5', '6')
        """,
    },
    {
        "id": "RJ-15",
        "descripcion": (
            "Si el tipo de documento es CC, CE, TI o RC, el número de "
            "documento no debe ser cero ni vacío"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, razon_social, 'SIN NOMBRE'),
                   'Documento tipo ' || tipo_documento || ' con número vacío o cero',
                   COALESCE(numero_documento, 'NULL'),
                   'número válido > 0'
            FROM cca_interesado
            WHERE tipo_documento IN ('0', '1', '4', '5')
              AND (numero_documento IS NULL
                   OR TRIM(numero_documento) = ''
                   OR TRIM(numero_documento) = '0')
        """,
    },
    {
        "id": "RJ-16",
        "descripcion": (
            "Si el tipo de documento es NIT, el número debe ser numérico "
            "con guion y dígito de verificación, sin ser consecutivo "
            "(ej: 12345678-9)"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(razon_social, nombre_interesado, 'SIN NOMBRE'),
                   CASE
                     WHEN numero_documento IS NULL
                          OR TRIM(numero_documento) = ''
                       THEN 'NIT vacío'
                     WHEN numero_documento NOT LIKE '%-%'
                       THEN 'NIT sin guion separador'
                     WHEN REPLACE(REPLACE(numero_documento, '-', ''), ' ', '')
                          <> CAST(CAST(
                              REPLACE(REPLACE(numero_documento, '-', ''), ' ', '')
                              AS INTEGER) AS TEXT)
                       THEN 'NIT con caracteres no numéricos (excluyendo guion)'
                     ELSE 'NIT con formato inválido'
                   END,
                   COALESCE(numero_documento, 'NULL'),
                   'formato: 99999999-9'
            FROM cca_interesado
            WHERE tipo_documento = '2'
              AND (numero_documento IS NULL
                   OR TRIM(numero_documento) = ''
                   OR numero_documento NOT LIKE '%-%')
        """,
    },
    # ------------------------------------------------------------------
    # NOMBRES / RAZÓN SOCIAL (RJ-17 a RJ-22)
    # ------------------------------------------------------------------
    {
        "id": "RJ-17",
        "descripcion": (
            "nombre_interesado de Persona Natural no debe contener números "
            "ni caracteres especiales"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, 'SIN NOMBRE'),
                   'nombre_interesado contiene números o caracteres especiales',
                   nombre_interesado,
                   'solo letras, espacios y guiones'
            FROM cca_interesado
            WHERE tipo_interesado = '0'
              AND nombre_interesado IS NOT NULL
              AND TRIM(nombre_interesado) <> ''
              AND (nombre_interesado GLOB '*[0-9]*'
                   OR nombre_interesado LIKE '%@%'
                   OR nombre_interesado LIKE '%#%'
                   OR nombre_interesado LIKE '%$%'
                   OR nombre_interesado LIKE '%&%'
                   OR nombre_interesado LIKE '%*%'
                   OR nombre_interesado LIKE '%/%'
                   OR nombre_interesado LIKE '%.%'
                   OR nombre_interesado LIKE '%,%'
                   OR nombre_interesado LIKE '%;%'
                   OR nombre_interesado LIKE '%:%'
                   OR nombre_interesado LIKE '%!%'
                   OR nombre_interesado LIKE '%+%'
                   OR nombre_interesado LIKE '%=%'
                   OR nombre_interesado LIKE '%(%'
                   OR nombre_interesado LIKE '%)%')
        """,
    },
    {
        "id": "RJ-18",
        "descripcion": (
            "Persona Jurídica no debe usar nombre_interesado; debe usar "
            "razon_social"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(razon_social, 'SIN RAZON SOCIAL'),
                   'Persona Jurídica con nombre_interesado diligenciado',
                   nombre_interesado,
                   'nombre_interesado vacío o NULL'
            FROM cca_interesado
            WHERE tipo_interesado = '1'
              AND nombre_interesado IS NOT NULL
              AND TRIM(nombre_interesado) <> ''
        """,
    },
    {
        "id": "RJ-19",
        "descripcion": (
            "nombre_interesado de Persona Natural no debe contener "
            "referencias a sucesiones ilíquidas (SUC)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, 'SIN NOMBRE'),
                   'nombre_interesado contiene referencia a sucesión (SUC)',
                   nombre_interesado,
                   'sin referencias a sucesiones en el nombre'
            FROM cca_interesado
            WHERE tipo_interesado = '0'
              AND nombre_interesado IS NOT NULL
              AND (UPPER(nombre_interesado) LIKE '%SUC %'
                   OR UPPER(nombre_interesado) LIKE '%SUC.%'
                   OR UPPER(nombre_interesado) LIKE 'SUC%'
                   OR UPPER(nombre_interesado) LIKE '%SUCESION%')
        """,
    },
    {
        "id": "RJ-20",
        "descripcion": (
            "razon_social solo debe estar diligenciada para Persona Jurídica"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, 'SIN NOMBRE'),
                   'Persona Natural con razon_social diligenciada',
                   razon_social,
                   'razon_social vacía o NULL para Persona Natural'
            FROM cca_interesado
            WHERE tipo_interesado = '0'
              AND razon_social IS NOT NULL
              AND TRIM(razon_social) <> ''
        """,
    },
    {
        "id": "RJ-21",
        "descripcion": (
            "El atributo sexo solo debe usarse para Persona Natural"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(razon_social, 'SIN RAZON SOCIAL'),
                   'Persona Jurídica con campo sexo diligenciado',
                   sexo,
                   'sexo NULL para Persona Jurídica'
            FROM cca_interesado
            WHERE tipo_interesado = '1'
              AND sexo IS NOT NULL
        """,
    },
    {
        "id": "RJ-22",
        "descripcion": (
            "Persona Natural no debe asociar razón social en lugar de "
            "nombre de persona"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', T_Id,
                   COALESCE(nombre_interesado, 'SIN NOMBRE'),
                   'Persona Natural sin nombre_interesado pero con razon_social',
                   COALESCE(razon_social, 'NULL'),
                   'nombre_interesado diligenciado'
            FROM cca_interesado
            WHERE tipo_interesado = '0'
              AND (nombre_interesado IS NULL OR TRIM(nombre_interesado) = '')
              AND razon_social IS NOT NULL
              AND TRIM(razon_social) <> ''
        """,
    },
    # ------------------------------------------------------------------
    # AGRUPACIONES (RJ-23 a RJ-26)
    # ------------------------------------------------------------------
    {
        "id": "RJ-23",
        "descripcion": (
            "Si la agrupación tiene Personas Naturales y Jurídicas, el "
            "tipo de agrupación debe ser Grupo_Mixto"
        ),
        "severidad": "error",
        "sql": """
            WITH composicion AS (
                SELECT a.T_Id AS agrup_id,
                       a.tipo_agrupacion,
                       a.nombre_agrupacion,
                       SUM(CASE WHEN i.tipo_interesado = '0' THEN 1 ELSE 0 END) AS n_natural,
                       SUM(CASE WHEN i.tipo_interesado = '1' THEN 1 ELSE 0 END) AS n_juridica
                FROM cca_agrupacioninteresados a
                JOIN cca_interesado_agrupacion ia ON ia.agrupacion = a.T_Id
                JOIN cca_interesado i ON i.T_Id = ia.interesado
                GROUP BY a.T_Id
            )
            SELECT 'cca_agrupacioninteresados', agrup_id,
                   COALESCE(nombre_agrupacion, 'SIN NOMBRE'),
                   'Agrupación mixta (naturales + jurídicas) con tipo incorrecto',
                   COALESCE(tipo_agrupacion, 'NULL'),
                   '3 (Grupo_Mixto)'
            FROM composicion
            WHERE n_natural > 0 AND n_juridica > 0
              AND (tipo_agrupacion IS NULL OR tipo_agrupacion <> '3')
        """,
    },
    {
        "id": "RJ-24",
        "descripcion": (
            "Si la agrupación solo tiene Personas Naturales, el tipo de "
            "agrupación debe ser Grupo_Civil"
        ),
        "severidad": "error",
        "sql": """
            WITH composicion AS (
                SELECT a.T_Id AS agrup_id,
                       a.tipo_agrupacion,
                       a.nombre_agrupacion,
                       SUM(CASE WHEN i.tipo_interesado = '0' THEN 1 ELSE 0 END) AS n_natural,
                       SUM(CASE WHEN i.tipo_interesado = '1' THEN 1 ELSE 0 END) AS n_juridica
                FROM cca_agrupacioninteresados a
                JOIN cca_interesado_agrupacion ia ON ia.agrupacion = a.T_Id
                JOIN cca_interesado i ON i.T_Id = ia.interesado
                GROUP BY a.T_Id
            )
            SELECT 'cca_agrupacioninteresados', agrup_id,
                   COALESCE(nombre_agrupacion, 'SIN NOMBRE'),
                   'Agrupación solo de Personas Naturales con tipo incorrecto',
                   COALESCE(tipo_agrupacion, 'NULL'),
                   '0 (Grupo_Civil)'
            FROM composicion
            WHERE n_natural > 0 AND n_juridica = 0
              AND (tipo_agrupacion IS NULL OR tipo_agrupacion <> '0')
        """,
    },
    {
        "id": "RJ-25",
        "descripcion": (
            "Si la agrupación solo tiene Personas Jurídicas, el tipo de "
            "agrupación debe ser Grupo_Empresarial"
        ),
        "severidad": "error",
        "sql": """
            WITH composicion AS (
                SELECT a.T_Id AS agrup_id,
                       a.tipo_agrupacion,
                       a.nombre_agrupacion,
                       SUM(CASE WHEN i.tipo_interesado = '0' THEN 1 ELSE 0 END) AS n_natural,
                       SUM(CASE WHEN i.tipo_interesado = '1' THEN 1 ELSE 0 END) AS n_juridica
                FROM cca_agrupacioninteresados a
                JOIN cca_interesado_agrupacion ia ON ia.agrupacion = a.T_Id
                JOIN cca_interesado i ON i.T_Id = ia.interesado
                GROUP BY a.T_Id
            )
            SELECT 'cca_agrupacioninteresados', agrup_id,
                   COALESCE(nombre_agrupacion, 'SIN NOMBRE'),
                   'Agrupación solo de Personas Jurídicas con tipo incorrecto',
                   COALESCE(tipo_agrupacion, 'NULL'),
                   '1 (Grupo_Empresarial)'
            FROM composicion
            WHERE n_natural = 0 AND n_juridica > 0
              AND (tipo_agrupacion IS NULL OR tipo_agrupacion <> '1')
        """,
    },
    {
        "id": "RJ-26",
        "descripcion": (
            "La suma del porcentaje de participación de la agrupación "
            "debe ser coherente (1 si FMI detalla porcentaje, 0/NULL "
            "en caso contrario)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_agrupacioninteresados', a.T_Id,
                   COALESCE(a.nombre_agrupacion, 'SIN NOMBRE'),
                   'porcentaje_participacion diligenciado pero <> 0 y <> 1',
                   COALESCE(CAST(a.porcentaje_participacion AS TEXT), 'NULL'),
                   '0 o 1'
            FROM cca_agrupacioninteresados a
            WHERE a.porcentaje_participacion IS NOT NULL
              AND a.porcentaje_participacion <> 0
              AND ABS(a.porcentaje_participacion - 1.0) > 0.001
        """,
    },
    # ------------------------------------------------------------------
    # FUENTE ADMINISTRATIVA (RJ-27, RJ-28)
    # ------------------------------------------------------------------
    {
        "id": "RJ-27",
        "descripcion": (
            "El registro de ente emisor, número de fuente y fecha de "
            "documento debe ser congruente con el tipo de fuente"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_fuenteadministrativa', f.T_Id,
                   COALESCE(f.nombre_fuente, 'SIN NOMBRE'),
                   CASE
                     WHEN f.tipo_fuente = '4'
                       THEN 'tipo_fuente es Sin_Documento pero tiene datos diligenciados'
                     ELSE 'tipo_fuente requiere ente_emisor/nombre_fuente/fecha_fuente completos'
                   END,
                   printf('tipo=%s ente=%s nombre=%s fecha=%s',
                          f.tipo_fuente,
                          COALESCE(f.ente_emisor, 'NULL'),
                          COALESCE(f.nombre_fuente, 'NULL'),
                          COALESCE(f.fecha_fuente, 'NULL')),
                   'datos congruentes con tipo de fuente'
            FROM cca_fuenteadministrativa f
            WHERE (f.tipo_fuente IN ('0','1','2','3')
                   AND (f.ente_emisor IS NULL OR TRIM(f.ente_emisor) = ''
                        OR f.nombre_fuente IS NULL OR TRIM(f.nombre_fuente) = ''
                        OR f.fecha_fuente IS NULL OR TRIM(f.fecha_fuente) = ''))
               OR (f.tipo_fuente = '4'
                   AND (f.ente_emisor IS NOT NULL AND TRIM(f.ente_emisor) <> ''
                        AND f.nombre_fuente IS NOT NULL AND TRIM(f.nombre_fuente) <> ''))
        """,
    },
    {
        "id": "RJ-28",
        "descripcion": (
            "El ente emisor debe corresponder al tipo de fuente "
            "administrativa (ej: Escritura Publica - Notaria)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_fuenteadministrativa', T_Id,
                   COALESCE(nombre_fuente, 'SIN NOMBRE'),
                   'ente_emisor no parece corresponder al tipo_fuente',
                   printf('tipo=%s ente=%s', tipo_fuente, ente_emisor),
                   CASE tipo_fuente
                     WHEN '0' THEN 'ente con NOTARI'
                     WHEN '1' THEN 'ente con JUZGADO o TRIBUNAL'
                     WHEN '2' THEN 'ente con entidad administrativa'
                     ELSE 'verificar manualmente'
                   END
            FROM cca_fuenteadministrativa
            WHERE ente_emisor IS NOT NULL
              AND TRIM(ente_emisor) <> ''
              AND (
                  (tipo_fuente = '0'
                   AND UPPER(ente_emisor) NOT LIKE '%NOTARI%')
                  OR (tipo_fuente = '1'
                   AND UPPER(ente_emisor) NOT LIKE '%JUZGADO%'
                   AND UPPER(ente_emisor) NOT LIKE '%TRIBUNAL%'
                   AND UPPER(ente_emisor) NOT LIKE '%CORTE%')
              )
        """,
    },
    # ------------------------------------------------------------------
    # PREDIO ↔ INTERESADO (RJ-29)
    # ------------------------------------------------------------------
    {
        "id": "RJ-29",
        "descripcion": (
            "Todo predio debe tener asociado un interesado o agrupación "
            "de interesados a través de un derecho"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_predio', p.T_Id, p.numero_predial_nacional,
                   CASE
                     WHEN d.T_Id IS NULL
                       THEN 'Predio sin derecho asociado'
                     ELSE 'Derecho sin interesado ni agrupación'
                   END,
                   'sin interesado',
                   'al menos un interesado o agrupación'
            FROM cca_predio p
            LEFT JOIN cca_derechocatastral d ON d.predio = p.T_Id
            WHERE d.T_Id IS NULL
               OR (d.interesado IS NULL AND d.agrupacion IS NULL)
        """,
    },
    # ------------------------------------------------------------------
    # DUPLICADOS Y HOMÓNIMOS (RJ-30, RJ-31)
    # ------------------------------------------------------------------
    {
        "id": "RJ-30",
        "descripcion": (
            "Interesados con igual nombre/razón social pero diferente "
            "número de documento deben verificarse (posibles homónimos)"
        ),
        "severidad": "advertencia",
        "sql": """
            SELECT 'cca_interesado', a.T_Id,
                   COALESCE(a.nombre_interesado, a.razon_social, 'SIN NOMBRE'),
                   'Posible homónimo: mismo nombre, diferente documento',
                   printf('doc_a=%s doc_b=%s', a.numero_documento, b.numero_documento),
                   'verificar si son personas distintas'
            FROM cca_interesado a
            JOIN cca_interesado b
              ON UPPER(TRIM(COALESCE(a.nombre_interesado, a.razon_social, '')))
               = UPPER(TRIM(COALESCE(b.nombre_interesado, b.razon_social, '')))
              AND a.T_Id < b.T_Id
            WHERE COALESCE(a.nombre_interesado, a.razon_social, '') <> ''
              AND a.numero_documento <> b.numero_documento
        """,
    },
    {
        "id": "RJ-31",
        "descripcion": (
            "No deben existir dos interesados con el mismo número de "
            "documento"
        ),
        "severidad": "error",
        "sql": """
            SELECT 'cca_interesado', i.T_Id,
                   COALESCE(i.nombre_interesado, i.razon_social, 'SIN NOMBRE'),
                   'numero_documento duplicado',
                   i.numero_documento,
                   'único'
            FROM cca_interesado i
            WHERE i.numero_documento IS NOT NULL
              AND TRIM(i.numero_documento) <> ''
              AND i.numero_documento IN (
                  SELECT numero_documento FROM cca_interesado
                  WHERE numero_documento IS NOT NULL
                    AND TRIM(numero_documento) <> ''
                  GROUP BY numero_documento
                  HAVING COUNT(*) > 1
              )
        """,
    },
]
