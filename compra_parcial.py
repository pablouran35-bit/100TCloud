"""Compra una parte y conserva el saldo como solicitud pendiente en la planilla."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from uuid import UUID, uuid4
from psycopg2.extras import Json

PENDIENTES=('PENDIENTE DE COMPRA','SOLICITADO','PENDIENTE','ENCARGADO','NO DISPONIBLE')
COMPRADOS=('COMPRADO Y RETIRADO','COMPRADO A RETIRAR','COMPRADO A ENTREGAR POR PROVEEDOR/FLETE')
MIGRACION='''CREATE TABLE IF NOT EXISTS divisiones_compra (
    operacion_id UUID PRIMARY KEY,
    solicitud_comprada_id BIGINT NOT NULL REFERENCES solicitudes(id),
    solicitud_pendiente_id BIGINT NOT NULL REFERENCES solicitudes(id),
    cantidad_original NUMERIC NOT NULL CHECK(cantidad_original>0),
    cantidad_comprada NUMERIC NOT NULL CHECK(cantidad_comprada>0 AND cantidad_comprada<cantidad_original),
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    creada_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    contenido TEXT NOT NULL,
    resultado JSONB NOT NULL
)'''

def migrar(conectar):
    db=conectar()
    try:
        with db,db.cursor() as q:q.execute(MIGRACION)
    finally:db.close()

def cantidad(valor):
    try:
        n=Decimal(str(valor).strip().replace(',','.'))
        if not n.is_finite() or n<=0 or n>Decimal('999999999999') or n!=n.quantize(Decimal('.000001')):raise ValueError
        return n
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError('Ingresá una cantidad positiva, con hasta seis decimales.') from None

def guardar(conectar,planilla_id,solicitud_id,usuario_id,comprada,total_anterior,estado_anterior,proveedor_id,estado_compra,operacion_id):
    comprada=cantidad(comprada);total_anterior=cantidad(total_anterior)
    if comprada>=total_anterior:raise ValueError('Para una compra parcial, la cantidad debe ser menor que la pendiente. Para comprar todo, usá la gestión habitual.')
    if estado_compra not in COMPRADOS:raise ValueError('Elegí si lo comprado se retiró, queda a retirar o lo entrega el proveedor.')
    clave=str(UUID(str(operacion_id)))
    contenido=hashlib.sha256(json.dumps([planilla_id,solicitud_id,str(comprada.normalize()),str(total_anterior.normalize()),estado_anterior,proveedor_id,estado_compra],ensure_ascii=False).encode()).hexdigest()
    db=conectar()
    try:
        with db,db.cursor() as q:
            q.execute('''SELECT 1 FROM usuarios u JOIN personas p ON p.id=u.persona_id
                JOIN usuario_rol ur ON ur.usuario_id=u.id JOIN roles r ON r.id=ur.rol_id
                WHERE u.id=%s AND p.activo=TRUE AND UPPER(TRIM(r.nombre)) IN ('ADMINISTRADOR','EMPLEADO')''',(usuario_id,))
            if not q.fetchone():raise PermissionError('Solo empleados y administradores pueden registrar compras.')
            # Serializa reintentos de la misma operación antes de mirar el resultado.
            q.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(clave,))
            q.execute('SELECT usuario_id,contenido,resultado FROM divisiones_compra WHERE operacion_id=%s',(clave,))
            repetida=q.fetchone()
            if repetida:
                if repetida[:2]!=(usuario_id,contenido):raise ValueError('La clave del guardado pertenece a otra compra.')
                return repetida[2]
            q.execute('SELECT estado_aprobacion FROM planillas WHERE id=%s FOR UPDATE',(planilla_id,))
            p=q.fetchone()
            if not p or (p[0] or '').strip().upper()!='APROBADA':raise ValueError('La planilla debe estar aprobada.')
            q.execute('''SELECT s.cantidad,s.estado,s.proveedor_id FROM solicitudes s
                JOIN planilla_solicitudes ps ON ps.solicitud_id=s.id
                WHERE ps.planilla_id=%s AND s.id=%s FOR UPDATE OF s''',(planilla_id,solicitud_id))
            s=q.fetchone()
            if not s:raise ValueError('La solicitud no pertenece a esta planilla.')
            if Decimal(str(s[0]))!=total_anterior or s[1]!=estado_anterior:raise ValueError('La solicitud cambió. Volvé a abrirla antes de comprar una parte.')
            if (s[1] or '').strip().upper() not in PENDIENTES:raise ValueError('Solo se puede comprar una parte de una solicitud pendiente de compra. Lo comprado a retirar se gestiona como retiro.')
            q.execute('''SELECT EXISTS(SELECT 1 FROM movimientos_mercaderia WHERE solicitud_id=%s)
                OR EXISTS(SELECT 1 FROM compras WHERE solicitud_id=%s)''',(solicitud_id,solicitud_id))
            if q.fetchone()[0]:raise ValueError('La solicitud ya tiene compras o retiros. Recargá su estado antes de continuar.')
            q.execute('SELECT id FROM proveedores WHERE id=%s AND activo=TRUE FOR SHARE',(proveedor_id,))
            if not q.fetchone():raise ValueError('Elegí un proveedor activo para la parte comprada.')
            pendiente=total_anterior-comprada
            q.execute('''INSERT INTO solicitudes(persona_id,obra_id,producto_id,cantidad,observaciones,fecha_solicitud,estado,area_id,proveedor_id)
                SELECT persona_id,obra_id,producto_id,%s,observaciones,fecha_solicitud,'PENDIENTE DE COMPRA',area_id,NULL
                FROM solicitudes WHERE id=%s RETURNING id''',(pendiente,solicitud_id))
            saldo_id=q.fetchone()[0]
            q.execute('''INSERT INTO planilla_solicitudes(planilla_id,solicitud_id)
                SELECT planilla_id,%s FROM planilla_solicitudes WHERE solicitud_id=%s''',(saldo_id,solicitud_id))
            # Las fotos del detalle siguen acompañando al saldo sin comprar.
            q.execute('SELECT id FROM fotos_solicitudes WHERE solicitud_id=%s',(solicitud_id,))
            for foto, in q.fetchall():
                q.execute('''INSERT INTO fotos_solicitudes(id,solicitud_id,usuario_id,usuario_nombre,creada_en,imagen,miniatura,ancho,alto,huella)
                    SELECT %s,%s,usuario_id,usuario_nombre,creada_en,imagen,miniatura,ancho,alto,huella
                    FROM fotos_solicitudes WHERE id=%s''',(str(uuid4()),saldo_id,foto))
            q.execute('UPDATE solicitudes SET cantidad=%s,estado=%s,proveedor_id=%s WHERE id=%s',(comprada,estado_compra,proveedor_id,solicitud_id))
            texto=f'Compra parcial del pedido de {total_anterior}: {comprada} comprados en solicitud #{solicitud_id}; {pendiente} pendientes en solicitud #{saldo_id}.'
            for sid,estado in ((solicitud_id,estado_compra),(saldo_id,'PENDIENTE DE COMPRA')):
                q.execute('''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                    VALUES(%s,%s,CURRENT_TIMESTAMP,%s,%s)''',(sid,estado,texto,usuario_id))
            resultado=dict(solicitud_comprada_id=solicitud_id,solicitud_pendiente_id=saldo_id,cantidad_comprada=str(comprada),cantidad_pendiente=str(pendiente),mensaje=texto)
            q.execute('''INSERT INTO divisiones_compra(operacion_id,solicitud_comprada_id,solicitud_pendiente_id,cantidad_original,cantidad_comprada,usuario_id,contenido,resultado)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',(clave,solicitud_id,saldo_id,total_anterior,comprada,usuario_id,contenido,Json(resultado)))
            return resultado
    finally:db.close()
