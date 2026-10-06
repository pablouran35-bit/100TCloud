from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from fastapi import Header
from pydantic import BaseModel, Field

from tareas_api import identidad_tareas
from planillas_api import _instante_operacion_offline
import comprascloud


router = APIRouter(prefix="/compras", tags=["Compras"])


class GestionSolicitud(BaseModel):
    estado: str
    proveedor_id: int | None = None
    observaciones: str | None = Field(
        default=None,
        max_length=4000
    )


class CambioEstadoSolicitud(BaseModel):
    estado: str = Field(
        min_length=1,
        max_length=100
    )
    estado_anterior: str = Field(
        min_length=1,
        max_length=100
    )


class GestionTarea(BaseModel):
    estado: str
    observaciones: str | None = Field(
        default=None,
        max_length=4000
    )


def limpiar_observaciones(valor):
    return valor.strip() if valor and valor.strip() else None


@router.get("/inicial")
def datos_iniciales(
    _identidad=Depends(identidad_tareas)
):
    return {
        "estados_solicitud":
            comprascloud.ESTADOS_SOLICITUD,

        "estados_tarea":
            comprascloud.ESTADOS_TAREA,

        "proveedores":
            comprascloud.obtener_proveedores_activos(),
    }


@router.get("/planillas")
def listar_planillas(
    _identidad=Depends(identidad_tareas)
):
    return comprascloud.listar_planillas_compra()


@router.get("/planillas/{planilla_id}")
def ver_planilla(
    planilla_id: int,
    _identidad=Depends(identidad_tareas)
):
    planilla = comprascloud.obtener_planilla_compra(
        planilla_id
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    return planilla


@router.put(
    "/planillas/{planilla_id}/solicitudes/{solicitud_id}"
)
def gestionar_solicitud(
    planilla_id: int,
    solicitud_id: int,
    datos: GestionSolicitud,
    identidad=Depends(identidad_tareas),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    """
    Gestión normal/online de una solicitud de compra.

    Este endpoint permite modificar:
    - estado
    - proveedor
    - observaciones

    NO es el endpoint utilizado para cambios de estado
    realizados offline.
    """

    estado = datos.estado.strip().upper()

    if estado not in comprascloud.ESTADOS_SOLICITUD:
        raise HTTPException(
            status_code=422,
            detail="Elegí un estado de compra válido."
        )

    try:
        actualizada = (
            comprascloud.actualizar_solicitud_compra(
                planilla_id,
                solicitud_id,
                estado,
                datos.proveedor_id,
                limpiar_observaciones(
                    datos.observaciones
                ),
                identidad["usuario_id"],
                str(operacion_id)
                if operacion_id
                else None,
                _instante_operacion_offline(
                    fecha_cambio
                ),
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    if not actualizada:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró esa solicitud "
                "en la planilla."
            )
        )

    return {
        "mensaje":
            "Solicitud actualizada y guardada "
            "en el historial."
    }


@router.patch(
    "/planillas/{planilla_id}/solicitudes/{solicitud_id}/estado"
)
def cambiar_estado_solicitud(
    planilla_id: int,
    solicitud_id: int,
    datos: CambioEstadoSolicitud,
    identidad=Depends(identidad_tareas),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    """
    Cambia SOLAMENTE el estado de una solicitud.

    Este endpoint es el utilizado por las operaciones
    que pueden haberse realizado mientras el dispositivo
    estaba sin conexión.

    El cliente debe enviar:

        estado
        estado_anterior

    Cloud compara estado_anterior con el estado real
    antes de aplicar el cambio.

    Si alguien modificó la solicitud mientras el dispositivo
    estaba offline, se devuelve HTTP 409 y NO se sobrescribe
    el estado actual de Cloud.
    """

    estado = datos.estado.strip().upper()
    estado_anterior = (
        datos.estado_anterior.strip().upper()
    )

    if estado not in comprascloud.ESTADOS_SOLICITUD:
        raise HTTPException(
            status_code=422,
            detail="Elegí un estado de compra válido."
        )

    if estado_anterior not in comprascloud.ESTADOS_SOLICITUD:
        raise HTTPException(
            status_code=422,
            detail=(
                "El estado anterior de la solicitud "
                "no es válido."
            )
        )

    try:
        actualizada = (
            comprascloud.actualizar_estado_solicitud_compra(
                planilla_id,
                solicitud_id,
                estado,
                estado_anterior,
                identidad["usuario_id"],
                str(operacion_id)
                if operacion_id
                else None,
                _instante_operacion_offline(
                    fecha_cambio
                ),
            )
        )

    except comprascloud.ConflictoSolicitudCompra as conflicto:
        raise HTTPException(
            status_code=409,
            detail={
                "tipo":
                    "CONFLICTO_SINCRONIZACION",

                "solicitud_id":
                    conflicto.solicitud_id,

                "estado_anterior":
                    conflicto.estado_anterior,

                "estado_cloud":
                    conflicto.estado_cloud,

                "mensaje": (
                    "La solicitud cambió en Cloud "
                    "mientras el dispositivo estaba "
                    "sin conexión."
                ),
            }
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    if not actualizada:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró esa solicitud "
                "en la planilla."
            )
        )

    return {
        "mensaje":
            "Estado de solicitud actualizado "
            "correctamente."
    }


@router.get("/tareas")
def listar_tareas(
    _identidad=Depends(identidad_tareas)
):
    return comprascloud.listar_tareas_compra()


@router.get("/tareas/{tarea_id}")
def ver_tarea(
    tarea_id: int,
    _identidad=Depends(identidad_tareas)
):
    tarea = comprascloud.obtener_tarea_compra(
        tarea_id
    )

    if tarea is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "La tarea ya no está pendiente "
                "o en proceso."
            )
        )

    return tarea


@router.put("/tareas/{tarea_id}")
def gestionar_tarea(
    tarea_id: int,
    datos: GestionTarea,
    identidad=Depends(identidad_tareas),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    estado = datos.estado.strip().upper()

    if estado not in comprascloud.ESTADOS_TAREA:
        raise HTTPException(
            status_code=422,
            detail="Elegí un estado de tarea válido."
        )

    actualizada = (
        comprascloud.actualizar_tarea_compra(
            tarea_id,
            estado,
            limpiar_observaciones(
                datos.observaciones
            ),
            identidad["usuario_id"],
            str(operacion_id)
            if operacion_id
            else None,
            _instante_operacion_offline(
                fecha_cambio
            ),
        )
    )

    if not actualizada:
        raise HTTPException(
            status_code=404,
            detail=(
                "La tarea ya no está pendiente "
                "o en proceso."
            )
        )

    return {
        "mensaje":
            "Tarea actualizada y guardada "
            "en el historial."
    }