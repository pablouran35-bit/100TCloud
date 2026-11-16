"""Corrección acotada de artículos por personal de compras."""
import precios_compra

def cargar(conectar,planilla_id,usuario_id):
    db=conectar()
    try:
        with db.cursor() as q:
            q.execute('''SELECT s.id FROM solicitudes s JOIN planilla_solicitudes ps ON ps.solicitud_id=s.id
                         WHERE ps.planilla_id=%s ORDER BY s.id LIMIT 1''',(planilla_id,))
            primera=q.fetchone()
            if primera is None:raise ValueError('No se encontró la planilla o no tiene solicitudes.')
            precios_compra._solicitud(q,primera[0],usuario_id)
            q.execute('''SELECT s.id,s.producto_id,p.nombre,p.unidad,s.cantidad,s.observaciones,s.estado
                FROM solicitudes s JOIN planilla_solicitudes ps ON ps.solicitud_id=s.id
                JOIN productos p ON p.id=s.producto_id WHERE ps.planilla_id=%s ORDER BY s.id''',(planilla_id,))
            solicitudes=[dict(zip(('id','producto_id','articulo','unidad','cantidad','observaciones','estado'),fila)) for fila in q.fetchall()]
            q.execute('SELECT id,nombre,unidad FROM productos WHERE activo=TRUE ORDER BY nombre,id')
            productos=[dict(zip(('id','nombre','unidad'),fila)) for fila in q.fetchall()]
            return dict(solicitudes=solicitudes,productos=productos)
    finally:db.close()

def guardar(conectar,planilla_id,solicitud_id,usuario_id,producto_anterior,producto_nuevo):
    db=conectar()
    try:
        with db,db.cursor() as q:
            precios_compra._solicitud(q,solicitud_id,usuario_id,True)
            q.execute('''SELECT s.producto_id FROM solicitudes s JOIN planilla_solicitudes ps ON ps.solicitud_id=s.id
                         WHERE ps.planilla_id=%s AND s.id=%s''',(planilla_id,solicitud_id))
            fila=q.fetchone()
            if not fila:raise ValueError('La solicitud no pertenece a la planilla.')
            if fila[0]!=producto_anterior:raise ValueError('Otra persona cambió el artículo. Volvé a abrir la planilla.')
            q.execute('SELECT id FROM productos WHERE id=%s AND activo=TRUE',(producto_nuevo,))
            if not q.fetchone():raise ValueError('Elegí un artículo activo del catálogo.')
            if producto_anterior==producto_nuevo:return
            q.execute('UPDATE solicitudes SET producto_id=%s WHERE id=%s',(producto_nuevo,solicitud_id))
            q.execute('''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                SELECT id,estado,CURRENT_TIMESTAMP,%s,%s FROM solicitudes WHERE id=%s''',
                ('Corrección de artículo en planilla '+str(planilla_id)+': '+str(producto_anterior)+' → '+str(producto_nuevo),usuario_id,solicitud_id))
    finally:db.close()
