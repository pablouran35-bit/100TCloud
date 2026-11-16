from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from tareas_api import identidad_tareas
import conexion,correccion_articulos
router=APIRouter(prefix='/corregir-articulos',tags=['Planillas'])
class CambioArticulo(BaseModel):
    producto_anterior:int=Field(gt=0)
    producto_nuevo:int=Field(gt=0)
@router.get('/{planilla_id}')
def cargar(planilla_id:int,identidad=Depends(identidad_tareas)):
    try:return correccion_articulos.cargar(conexion.conectar,planilla_id,identidad['usuario_id'])
    except PermissionError as e:raise HTTPException(403,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
@router.put('/{planilla_id}/{solicitud_id}')
def guardar(planilla_id:int,solicitud_id:int,datos:CambioArticulo,identidad=Depends(identidad_tareas)):
    try:
        correccion_articulos.guardar(conexion.conectar,planilla_id,solicitud_id,identidad['usuario_id'],datos.producto_anterior,datos.producto_nuevo)
        return {'mensaje':'Artículo corregido. Las observaciones y los movimientos se conservaron.'}
    except PermissionError as e:raise HTTPException(403,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
