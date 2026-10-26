from datetime import date
from uuid import UUID
from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import BaseModel,Field,StrictBool
from entregas_api import identidad_entregas
from recorrido_proveedores import Recorridos,ConflictoRecorrido
import conexion

router=APIRouter(prefix='/recorridos',tags=['Recorrido de proveedores'])
servicio=Recorridos(conexion.conectar)
class Parada(BaseModel):
    proveedor_id:int=Field(gt=0)
    visitado:StrictBool=False
class Cambio(BaseModel):
    revision:int=Field(ge=0)
    paradas:list[Parada]=Field(max_length=300)
def error(e):
    if isinstance(e,PermissionError):raise HTTPException(403,str(e))
    if isinstance(e,ConflictoRecorrido):raise HTTPException(409,str(e))
    if isinstance(e,ValueError):raise HTTPException(422,str(e))
    raise HTTPException(500,'No se pudo guardar o consultar el recorrido. Reintentá para verificar su estado.')
@router.get('/{fecha}')
def obtener(fecha:date,identidad=Depends(identidad_entregas)):
    try:return servicio.obtener(fecha,identidad['usuario_id'])
    except Exception as e:error(e)
@router.put('/{fecha}')
def guardar(fecha:date,datos:Cambio,operacion_id:UUID=Header(alias='Idempotency-Key'),identidad=Depends(identidad_entregas)):
    try:return servicio.guardar(fecha,identidad['usuario_id'],datos.revision,[p.model_dump() for p in datos.paradas],operacion_id)
    except Exception as e:error(e)
