import conexion


def obtener_catalogos():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM obras ORDER BY nombre;")
            obras = cursor.fetchall()
            cursor.execute("""
                SELECT p.id, concat_ws(' ', p.nombre, p.apellido)
                FROM personas AS p
                ORDER BY p.apellido, p.nombre;
            """)
            personas = cursor.fetchall()
            cursor.execute("SELECT id, nombre FROM productos ORDER BY nombre;")
            productos = cursor.fetchall()
            cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre;")
            proveedores = cursor.fetchall()
            cursor.execute("SELECT id, nombre FROM areas ORDER BY id;")
            areas = cursor.fetchall()
            cursor.execute("SELECT id FROM planillas ORDER BY id DESC;")
            planillas = cursor.fetchall()
            cursor.execute("""
                SELECT DISTINCT estado FROM solicitudes
                WHERE estado IS NOT NULL ORDER BY estado;
            """)
            estados = cursor.fetchall()
        return {
            "obras": [{"id": x[0], "nombre": x[1]} for x in obras],
            "personas": [{"id": x[0], "nombre": x[1]} for x in personas],
            "productos": [{"id": x[0], "nombre": x[1]} for x in productos],
            "proveedores": [{"id": x[0], "nombre": x[1]} for x in proveedores],
            "areas": [{"id": x[0], "nombre": x[1]} for x in areas],
            "planillas": [{"id": x[0], "nombre": f"Planilla N.º {x[0]}"} for x in planillas],
            "estados": [x[0] for x in estados],
        }
    finally:
        conexion_db.close()


