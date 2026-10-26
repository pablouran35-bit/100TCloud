"""Recorrido personal diario de proveedores, compartido entre Cloud y escritorio."""
from datetime import date
from hashlib import sha256
from uuid import UUID
import json
from psycopg2.extras import Json

class ConflictoRecorrido(ValueError):pass

class Recorridos:
    def __init__(self,conectar,escritorio=False):self.conectar=conectar;self.escritorio=escritorio
    def ejecutar(self,q,sql,args=()):q.execute(sql.replace('%s','?') if self.escritorio else sql,args)
    def autorizar(self,q,uid):
        self.ejecutar(q,"""SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id
          WHERE u.id=%s AND p.activo=TRUE AND EXISTS(SELECT 1 FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id
          WHERE ur.usuario_id=u.id AND UPPER(TRIM(r.nombre)) IN ('ADMINISTRADOR','EMPLEADO'))""",(uid,))
        if not q.fetchone():raise PermissionError('El recorrido está disponible para empleados y administradores activos.')
    def obtener(self,dia,uid):
        dia=date.fromisoformat(str(dia));c=self.conectar()
        try:
            q=c.cursor();self.autorizar(q,uid)
            self.ejecutar(q,'SELECT revision,paradas FROM recorridos_proveedores WHERE usuario_id=%s AND fecha=%s',(uid,dia))
            fila=q.fetchone()
            self.ejecutar(q,'SELECT id,nombre FROM proveedores WHERE activo=TRUE ORDER BY nombre,id')
            proveedores=[{'id':f[0],'nombre':f[1]} for f in q.fetchall()]
            return {'fecha':dia.isoformat(),'revision':fila[0] if fila else 0,'paradas':fila[1] if fila else [],'proveedores':proveedores}
        finally:c.close()
    def guardar(self,dia,uid,revision,paradas,operacion_id):
        dia=date.fromisoformat(str(dia));operacion_id=str(UUID(str(operacion_id)))
        if not isinstance(revision,int) or revision<0 or not isinstance(paradas,list) or len(paradas)>300:raise ValueError('Recorrido inválido.')
        ids=[p['proveedor_id'] for p in paradas]
        if any(type(i) is not int or i<=0 for i in ids) or len(ids)!=len(set(ids)):raise ValueError('No repitas proveedores en el recorrido.')
        if any(type(p.get('visitado')) is not bool for p in paradas):raise ValueError('Indicá si cada parada ya fue visitada.')
        recurso='recorrido:'+sha256(json.dumps([dia.isoformat(),revision,paradas],sort_keys=True).encode()).hexdigest()
        c=self.conectar()
        try:
            q=c.cursor();self.autorizar(q,uid)
            self.ejecutar(q,'''INSERT INTO operaciones_offline(operacion_id,usuario_id,recurso,resultado)
              VALUES(%s,%s,%s,NULL) ON CONFLICT(operacion_id) DO NOTHING RETURNING operacion_id''',(operacion_id,uid,recurso))
            if q.fetchone() is None:
                self.ejecutar(q,'SELECT usuario_id,recurso,resultado FROM operaciones_offline WHERE operacion_id=%s',(operacion_id,))
                anterior=q.fetchone()
                if not anterior or anterior[0]!=uid or anterior[1]!=recurso:raise ValueError('La clave del cambio ya pertenece a otra operación.')
                if anterior[2] is None:raise ValueError('El cambio anterior todavía no terminó. Reintentá.')
                c.commit();return anterior[2]
            self.ejecutar(q,'''INSERT INTO recorridos_proveedores(usuario_id,fecha,revision,paradas)
              VALUES(%s,%s,0,'[]') ON CONFLICT(usuario_id,fecha) DO NOTHING''',(uid,dia))
            self.ejecutar(q,'SELECT revision,paradas FROM recorridos_proveedores WHERE usuario_id=%s AND fecha=%s FOR UPDATE',(uid,dia))
            actual,previas=q.fetchone()
            if actual!=revision:raise ConflictoRecorrido('Este recorrido cambió en otro dispositivo. No se sobrescribió. Actualizá antes de continuar.')
            self.ejecutar(q,'SELECT id,nombre,activo FROM proveedores')
            proveedores={f[0]:(f[1],f[2]) for f in q.fetchall()};anteriores={p['proveedor_id'] for p in previas}
            nuevas=[]
            for p in paradas:
                proveedor=proveedores.get(p['proveedor_id'])
                if proveedor is None or (not proveedor[1] and p['proveedor_id'] not in anteriores):raise ValueError('Uno de los proveedores ya no está activo. Actualizá la lista.')
                nuevas.append({'proveedor_id':p['proveedor_id'],'nombre':proveedor[0],'visitado':p['visitado']})
            resultado={'fecha':dia.isoformat(),'revision':actual+1,'paradas':nuevas,'mensaje':'Recorrido guardado.'}
            self.ejecutar(q,'''UPDATE recorridos_proveedores SET revision=%s,paradas=%s,actualizado_en=CURRENT_TIMESTAMP
              WHERE usuario_id=%s AND fecha=%s''',(actual+1,Json(nuevas),uid,dia))
            self.ejecutar(q,'UPDATE operaciones_offline SET resultado=%s WHERE operacion_id=%s',(Json(resultado),operacion_id))
            c.commit();return resultado
        except Exception:c.rollback();raise
        finally:c.close()
