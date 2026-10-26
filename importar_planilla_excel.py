"""Vista previa y confirmación atómica de una planilla nueva desde Excel."""
from datetime import datetime,timedelta,timezone,date
from uuid import UUID
from hashlib import sha256
from psycopg2.extras import Json
from decimal import Decimal
import json,re
from leer_excel_planilla import normalizar,unidad_clave,cantidad

class ConflictoImportacion(ValueError):pass
def fecha_objetivo(roles,hoy=None):
    hoy=hoy or datetime.now(timezone(timedelta(hours=-3))).date()
    contratista='CONTRATISTA' in roles and not set(roles).intersection({'ADMINISTRADOR','EMPLEADO'})
    salto=(8 if hoy.weekday()==0 else 7) if contratista and hoy.weekday()<=1 else (1-hoy.weekday())%7
    return hoy+timedelta(days=salto)

def preparar_filas(preview,catalogos):
    productos={};areas_por_nombre={normalizar(a['nombre']):a['id'] for a in catalogos['areas']};areas_por_id={a['id'] for a in catalogos['areas']}
    for p in catalogos['productos']:productos.setdefault(normalizar(p['nombre']),[]).append(p)
    for fila in preview['filas']:
        coincidencias=productos.get(normalizar(fila['descripcion']),[])
        misma_unidad=[p for p in coincidencias if unidad_clave(p['unidad'])==unidad_clave(fila['unidad'])]
        candidato=misma_unidad[0] if len(misma_unidad)==1 else (coincidencias[0] if len(coincidencias)==1 else None)
        fila['producto_id']=candidato['id'] if candidato else None
        fila['crear_nuevo']=candidato is None and catalogos['puede_crear_articulos']
        fila['unidad_confirmada']=False
        raw=fila['area_original'];codigo=int(raw) if re.fullmatch(r'\d+',raw.strip()) else None
        fila['area_id']=areas_por_nombre.get(normalizar(raw))
        if fila['area_id'] is None and codigo in areas_por_id:fila['area_id']=codigo
        if fila['area_id'] is None:fila['problemas'].append('Elegí un área: el dato del Excel no corresponde a una única área del sistema.')
        if not candidato and not fila['crear_nuevo']:fila['problemas'].append('Elegí un artículo existente del catálogo.')
    return preview

