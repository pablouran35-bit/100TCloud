from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Query
from entregas_api import identidad_entregas
import conexion
from fotos_planillas import FotosPlanillas,MAX_ENTRADA

router=APIRouter(prefix='/entregas',tags=['Fotos de entrega'])
servicio=FotosPlanillas(conexion.conectar)

def traducir(error):
    if isinstance(error,PermissionError):raise HTTPException(403,str(error))
    if isinstance(error,FileNotFoundError):raise HTTPException(404,str(error))
    if isinstance(error,ValueError):raise HTTPException(422,str(error))
    raise HTTPException(500,'No se pudo acceder a las fotos. Si estabas subiendo una, reintentá para verificar si quedó guardada.')

@router.get('/{planilla_id}/fotos')
def listar(planilla_id:int,identidad=Depends(identidad_entregas)):
    try:return servicio.listar(planilla_id,identidad['usuario_id'])
    except Exception as e:traducir(e)

@router.put('/{planilla_id}/fotos/{foto_id}')
async def subir(planilla_id:int,foto_id:UUID,request:Request,identidad=Depends(identidad_entregas)):
    datos=bytearray()
    async for parte in request.stream():
        if len(datos)+len(parte)>MAX_ENTRADA:raise HTTPException(413,'La imagen supera 8 MB.')
        datos.extend(parte)
    # Pillow y la base no deben bloquear el bucle de eventos de FastAPI.
    from starlette.concurrency import run_in_threadpool
    try:return await run_in_threadpool(servicio.guardar,planilla_id,identidad['usuario_id'],str(foto_id),bytes(datos))
    except Exception as e:traducir(e)

@router.get('/{planilla_id}/fotos/{foto_id}')
def ver(planilla_id:int,foto_id:UUID,miniatura:bool=Query(False),identidad=Depends(identidad_entregas)):
    try:
        datos=servicio.leer(planilla_id,identidad['usuario_id'],str(foto_id),miniatura)
        return Response(datos,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    except Exception as e:traducir(e)
