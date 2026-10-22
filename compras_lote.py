"""Actualización atómica de solicitudes seleccionadas de una planilla."""
import json
import hashlib
import conexion
import offlinecloud
from comprascloud import ESTADOS_SOLICITUD

class ConflictoLote(ValueError):
    pass

def guardar(planilla_id, usuario_id, estado, proveedor_id, solicitudes, operacion_id):
    estado=estado.strip().upper()
    if estado not in ESTADOS_SOLICITUD:
        raise ValueError('Elegí un estado de compra válido.')
    ids=[s['id'] for s in solicitudes]
    if not ids or len(ids)!=len(set(ids)) or len(ids)>500:
        raise ValueError('Seleccioná entre 1 y 500 solicitudes sin repetir.')
    # Vincular la clave al contenido: un reintento idéntico no duplica historial.
    contenido=json.dumps([planilla_id,estado,proveedor_id,sorted(solicitudes,key=lambda s:s['id'])],sort_keys=True)
    recurso='compras:lote:'+hashlib.sha256(contenido.encode()).hexdigest()
    c=conexion.conectar()
    try:
        with c.cursor() as q:
            repetida=offlinecloud.iniciar_operacion(q,operacion_id,usuario_id,recurso)
            if repetida is not None:
                c.commit()
                return repetida
            q.execute('SELECT estado_aprobacion FROM planillas WHERE id=%s FOR UPDATE',(planilla_id,))
            p=q.fetchone()
            if not p or (p[0] or '').strip().upper()!='APROBADA':
                raise ValueError('La planilla no existe o no está aprobada.')
            if proveedor_id is not None:
                q.execute('SELECT id FROM proveedores WHERE id=%s AND activo=TRUE FOR SHARE',(proveedor_id,))
                if not q.fetchone():raise ValueError('El proveedor seleccionado no está activo.')
            q.execute('''SELECT s.id,s.estado,s.proveedor_id FROM solicitudes s
                         JOIN planilla_solicitudes ps ON ps.solicitud_id=s.id
                         WHERE ps.planilla_id=%s AND s.id=ANY(%s) ORDER BY s.id FOR UPDATE OF s''',(planilla_id,ids))
            filas=q.fetchall()
            if len(filas)!=len(ids):raise ValueError('Una solicitud no pertenece a esta planilla.')
            anteriores={s['id']:s for s in solicitudes}
            for sid,actual,proveedor in filas:
                if (actual or '').strip().upper() in ('ENTREGADO','CANCELADA','RECHAZADA','COMPRADO Y RETIRADO'):
                    raise ConflictoLote(f'La solicitud {sid} ya está finalizada. Recargá la planilla antes de continuar.')
                anterior=anteriores[sid]
                if actual!=anterior['estado_anterior'] or proveedor!=anterior['proveedor_anterior']:
                    raise ConflictoLote(f'Otra persona modificó la solicitud {sid}. No se guardó ninguna. Recargá la planilla.')
            cantidad=0
            for sid,actual,proveedor in filas:
                if actual==estado and proveedor==proveedor_id:continue
                q.execute('UPDATE solicitudes SET estado=%s,proveedor_id=%s WHERE id=%s',(estado,proveedor_id,sid))
                nota='Cambio conjunto desde Compras: '+json.dumps({'estado_anterior':actual,'proveedor_anterior':proveedor,'proveedor_nuevo':proveedor_id},ensure_ascii=False)
                q.execute('''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                             VALUES(%s,%s,NOW(),%s,%s)''',(sid,estado,nota,usuario_id))
                cantidad+=1
            resultado={'actualizadas':cantidad,'mensaje':f'{cantidad} solicitudes actualizadas. Los cambios quedaron registrados.'}
            offlinecloud.finalizar_operacion(q,operacion_id,resultado)
        c.commit()
        return resultado
    except Exception:
        c.rollback();raise
    finally:
        c.close()
