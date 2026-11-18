from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import BaseModel,Field
from tareas_api import identidad_tareas
import conexion,compra_parcial
router=APIRouter(prefix='/compras-parciales',tags=['Compras'])
class CompraParcial(BaseModel):
    cantidad:Decimal=Field(gt=0)
    cantidad_anterior:Decimal=Field(gt=0)
    estado_anterior:str
    proveedor_id:int=Field(gt=0)
    estado_compra:str
@router.post('/{planilla_id}/{solicitud_id}')
def registrar(planilla_id:int,solicitud_id:int,datos:CompraParcial,identidad=Depends(identidad_tareas),operacion_id:UUID=Header(alias='Idempotency-Key')):
    try:return compra_parcial.guardar(conexion.conectar,planilla_id,solicitud_id,identidad['usuario_id'],datos.cantidad,datos.cantidad_anterior,datos.estado_anterior,datos.proveedor_id,datos.estado_compra,operacion_id)
    except PermissionError as e:raise HTTPException(403,str(e)) from e
    except ValueError as e:raise HTTPException(422,str(e)) from e
