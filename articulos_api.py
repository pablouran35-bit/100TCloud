from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import productoscloud
from administracion_api import requiere_administracion


router = APIRouter(
    prefix="/administracion/articulos",
    tags=["Administración"]
)


class DatosArticulo(BaseModel):
    nombre: str
    unidad: str
    observaciones: str | None = None


class EstadoArticulo(BaseModel):
    activo: bool


@router.get("")
def listar_articulos(
    _administrador=Depends(requiere_administracion)
):
    articulos = productoscloud.obtener_productos(incluir_inactivos=True)

    return [
        {
            "id": articulo[0],
            "nombre": articulo[1],
            "unidad": articulo[2],
            "activo": articulo[3],
            "observaciones": articulo[4]
        }
        for articulo in articulos
    ]


@router.post("", status_code=201)
def crear_articulo(
    datos: DatosArticulo,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()
    unidad = datos.unidad.strip()
    observaciones = (
        datos.observaciones.strip()
        if datos.observaciones and datos.observaciones.strip()
        else None
    )

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del artículo no puede quedar vacío."
        )

    if not unidad:
        raise HTTPException(
            status_code=422,
            detail="La unidad no puede quedar vacía."
        )

    articulo_id = productoscloud.crear_producto(
        nombre,
        unidad,
        observaciones
    )

    return {
        "id": articulo_id,
        "mensaje": "Artículo creado correctamente."
    }


@router.put("/{articulo_id}")
def modificar_articulo(
    articulo_id: int,
    datos: DatosArticulo,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()
    unidad = datos.unidad.strip()
    observaciones = (
        datos.observaciones.strip()
        if datos.observaciones and datos.observaciones.strip()
        else None
    )

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del artículo no puede quedar vacío."
        )

    if not unidad:
        raise HTTPException(
            status_code=422,
            detail="La unidad no puede quedar vacía."
        )

    filas = productoscloud.actualizar_producto(
        articulo_id,
        nombre,
        unidad,
        observaciones
    )

    if filas == 0:
        raise HTTPException(
            status_code=404,
            detail="No se encontró ese artículo."
        )

    return {"mensaje": "Artículo modificado correctamente."}


@router.patch("/{articulo_id}/estado")
def cambiar_estado_articulo(
    articulo_id: int,
    datos: EstadoArticulo,
    _administrador=Depends(requiere_administracion)
):
    filas = productoscloud.cambiar_estado_producto(
        articulo_id,
        datos.activo
    )

    if filas == 0:
        raise HTTPException(
            status_code=404,
            detail="No se encontró ese artículo."
        )

    return {"mensaje": "Estado del artículo actualizado correctamente."}