class Importador:
    def __init__(self,conectar,escritorio=False):self.conectar=conectar;self.escritorio=escritorio
    def ejecutar(self,q,sql,args=()):q.execute(sql.replace('%s','?') if self.escritorio else sql,args)
    def identidad(self,q,uid):
        self.ejecutar(q,'SELECT p.id,p.activo FROM usuarios u JOIN personas p ON p.id=u.persona_id WHERE u.id=%s',(uid,))
        p=q.fetchone()
        if not p or not p[1]:raise PermissionError('Necesitás una cuenta activa para importar.')
        self.ejecutar(q,'SELECT UPPER(TRIM(r.nombre)) FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=%s',(uid,))
        roles=[f[0] for f in q.fetchall()]
        if not set(roles).intersection({'ADMINISTRADOR','EMPLEADO','CONTRATISTA'}):raise PermissionError('No tenés permiso para cargar planillas.')
        return p[0],roles
    def catalogos(self,uid):
        c=self.conectar()
        try:
            q=c.cursor();persona,roles=self.identidad(q,uid);staff=bool(set(roles).intersection({'ADMINISTRADOR','EMPLEADO'}))
            if staff:self.ejecutar(q,'SELECT id,nombre FROM obras WHERE activo=TRUE ORDER BY nombre,id')
            else:self.ejecutar(q,'SELECT o.id,o.nombre FROM obras o JOIN persona_obra po ON po.obra_id=o.id WHERE po.persona_id=%s AND o.activo=TRUE ORDER BY o.nombre,o.id',(persona,))
            obras=[{'id':f[0],'nombre':f[1]} for f in q.fetchall()]
            self.ejecutar(q,'SELECT id,nombre,unidad FROM productos WHERE activo=TRUE ORDER BY nombre,id')
            productos=[{'id':f[0],'nombre':f[1],'unidad':f[2] or ''} for f in q.fetchall()]
            self.ejecutar(q,'SELECT id,nombre FROM areas WHERE activo=TRUE ORDER BY id')
            areas=[{'id':f[0],'nombre':f[1]} for f in q.fetchall()]
            return {'obras':obras,'productos':productos,'areas':areas,'puede_crear_articulos':staff,'fecha_compra':str(fecha_objetivo(roles))}
        finally:c.close()
    def confirmar(self,uid,obra_id,fecha_compra,filas,archivo,hoja,operacion_id,confirmar_nuevos=False):
        operacion_id=str(UUID(str(operacion_id)))
        if type(obra_id) is not int or obra_id<=0:raise ValueError('Elegí la obra de la nueva planilla.')
        if not isinstance(filas,list) or not 1<=len(filas)<=1000:raise ValueError('Seleccioná entre 1 y 1.000 solicitudes para importar.')
        archivo=str(archivo).replace('\\','/').split('/')[-1][:180];hoja=str(hoja)[:100]
        recurso='importar-excel:'+sha256(json.dumps([obra_id,str(fecha_compra),filas,archivo,hoja,confirmar_nuevos],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        c=self.conectar()
        try:
            q=c.cursor();persona,roles=self.identidad(q,uid);staff=bool(set(roles).intersection({'ADMINISTRADOR','EMPLEADO'}))
            self.ejecutar(q,'''INSERT INTO operaciones_offline(operacion_id,usuario_id,recurso,resultado)
              VALUES(%s,%s,%s,NULL) ON CONFLICT(operacion_id) DO NOTHING RETURNING operacion_id''',(operacion_id,uid,recurso))
            if q.fetchone() is None:
                self.ejecutar(q,'SELECT usuario_id,recurso,resultado FROM operaciones_offline WHERE operacion_id=%s',(operacion_id,))
                previa=q.fetchone()
                if not previa or previa[0]!=uid or previa[1]!=recurso:raise ValueError('La clave del guardado pertenece a otra importación.')
                if previa[2] is None:raise ValueError('El guardado anterior todavía no terminó. Reintentá.')
                c.commit();return previa[2]
            fecha=fecha_objetivo(roles)
            if str(fecha_compra)!=str(fecha):raise ConflictoImportacion('Cambió la fecha de salida desde la revisión. Volvé a cargar la vista previa antes de confirmar.')
            if staff:self.ejecutar(q,'SELECT id FROM obras WHERE id=%s AND activo=TRUE FOR SHARE',(obra_id,))
            else:self.ejecutar(q,'SELECT o.id FROM obras o JOIN persona_obra po ON po.obra_id=o.id WHERE o.id=%s AND o.activo=TRUE AND po.persona_id=%s FOR SHARE OF o',(obra_id,persona))
            if not q.fetchone():raise PermissionError('La obra no está activa o no está asignada a tu usuario.')
            # Serializar las altas de artículos de importaciones simultáneas.
            self.ejecutar(q,'SELECT pg_advisory_xact_lock(%s)',(100714036,))
            self.ejecutar(q,'SELECT id,nombre,unidad FROM productos WHERE activo=TRUE ORDER BY id')
            productos={f[0]:{'id':f[0],'nombre':f[1],'unidad':f[2] or ''} for f in q.fetchall()}
            self.ejecutar(q,'SELECT id FROM areas WHERE activo=TRUE');areas={f[0] for f in q.fetchall()}
            validadas=[];nuevos=0
            for numero,f in enumerate(filas,1):
                prefijo=f'Fila {f.get("fila_excel",numero)}: '
                desc=str(f.get('descripcion') or '').strip();unidad=str(f.get('unidad') or '').strip()
                if not desc or len(desc)>1000:raise ValueError(prefijo+'completá una descripción de hasta 1.000 caracteres.')
                try:qty=cantidad(f.get('cantidad'))
                except ValueError as e:raise ValueError(prefijo+str(e)) from None
                area=f.get('area_id')
                if type(area) is not int or area not in areas:raise ValueError(prefijo+'elegí un área activa del sistema.')
                if f.get('crear_nuevo'):
                    if not staff:raise PermissionError('Solo empleados y administradores pueden crear artículos durante la importación.')
                    if not confirmar_nuevos:raise ValueError('Confirmá la creación de los artículos nuevos de la vista previa.')
                    if not unidad or len(unidad)>80:raise ValueError(prefijo+'indicá la unidad del artículo nuevo.')
                    candidatos=[p for p in productos.values() if normalizar(p['nombre'])==normalizar(desc) and unidad_clave(p['unidad'])==unidad_clave(unidad)]
                    if len(candidatos)>1:raise ConflictoImportacion(prefijo+'hay varios artículos iguales. Elegí uno del catálogo.')
                    if candidatos:producto=candidatos[0]
                    else:
                        self.ejecutar(q,'INSERT INTO productos(nombre,unidad,observaciones) VALUES(%s,%s,%s) RETURNING id',(desc,unidad,'Alta desde importación Excel revisada.'))
                        pid=q.fetchone()[0];producto={'id':pid,'nombre':desc,'unidad':unidad};productos[pid]=producto;nuevos+=1
                else:
                    producto=productos.get(f.get('producto_id'))
                    if producto is None:raise ValueError(prefijo+'elegí un artículo activo o marcá Crear artículo nuevo.')
                    if unidad and unidad_clave(unidad)!=unidad_clave(producto['unidad']) and not f.get('unidad_confirmada'):
                        raise ValueError(prefijo+f'la unidad del Excel ({unidad}) difiere de la del artículo ({producto["unidad"]}). Revisá la cantidad y confirmá la unidad.')
                obs=str(f.get('observaciones') or '').strip();pres=str(f.get('presentacion') or '').strip();original=str(f.get('area_original') or '')
                if len(obs)>1000 or len(pres)>1000:raise ValueError(prefijo+'las observaciones o presentación superan 1.000 caracteres.')
                nota=f'Excel: {archivo} · {hoja} · fila {f.get("fila_excel",numero)}. Descripción: {desc}. Unidad Excel: {unidad}.'
                if original:nota+=' Área Excel: '+original+'.'
                if pres:nota+=' Presentación: '+pres+'.'
                if obs:nota+=' '+obs
                if len(nota)>4000:raise ValueError(prefijo+'los detalles son demasiado largos.')
                validadas.append((producto['id'],area,qty,nota))
            admin='ADMINISTRADOR' in roles
            self.ejecutar(q,'''INSERT INTO planillas(obra_id,fecha_compra,estado,observaciones,estado_aprobacion,aprobada_por,fecha_aprobacion)
              VALUES(%s,%s,'ABIERTA',%s,%s,%s,CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END) RETURNING id''',
              (obra_id,fecha,f'Importación Excel revisada: {archivo} · {hoja}', 'APROBADA' if admin else 'PENDIENTE',uid if admin else None,admin))
            pid=q.fetchone()[0]
            for producto,area,qty,nota in validadas:
                self.ejecutar(q,'''INSERT INTO solicitudes(persona_id,obra_id,producto_id,cantidad,observaciones,estado,area_id)
                  VALUES(%s,%s,%s,%s,%s,'PENDIENTE DE COMPRA',%s) RETURNING id''',(persona,obra_id,producto,qty,nota,area))
                sid=q.fetchone()[0]
                self.ejecutar(q,'INSERT INTO planilla_solicitudes(planilla_id,solicitud_id) VALUES(%s,%s)',(pid,sid))
                self.ejecutar(q,'''INSERT INTO historial_solicitudes(solicitud_id,estado,fecha_hora,observaciones,usuario_id)
                  VALUES(%s,'PENDIENTE DE COMPRA',CURRENT_TIMESTAMP,'Solicitud importada desde Excel y revisada por el usuario',%s)''',(sid,uid))
            resultado={'id':pid,'fecha_compra':str(fecha),'solicitudes':len(validadas),'articulos_creados':nuevos,'mensaje':f'Planilla {pid} creada con {len(validadas)} solicitudes importadas.'}
            self.ejecutar(q,'UPDATE operaciones_offline SET resultado=%s WHERE operacion_id=%s',(Json(resultado),operacion_id))
            c.commit();return resultado
        except Exception:c.rollback();raise
        finally:c.close()
