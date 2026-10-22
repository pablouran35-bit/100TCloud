"""Edición administrativa de PC. Guarda el documento completo y su auditoría juntos."""
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import conexion

AZUL = '#223C61'
FONDO = '#F5F0E6'
CAMPOS = ('persona_id', 'producto_id', 'area_id', 'cantidad', 'observaciones',
          'fecha_solicitud', 'estado', 'proveedor_id')


def _administrador(cursor, usuario_id):
    cursor.execute('''SELECT 1 FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id
                      WHERE ur.usuario_id=%s AND UPPER(TRIM(r.nombre))='ADMINISTRADOR' ''', (usuario_id,))
    if not cursor.fetchone():
        raise PermissionError('Solo un administrador puede editar planillas.')


def _documento(cursor, planilla_id, bloquear=False):
    cursor.execute('''SELECT id, obra_id, fecha_compra, estado, observaciones,
                      estado_aprobacion, aprobada_por, fecha_aprobacion, motivo_aprobacion
                      FROM planillas WHERE id=%s''' + (' FOR UPDATE' if bloquear else ''), (planilla_id,))
    p = cursor.fetchone()
    if not p:
        raise ValueError('La planilla ya no existe.')
    nombres = ('id', 'obra_id', 'fecha_compra', 'estado', 'observaciones',
               'estado_aprobacion', 'aprobada_por', 'fecha_aprobacion', 'motivo_aprobacion')
    doc = dict(zip(nombres, p))
    cursor.execute('''SELECT s.id,s.persona_id,s.producto_id,s.area_id,s.cantidad,
                      s.observaciones,s.fecha_solicitud,s.estado,s.proveedor_id,s.obra_id
                      FROM planilla_solicitudes ps JOIN solicitudes s ON s.id=ps.solicitud_id
                      WHERE ps.planilla_id=%s ORDER BY s.id''' + (' FOR UPDATE OF s' if bloquear else ''), (planilla_id,))
    doc['solicitudes'] = [dict(zip(('id',) + CAMPOS + ('obra_id',), fila)) for fila in cursor.fetchall()]
    return json.loads(_serializar(doc))


def _serializar(doc):
    return json.dumps(doc, default=str, ensure_ascii=False, sort_keys=True)


def cargar(planilla_id, usuario_id):
    c = conexion.conectar()
    try:
        q = c.cursor(); _administrador(q, usuario_id)
        doc = _documento(q, planilla_id)
        opciones = {}
        # Incluir también catálogos inactivos para poder mantener valores históricos.
        for tabla in ('obras', 'productos', 'areas', 'proveedores'):
            q.execute('SELECT id,nombre FROM ' + tabla + ' ORDER BY nombre')
            opciones[tabla] = q.fetchall()
        q.execute("SELECT id,TRIM(COALESCE(nombre,'') || ' ' || COALESCE(apellido,'')) FROM personas ORDER BY nombre,apellido")
        opciones['personas'] = q.fetchall()
        return doc, opciones
    finally:
        c.close()


