"""Fotos de entrega compartidas entre Cloud y escritorio, asociadas a la planilla."""
from io import BytesIO
from uuid import UUID
from hashlib import sha256
from PIL import Image, ImageOps, UnidentifiedImageError
import warnings

MAX_ENTRADA=8*1024*1024
MAX_FOTO=450*1024
Image.MAX_IMAGE_PIXELS=36_000_000

def comprimir(datos):
    if not datos or len(datos)>MAX_ENTRADA:raise ValueError('La imagen supera 8 MB. Elegí una imagen más pequeña.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(datos)) as im:
                if im.format not in ('JPEG','PNG','WEBP','HEIF','HEIC'):raise ValueError('Usá una foto JPG, PNG o WebP.')
                im=ImageOps.exif_transpose(im)
                im.thumbnail((1280,1280),Image.Resampling.LANCZOS)
                if im.mode in ('RGBA','LA') or 'transparency' in im.info:
                    rgba=im.convert('RGBA');fondo=Image.new('RGBA',rgba.size,'white');fondo.alpha_composite(rgba);im=fondo.convert('RGB')
                else:im=im.convert('RGB')
                # No conservar EXIF, GPS ni metadatos del archivo original.
                for calidad in (78,68,58,48):
                    salida=BytesIO();im.save(salida,'JPEG',quality=calidad,optimize=True)
                    foto=salida.getvalue()
                    if len(foto)<=MAX_FOTO:break
                if len(foto)>MAX_FOTO:raise ValueError('No se pudo reducir esta imagen. Elegí otra foto.')
                ancho,alto=im.size
                im.thumbnail((320,320),Image.Resampling.LANCZOS)
                mini=BytesIO();im.save(mini,'JPEG',quality=65,optimize=True)
                return foto,mini.getvalue(),ancho,alto
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('No se pudo leer la imagen. Usá JPG, PNG o WebP.') from None

class FotosPlanillas:
    def __init__(self,conectar,escritorio=False):self.conectar=conectar;self.escritorio=escritorio
    def ejecutar(self,q,sql,args=()):q.execute(sql.replace('%s','?') if self.escritorio else sql,args)
    def autorizar(self,q,usuario_id):
        self.ejecutar(q,"""SELECT COALESCE(NULLIF(TRIM(COALESCE(p.nombre,'') || ' ' || COALESCE(p.apellido,'')),''),u.usuario)
            FROM usuarios u JOIN personas p ON p.id=u.persona_id
            WHERE u.id=%s AND p.activo=TRUE AND EXISTS
            (SELECT 1 FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id
            AND UPPER(TRIM(r.nombre)) IN ('ADMINISTRADOR','EMPLEADO'))""",(usuario_id,))
        fila=q.fetchone()
        if not fila:raise PermissionError('Solo empleados y administradores activos pueden acceder a las fotos de entrega.')
        return fila[0]
    def planilla(self,q,pid):
        self.ejecutar(q,'SELECT id FROM planillas WHERE id=%s',(pid,))
        if not q.fetchone():raise ValueError('La planilla no existe.')
    def listar(self,pid,uid):
        c=self.conectar()
        try:
            q=c.cursor();self.autorizar(q,uid);self.planilla(q,pid)
            self.ejecutar(q,'''SELECT id,creada_en,usuario_nombre,ancho,alto,octet_length(imagen)
                FROM fotos_entrega_planillas WHERE planilla_id=%s ORDER BY creada_en,id''',(pid,))
            return [dict(id=str(f[0]),creada_en=str(f[1]),usuario=f[2],ancho=f[3],alto=f[4],bytes=f[5]) for f in q.fetchall()]
        finally:c.close()
    def guardar(self,pid,uid,foto_id,datos):
        foto_id=str(UUID(str(foto_id)))
        foto,mini,ancho,alto=comprimir(datos)
        huella=sha256(datos).hexdigest()
        c=self.conectar()
        try:
            q=c.cursor();nombre=self.autorizar(q,uid);self.planilla(q,pid)
            self.ejecutar(q,'''INSERT INTO fotos_entrega_planillas
                (id,planilla_id,usuario_id,usuario_nombre,imagen,miniatura,ancho,alto,huella)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',
                (foto_id,pid,uid,nombre,foto,mini,ancho,alto,huella))
            self.ejecutar(q,'SELECT planilla_id,usuario_id,huella FROM fotos_entrega_planillas WHERE id=%s',(foto_id,))
            actual=q.fetchone()
            if actual is None or (int(actual[0]),actual[1],actual[2])!=(int(pid),uid,huella):
                raise ValueError('Ese identificador pertenece a otra foto. Volvé a seleccionar el archivo.')
            c.commit();return {'id':foto_id,'bytes':len(foto),'ancho':ancho,'alto':alto}
        except Exception:c.rollback();raise
        finally:c.close()
    def leer(self,pid,uid,foto_id,miniatura=False):
        foto_id=str(UUID(str(foto_id)));c=self.conectar()
        try:
            q=c.cursor();self.autorizar(q,uid)
            campo='miniatura' if miniatura else 'imagen'
            self.ejecutar(q,'SELECT '+campo+' FROM fotos_entrega_planillas WHERE id=%s AND planilla_id=%s',(foto_id,pid))
            fila=q.fetchone()
            if not fila:raise FileNotFoundError('No se encontró esa foto en esta planilla.')
            return bytes(fila[0])
        finally:c.close()

    def entregadas_dia(self,dia,uid):
        from datetime import date
        dia=date.fromisoformat(str(dia))
        c=self.conectar()
        try:
            q=c.cursor();self.autorizar(q,uid)
            self.ejecutar(q,"""SELECT p.id,o.nombre FROM planillas p JOIN obras o ON o.id=p.obra_id
                WHERE EXISTS (SELECT 1 FROM planilla_solicitudes ps
                JOIN historial_solicitudes h ON h.solicitud_id=ps.solicitud_id
                WHERE ps.planilla_id=p.id AND UPPER(TRIM(h.estado))='ENTREGADO'
                AND (h.fecha_hora AT TIME ZONE 'America/Argentina/Buenos_Aires')::date=%s)
                ORDER BY p.id DESC""",(dia,))
            return [dict(id=f[0],obra=f[1]) for f in q.fetchall()]
        finally:c.close()
