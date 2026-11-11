from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Header
from pydantic import BaseModel, Field
from uuid import UUID

from planillas_api import identidad_actual, es_contratista
from planillas_api import _instante_operacion_offline
import entregascloud


router = APIRouter(prefix="/entregas", tags=["Entregas"])


def identidad_entregas(identidad=Depends(identidad_actual)):
    roles = set(identidad["roles"])
    if es_contratista(identidad) or not roles.intersection({"ADMINISTRADOR", "EMPLEADO"}):
        raise HTTPException(status_code=403, detail="Entregas está disponible para empleados y administradores.")
    return identidad


class SolicitudesEntrega(BaseModel):
    solicitud_ids: list[int] = Field(min_length=1)


class CantidadEntrega(BaseModel):
    solicitud_id: int = Field(gt=0)
    cantidad: Decimal = Field(gt=0)
    entregada_anterior: Decimal = Field(ge=0)


class EntregasConCantidad(BaseModel):
    entregas: list[CantidadEntrega] = Field(min_length=1)


@router.post("/{planilla_id}/movimientos")
def registrar_entregas_con_cantidad(planilla_id: int, datos: EntregasConCantidad,
                                   identidad=Depends(identidad_entregas),
                                   operacion_id: UUID = Header(alias="Idempotency-Key")):
    cantidades = {e.solicitud_id: (e.cantidad, e.entregada_anterior) for e in datos.entregas}
    if len(cantidades) != len(datos.entregas):
        raise HTTPException(422, "No repitas una solicitud en la entrega.")
    try:
        cantidad = entregascloud.registrar_entrega(
            planilla_id, cantidades, identidad["usuario_id"], str(operacion_id),
            cantidades=cantidades,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"mensaje": "Entrega registrada correctamente.", "cantidad": cantidad}


@router.get("")
def listar_planillas(_identidad=Depends(identidad_entregas)):
    return entregascloud.listar_planillas_disponibles()


@router.get("/{planilla_id}")
def obtener_planilla(planilla_id: int, _identidad=Depends(identidad_entregas)):
    planilla = entregascloud.obtener_planilla(planilla_id)
    if planilla is None:
        raise HTTPException(status_code=404, detail="No se encontró esa planilla.")
    return planilla


@router.patch("/{planilla_id}/solicitudes")
def registrar_entrega(planilla_id: int, datos: SolicitudesEntrega,
                      identidad=Depends(identidad_entregas),
                      operacion_id: UUID | None = Header(default=None, alias="Idempotency-Key"),
                      fecha_cambio: str | None = Header(default=None, alias="X-Offline-Created-At")):
    try:
        cantidad = entregascloud.registrar_entrega(
            planilla_id, datos.solicitud_ids, identidad["usuario_id"],
            str(operacion_id) if operacion_id else None,
            _instante_operacion_offline(fecha_cambio),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"mensaje": "Entrega registrada correctamente.", "cantidad": cantidad}