def _fecha(valor, hora=False):
    texto = str(valor).strip()
    try:
        if hora:
            valor = datetime.fromisoformat(texto)
            return valor if valor.tzinfo else valor.replace(tzinfo=timezone(timedelta(hours=-3)))
        return datetime.strptime(texto, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError('Ingresá las fechas como AAAA-MM-DD; para solicitudes podés agregar HH:MM:SS.')


def guardar(planilla_id, usuario_id, anterior, cambios):
    """Revalida rol y documento bajo bloqueo; nunca toca compras ni retiros."""
    fecha = _fecha(cambios['fecha_compra'])
    solicitudes = cambios['solicitudes']
    if set(s['id'] for s in solicitudes) != set(s['id'] for s in anterior['solicitudes']) or len(solicitudes) != len(anterior['solicitudes']):
        raise ValueError('La lista de solicitudes no coincide con la planilla abierta.')
    for s in solicitudes:
        try:
            cantidad = Decimal(str(s['cantidad']).replace(',', '.'))
        except InvalidOperation:
            raise ValueError('La cantidad debe ser un número positivo.')
        if not cantidad.is_finite() or cantidad <= 0:
            raise ValueError('La cantidad debe ser un número positivo.')
        s['cantidad'] = cantidad
        _fecha(s['fecha_solicitud'], True)
        if not str(s['estado'] or '').strip():
            raise ValueError('Cada solicitud debe tener un estado.')
    if not cambios.get('estado') or cambios.get('estado_aprobacion') not in ('APROBADA', 'PENDIENTE'):
        raise ValueError('Revisá el estado y la aprobación de la planilla.')
    c = conexion.conectar()
    try:
        q = c.cursor(); _administrador(q, usuario_id)
        actual = _documento(q, planilla_id, True)
        if _serializar(actual) != _serializar(anterior):
            raise ValueError('Otra persona modificó la planilla. Cerrá el editor y volvé a abrirla antes de guardar.')
        q.execute('SELECT id FROM obras WHERE id=%s', (cambios['obra_id'],))
        if not q.fetchone():
            raise ValueError('La obra seleccionada ya no existe.')
        # Una solicitud compartida no puede cambiar de obra solo en uno de sus documentos.
        q.execute('''SELECT ps.solicitud_id FROM planilla_solicitudes ps
                     WHERE ps.planilla_id<>%s AND ps.solicitud_id IN
                     (SELECT solicitud_id FROM planilla_solicitudes WHERE planilla_id=%s) LIMIT 1''', (planilla_id, planilla_id))
        if q.fetchone() and str(actual['obra_id']) != str(cambios['obra_id']):
            raise ValueError('Hay solicitudes compartidas con otra planilla. No se puede cambiar su obra desde un solo documento.')
        for s in solicitudes:
            for campo, tabla in (('persona_id', 'personas'), ('producto_id', 'productos'), ('area_id', 'areas'), ('proveedor_id', 'proveedores')):
                if s[campo] is None and campo == 'proveedor_id':
                    continue
                q.execute('SELECT id FROM ' + tabla + ' WHERE id=%s', (s[campo],))
                if not q.fetchone():
                    raise ValueError('Revisá los datos de la solicitud ' + str(s['id']) + ': ' + campo)
        q.execute('''UPDATE planillas SET obra_id=%s,fecha_compra=%s,estado=%s,observaciones=%s,estado_aprobacion=%s,
                     aprobada_por=CASE WHEN %s='APROBADA' THEN COALESCE(aprobada_por,%s) ELSE NULL END,
                     fecha_aprobacion=CASE WHEN %s='APROBADA' THEN COALESCE(fecha_aprobacion,CURRENT_TIMESTAMP) ELSE NULL END
                     WHERE id=%s''', (cambios['obra_id'], fecha, cambios['estado'], cambios['observaciones'],
                     cambios['estado_aprobacion'], cambios['estado_aprobacion'], usuario_id, cambios['estado_aprobacion'], planilla_id))
        anteriores = {s['id']: s for s in actual['solicitudes']}
        for s in solicitudes:
            antes = anteriores[s['id']]
            q.execute('''UPDATE solicitudes SET persona_id=%s,producto_id=%s,area_id=%s,cantidad=%s,observaciones=%s,
                         fecha_solicitud=CASE WHEN %s THEN CAST(%s AS timestamptz) ELSE fecha_solicitud END,
                         estado=%s,proveedor_id=%s,obra_id=%s WHERE id=%s''',
                      tuple(s[k] for k in CAMPOS[:5]) +
                      (str(s['fecha_solicitud']) != str(antes['fecha_solicitud']), _fecha(s['fecha_solicitud'], True),
                       s['estado'], s['proveedor_id'], cambios['obra_id'], s['id']))
            diferencias = {k: {'antes': antes[k], 'despues': s[k]} for k in CAMPOS if str(antes[k] or '') != str(s[k] or '')}
            if str(antes['obra_id']) != str(cambios['obra_id']):
                diferencias['obra_id'] = {'antes': antes['obra_id'], 'despues': cambios['obra_id']}
            if diferencias or any(str(actual[k] or '') != str(cambios[k] or '') for k in ('fecha_compra','estado','observaciones','estado_aprobacion')):
                q.execute('''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                             VALUES(%s,%s,CURRENT_TIMESTAMP,%s,%s)''', (s['id'], s['estado'],
                             'Edición administrativa Cloud de planilla ' + str(planilla_id) + ': ' + _serializar(diferencias), usuario_id))
        # Auditoría del documento completo, incluso si la planilla está vacía.
        q.execute('''CREATE TABLE IF NOT EXISTS historial_ediciones_planillas (
                     id BIGSERIAL PRIMARY KEY,planilla_id BIGINT NOT NULL REFERENCES planillas(id),
                     usuario_id BIGINT NOT NULL REFERENCES usuarios(id),fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                     antes JSONB NOT NULL,despues JSONB NOT NULL)''')
        despues = _documento(q, planilla_id)
        q.execute('''INSERT INTO historial_ediciones_planillas(planilla_id,usuario_id,antes,despues)
                     VALUES(%s,%s,CAST(%s AS jsonb),CAST(%s AS jsonb))''',
                  (planilla_id, usuario_id, _serializar(actual), _serializar(despues)))
        c.commit()
        return despues
    except Exception:
        c.rollback(); raise
    finally:
        c.close()


def listar(usuario_id):
    c=conexion.conectar()
    try:
        q=c.cursor(); _administrador(q,usuario_id)
        q.execute("SELECT p.id,o.nombre,p.fecha_compra FROM planillas p JOIN obras o ON o.id=p.obra_id ORDER BY p.fecha_compra DESC,p.id DESC LIMIT 1000")
        return [dict(zip(('id','obra','fecha_compra'),f)) for f in q.fetchall()]
    finally:
        c.close()