def _ejecutar(sql, parametros=()):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute(sql, parametros)
            columnas = [columna.name for columna in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion_db.close()


def _agregar_filtros(sql, parametros, filtros, columnas_fecha):
    for columna, valor in filtros.values():
        if columna is not None and valor is not None:
            sql += f" AND {columna} = %s"
            parametros.append(valor)
    _, desde = filtros.get("desde", (None, None))
    _, hasta = filtros.get("hasta", (None, None))
    if desde:
        sql += f" AND {columnas_fecha} >= %s"
        parametros.append(desde)
    if hasta:
        sql += f" AND {columnas_fecha} < (%s::date + INTERVAL '1 day')"
        parametros.append(hasta)
    return sql, parametros


def solicitudes(obra_id=None, persona_id=None, producto_id=None,
                proveedor_id=None, area_id=None, estado=None,
                desde=None, hasta=None):
    sql = """
        SELECT s.id AS solicitud, o.nombre AS obra,
               concat_ws(' ', per.nombre, per.apellido) AS solicitante,
               COALESCE(pr.nombre, 'Artículo no disponible') AS articulo,
               COALESCE(prov.nombre, 'SIN PROVEEDOR') AS proveedor,
               s.cantidad, COALESCE(a.nombre, '') AS area,
               COALESCE(s.estado, '') AS estado, s.fecha_solicitud AS fecha,
               COALESCE(s.observaciones, '') AS observaciones
        FROM solicitudes AS s
        LEFT JOIN obras AS o ON o.id = s.obra_id
        LEFT JOIN personas AS per ON per.id = s.persona_id
        LEFT JOIN productos AS pr ON pr.id = s.producto_id
        LEFT JOIN proveedores AS prov ON prov.id = s.proveedor_id
        LEFT JOIN areas AS a ON a.id = s.area_id
        WHERE TRUE
    """
    sql, params = _agregar_filtros(sql, [], {
        "obra_id": ("s.obra_id", obra_id),
        "persona_id": ("s.persona_id", persona_id),
        "producto_id": ("s.producto_id", producto_id),
        "proveedor_id": ("s.proveedor_id", proveedor_id),
        "area_id": ("s.area_id", area_id),
        "estado": ("s.estado", estado),
        "desde": (None, desde),
        "hasta": (None, hasta),
    }, "s.fecha_solicitud")
    return _ejecutar(sql + " ORDER BY s.id DESC;", params)


def compras(planilla_id=None, obra_id=None, producto_id=None,
            proveedor_id=None, estado=None, desde=None, hasta=None):
    sql = """
        SELECT p.id AS planilla, o.nombre AS obra, s.id AS solicitud,
               COALESCE(pr.nombre, 'Artículo no disponible') AS articulo,
               s.cantidad, COALESCE(prov.nombre, 'SIN PROVEEDOR') AS proveedor,
               COALESCE(s.estado, '') AS estado, s.fecha_solicitud AS fecha,
               COALESCE(s.observaciones, '') AS observaciones
        FROM planillas AS p
        JOIN planilla_solicitudes AS ps ON ps.planilla_id = p.id
        JOIN solicitudes AS s ON s.id = ps.solicitud_id
        LEFT JOIN obras AS o ON o.id = s.obra_id
        LEFT JOIN productos AS pr ON pr.id = s.producto_id
        LEFT JOIN proveedores AS prov ON prov.id = s.proveedor_id
        WHERE TRUE
    """
    sql, params = _agregar_filtros(sql, [], {
        "planilla_id": ("p.id", planilla_id),
        "obra_id": ("s.obra_id", obra_id),
        "producto_id": ("s.producto_id", producto_id),
        "proveedor_id": ("s.proveedor_id", proveedor_id),
        "estado": ("s.estado", estado),
        "desde": (None, desde),
        "hasta": (None, hasta),
    }, "s.fecha_solicitud")
    return _ejecutar(sql + " ORDER BY p.id DESC, s.id DESC;", params)


def entregas(entrega_id=None, obra_id=None, producto_id=None,
             usuario_id=None, desde=None, hasta=None):
    sql = """
        SELECT hs.id AS entrega, s.id AS solicitud, o.nombre AS obra,
               COALESCE(pr.nombre, 'Artículo no disponible') AS articulo,
               s.cantidad, COALESCE(concat_ws(' ', per.nombre, per.apellido),
                    u.usuario, 'Usuario no disponible') AS entregado_por,
               hs.fecha_hora AS fecha,
               COALESCE(hs.observaciones, '') AS observaciones
        FROM historial_solicitudes AS hs
        JOIN solicitudes AS s ON s.id = hs.solicitud_id
        LEFT JOIN obras AS o ON o.id = s.obra_id
        LEFT JOIN productos AS pr ON pr.id = s.producto_id
        LEFT JOIN usuarios AS u ON u.id = hs.usuario_id
        LEFT JOIN personas AS per ON per.id = u.persona_id
        WHERE UPPER(COALESCE(hs.estado, '')) = 'ENTREGADO'
    """
    sql, params = _agregar_filtros(sql, [], {
        "entrega_id": ("hs.id", entrega_id),
        "obra_id": ("s.obra_id", obra_id),
        "producto_id": ("s.producto_id", producto_id),
        "usuario_id": ("hs.usuario_id", usuario_id),
        "desde": (None, desde),
        "hasta": (None, hasta),
    }, "hs.fecha_hora")
    return _ejecutar(sql + " ORDER BY hs.fecha_hora DESC, hs.id DESC;", params)


def obras():
    return _ejecutar("""
        SELECT o.id, o.nombre AS obra, COALESCE(o.direccion, '') AS direccion,
               COALESCE((
                   SELECT string_agg(c.nombre, ', ' ORDER BY c.nombre)
                   FROM (
                       SELECT DISTINCT concat_ws(' ', p.nombre, p.apellido) AS nombre
                       FROM persona_obra AS po
                       JOIN personas AS p ON p.id = po.persona_id
                       JOIN usuarios AS u ON u.persona_id = p.id
                       JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                       JOIN roles AS r ON r.id = ur.rol_id
                       WHERE po.obra_id = o.id AND UPPER(r.nombre) = 'CONTRATISTA'
                   ) AS c
               ), 'SIN CONTRATISTA ASIGNADO') AS contratistas,
               o.activo
        FROM obras AS o ORDER BY o.nombre;
    """)
