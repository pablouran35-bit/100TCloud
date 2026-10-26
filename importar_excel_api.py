from fastapi import APIRouter,Depends,HTTPException,Request,Header,Query
from pydantic import BaseModel,Field,StrictBool,ValidationError
from uuid import UUID
from datetime import date
from starlette.concurrency import run_in_threadpool
from planillas_api import identidad_actual
from leer_excel_planilla import Libro,MAX_ARCHIVO
from importar_planilla_excel import Importador,preparar_filas,ConflictoImportacion
import conexion

router=APIRouter(prefix='/importar-excel',tags=['Importar planilla Excel'])
servicio=Importador(conexion.conectar)
def error(e):
    if isinstance(e,PermissionError):raise HTTPException(403,str(e))
    if isinstance(e,ConflictoImportacion):raise HTTPException(409,str(e))
    if isinstance(e,ValueError):raise HTTPException(422,str(e))
    raise HTTPException(500,'No se pudo completar la importación. Si estabas confirmando, reintentá el mismo guardado para comprobar si se completó.')
@router.get('/catalogos')
def catalogos(identidad=Depends(identidad_actual)):
    try:return servicio.catalogos(identidad['usuario_id'])
    except Exception as e:error(e)
@router.post('/leer')
async def leer(request:Request,hoja:str|None=None,encabezado:int|None=None,columnas:str|None=None,identidad=Depends(identidad_actual)):
    contenido=bytearray()
    async for parte in request.stream():
        if len(contenido)+len(parte)>MAX_ARCHIVO:raise HTTPException(413,'El archivo supera 8 MB.')
        contenido.extend(parte)
    def preparar():
        import json
        cats=servicio.catalogos(identidad['usuario_id'])
        mapa=json.loads(columnas) if columnas else None
        if mapa is not None and (not isinstance(mapa,dict) or set(mapa)-{'cantidad','descripcion','area','unidad','presentacion','observaciones'}):raise ValueError('Mapeo de columnas inválido.')
        libro=Libro(bytes(contenido))
        try:resultado=libro.leer(hoja,encabezado,mapa)
        finally:libro.zip.close()
        return {**preparar_filas(resultado,cats),'catalogos':cats}
    try:return await run_in_threadpool(preparar)
    except Exception as e:error(e)
class FilaImportada(BaseModel):
    fila_excel:int=Field(ge=1,le=10000)
    descripcion:str=Field(min_length=1,max_length=1000)
    cantidad:str|int|float
    unidad:str=Field(default='',max_length=80)
    area_id:int=Field(ge=0)
    producto_id:int|None=None
    crear_nuevo:StrictBool=False
    unidad_confirmada:StrictBool=False
    area_original:str=Field(default='',max_length=500)
    presentacion:str=Field(default='',max_length=1000)
    observaciones:str=Field(default='',max_length=1000)
class Importacion(BaseModel):
    obra_id:int=Field(gt=0)
    fecha_compra:date
    archivo:str=Field(max_length=200)
    hoja:str=Field(max_length=100)
    confirmar_nuevos:StrictBool=False
    filas:list[FilaImportada]=Field(min_length=1,max_length=1000)
@router.post('/confirmar')
async def confirmar(request:Request,operacion_id:UUID=Header(alias='Idempotency-Key'),identidad=Depends(identidad_actual)):
    contenido=bytearray()
    async for parte in request.stream():
        if len(contenido)+len(parte)>8*1024*1024:raise HTTPException(413,'La importación revisada supera 8 MB.')
        contenido.extend(parte)
    try:datos=Importacion.model_validate_json(bytes(contenido))
    except ValidationError:raise HTTPException(422,'Revisá las filas seleccionadas: faltan cantidades, artículos o áreas válidas.')
    try:return await run_in_threadpool(servicio.confirmar,identidad['usuario_id'],datos.obra_id,str(datos.fecha_compra),[f.model_dump() for f in datos.filas],datos.archivo,datos.hoja,operacion_id,datos.confirmar_nuevos)
    except Exception as e:error(e)
