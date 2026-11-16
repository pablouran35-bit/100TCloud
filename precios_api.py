from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import conexion
import precios_referencia as precios
from administracion_api import requiere_administracion

router = APIRouter(prefix='/administracion/precios', tags=['Administración'],
                   dependencies=[Depends(requiere_administracion)])


class PrecioArticulo(BaseModel):
    precio_unitario: str | None


@router.get('')
def listar():
    return precios.listar_articulos(conexion.conectar)


@router.get('/filtros')
def filtros():
    return precios.opciones_filtros(conexion.conectar)


@router.get('/estimacion')
def estimacion(fecha: date | None = None, obra_id: int | None = None,
               planilla_id: int | None = None, solo_aprobadas: bool = False):
    return precios.estimar(conexion.conectar, fecha, obra_id, planilla_id, solo_aprobadas)


@router.patch('/{producto_id}')
def guardar(producto_id: int, datos: PrecioArticulo):
    try:
        precio = precios.guardar_precio(conexion.conectar, producto_id, datos.precio_unitario)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'precio_unitario': precio, 'mensaje': 'Precio de referencia guardado.'}
