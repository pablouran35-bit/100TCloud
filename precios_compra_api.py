from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from tareas_api import identidad_tareas
import conexion
import precios_compra

router = APIRouter(prefix='/compras/precios-reales', tags=['Compras'])

class PrecioReal(BaseModel):
    precio_unitario: str | None
    revision: int = Field(ge=0)

@router.get('/{solicitud_id}')
def obtener(solicitud_id: int, identidad=Depends(identidad_tareas)):
    try:
        return precios_compra.obtener(conexion.conectar, solicitud_id, identidad['usuario_id'])
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

@router.put('/{solicitud_id}')
def guardar(solicitud_id: int, datos: PrecioReal, identidad=Depends(identidad_tareas)):
    try:
        return precios_compra.guardar(conexion.conectar, solicitud_id, identidad['usuario_id'], datos.precio_unitario, datos.revision)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
