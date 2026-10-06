from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import areascloud
from administracion_api import requiere_administracion


router = APIRouter(
    prefix="/administracion/areas",
    tags=["Administración"]
)


class DatosArea(BaseModel):
    nombre: str


class EstadoArea(BaseModel):
    activo: bool


@router.get("")
def listar_areas(
    _administrador=Depends(requiere_administracion)
):
    areas = areascloud.obtener_areas_administracion()

    return [
        {
            "id": area[0],
            "nombre": area[1],
            "activo": area[2]
        }
        for area in areas
    ]


@router.post("", status_code=201)
def crear_area(
    datos: DatosArea,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del área no puede quedar vacío."
        )

    area_id = areascloud.crear_area(nombre)

    return {
        "id": area_id,
        "mensaje": "Área creada correctamente."
    }


@router.put("/{area_id}")
def modificar_area(
    area_id: int,
    datos: DatosArea,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del área no puede quedar vacío."
        )

    filas = areascloud.actualizar_area(area_id, nombre)

    if filas == 0:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa área."
        )

    return {"mensaje": "Área modificada correctamente."}


@router.patch("/{area_id}/estado")
def cambiar_estado_area(
    area_id: int,
    datos: EstadoArea,
    _administrador=Depends(requiere_administracion)
):
    filas = areascloud.cambiar_estado_area(area_id, datos.activo)

    if filas == 0:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa área."
        )

    return {"mensaje": "Estado del área actualizado correctamente."}
