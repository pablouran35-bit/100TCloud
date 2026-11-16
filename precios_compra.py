"""Precio real por renglón de compra, separado del precio de referencia."""
from decimal import Decimal, InvalidOperation


def validar(valor):
    if valor is None or str(valor).strip() == '':
        return None
    try:
        precio = Decimal(str(valor).strip().replace(',', '.'))
    except InvalidOperation:
        raise ValueError('Ingresá un precio unitario válido, sin separador de miles.')
    if not precio.is_finite() or precio < 0 or precio > Decimal('999999999999.99') or precio != precio.quantize(Decimal('.01')):
        raise ValueError('El precio debe ser positivo o cero, con hasta dos decimales.')
    return precio


def migrar(conectar):
    db = conectar()
    try:
        with db, db.cursor() as q:
            q.execute('''CREATE TABLE IF NOT EXISTS precios_reales_compra (
                solicitud_id BIGINT PRIMARY KEY REFERENCES solicitudes(id),
                precio_unitario NUMERIC(14,2) CHECK(precio_unitario >= 0),
                revision BIGINT NOT NULL DEFAULT 1,
                usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
                actualizado TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    finally:
        db.close()


def _solicitud(q, solicitud_id, usuario_id, bloquear=False):
    q.execute('''SELECT 1 FROM usuarios u JOIN personas pe ON pe.id=u.persona_id JOIN usuario_rol ur ON ur.usuario_id=u.id
        JOIN roles r ON r.id=ur.rol_id WHERE u.id=%s AND pe.activo=TRUE
        AND UPPER(TRIM(r.nombre)) IN ('ADMINISTRADOR','EMPLEADO')''', (usuario_id,))
    if not q.fetchone():
        raise PermissionError('No tenés permiso para gestionar precios de compra.')
    q.execute('''SELECT s.cantidad,s.estado,p.nombre,p.unidad FROM solicitudes s
        JOIN productos p ON p.id=s.producto_id WHERE s.id=%s'''
        + (' FOR UPDATE OF s' if bloquear else ''), (solicitud_id,))
    solicitud = q.fetchone()
    if not solicitud:
        raise ValueError('No se encontró la solicitud.')
    return solicitud


def _precio(q, solicitud_id, solicitud):
    q.execute('SELECT precio_unitario,revision FROM precios_reales_compra WHERE solicitud_id=%s', (solicitud_id,))
    fila = q.fetchone()
    precio, revision = fila if fila else (None, 0)
    if precio is not None:
        precio = Decimal(str(precio))
    return dict(precio_unitario=str(precio) if precio is not None else None,
                revision=revision, articulo=solicitud[2], unidad=solicitud[3],
                total=str((Decimal(str(solicitud[0])) * precio).quantize(Decimal('.01'))) if precio is not None else None)


def obtener(conectar, solicitud_id, usuario_id):
    db = conectar()
    try:
        with db.cursor() as q:
            solicitud = _solicitud(q, solicitud_id, usuario_id)
            return _precio(q, solicitud_id, solicitud)
    finally:
        db.close()


def guardar(conectar, solicitud_id, usuario_id, valor, revision):
    precio = validar(valor)
    db = conectar()
    try:
        with db, db.cursor() as q:
            solicitud = _solicitud(q, solicitud_id, usuario_id, True)
            anterior = _precio(q, solicitud_id, solicitud)
            if anterior['revision'] != revision:
                raise ValueError('Otra persona cambió el precio. Volvé a abrirlo antes de guardar.')
            if str(solicitud[1]).strip().upper() in ('CANCELADA', 'RECHAZADA'):
                raise ValueError('La solicitud está cancelada o rechazada.')
            q.execute('''INSERT INTO precios_reales_compra(solicitud_id,precio_unitario,usuario_id)
                VALUES(%s,%s,%s) ON CONFLICT(solicitud_id) DO UPDATE SET
                precio_unitario=EXCLUDED.precio_unitario,usuario_id=EXCLUDED.usuario_id,
                revision=precios_reales_compra.revision+1,actualizado=CURRENT_TIMESTAMP''',
                (solicitud_id, precio, usuario_id))
            q.execute('''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                VALUES(%s,%s,CURRENT_TIMESTAMP,%s,%s)''',
                (solicitud_id, solicitud[1], 'Precio unitario real: '+str(anterior['precio_unitario'])+' → '+(str(precio) if precio is not None else 'Sin precio'), usuario_id))
            return _precio(q, solicitud_id, solicitud)
    finally:
        db.close()
