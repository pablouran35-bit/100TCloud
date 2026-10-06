from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import proveedorescloud
from administracion_api import requiere_administracion


router = APIRouter(
    prefix="/administracion/proveedores",
    tags=["Administración"]
)


class DatosProveedor(BaseModel):
    nombre: str
    telefono: str | None = None
    email: str | None = None
    observaciones: str | None = None
    contacto: str | None = None
    whatsapp: str | None = None


class EstadoProveedor(BaseModel):
    activo: bool


def limpiar_opcional(valor):
    return valor.strip() if valor and valor.strip() else None


@router.get("")
def listar_proveedores(_administrador=Depends(requiere_administracion)):
    proveedores = proveedorescloud.obtener_proveedores(incluir_inactivos=True)
    return [
        {
            "id": fila[0],
            "nombre": fila[1],
            "telefono": fila[2],
            "email": fila[3],
            "observaciones": fila[4],
            "activo": fila[5],
            "contacto": fila[6],
            "whatsapp": fila[7],
        }
        for fila in proveedores
    ]


@router.post("", status_code=201)
def crear_proveedor(datos: DatosProveedor,
                    _administrador=Depends(requiere_administracion)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del proveedor no puede quedar vacío."
        )

    proveedor_id = proveedorescloud.crear_proveedor(
        nombre,
        limpiar_opcional(datos.telefono),
        limpiar_opcional(datos.email),
        limpiar_opcional(datos.observaciones),
        limpiar_opcional(datos.contacto),
        limpiar_opcional(datos.whatsapp),
    )
    return {"id": proveedor_id, "mensaje": "Proveedor creado correctamente."}


@router.put("/{proveedor_id}")
def modificar_proveedor(proveedor_id: int, datos: DatosProveedor,
                        _administrador=Depends(requiere_administracion)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre del proveedor no puede quedar vacío."
        )

    filas = proveedorescloud.actualizar_proveedor(
        proveedor_id,
        nombre,
        limpiar_opcional(datos.telefono),
        limpiar_opcional(datos.email),
        limpiar_opcional(datos.observaciones),
        limpiar_opcional(datos.contacto),
        limpiar_opcional(datos.whatsapp),
    )
    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró ese proveedor.")
    return {"mensaje": "Proveedor modificado correctamente."}


@router.patch("/{proveedor_id}/estado")
def cambiar_estado_proveedor(proveedor_id: int, datos: EstadoProveedor,
                             _administrador=Depends(requiere_administracion)):
    filas = proveedorescloud.cambiar_estado_proveedor(proveedor_id, datos.activo)
    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró ese proveedor.")
    return {"mensaje": "Estado del proveedor actualizado correctamente."}
