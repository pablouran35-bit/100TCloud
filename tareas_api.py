from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from planillas_api import identidad_actual, es_contratista, _instante_operacion_offline
import tareascloud


router = APIRouter(prefix="/tareas", tags=["Tareas"])
ZONA_ARGENTINA = timezone(timedelta(hours=-3))


def identidad_tareas(identidad=Depends(identidad_actual)):
    roles = set(identidad["roles"])
    if es_contratista(identidad) or not roles.intersection({"ADMINISTRADOR", "EMPLEADO"}):
        raise HTTPException(status_code=403, detail="Tareas está disponible para empleados y administradores.")
    return identidad


class DatosTareaNueva(BaseModel):
    descripcion: str = Field(min_length=1, max_length=2000)
    fecha_solicitud: date
    observaciones: str | None = Field(default=None, max_length=4000)


class DatosTareaActualizada(DatosTareaNueva):
    estado: str


def limpiar_descripcion(valor):
    valor = valor.strip()
    if not valor:
        raise HTTPException(status_code=422, detail="La descripción no puede quedar vacía.")
    return valor


def limpiar_observaciones(valor):
    return valor.strip() if valor and valor.strip() else None


@router.get("/inicial")
def datos_iniciales(_identidad=Depends(identidad_tareas)):
    return {"fecha_hoy": datetime.now(ZONA_ARGENTINA).date().isoformat()}


@router.get("")
def listar_tareas(_identidad=Depends(identidad_tareas)):
    return tareascloud.listar_tareas()


@router.get("/{tarea_id}")
def ver_tarea(tarea_id: int, _identidad=Depends(identidad_tareas)):
    tarea = tareascloud.obtener_tarea(tarea_id)
    if tarea is None:
        raise HTTPException(status_code=404, detail="No se encontró esa tarea.")
    return tarea


@router.post("", status_code=201)
def crear_tarea(datos: DatosTareaNueva,
                identidad=Depends(identidad_tareas),
                operacion_id: UUID | None = Header(default=None, alias="Idempotency-Key"),
                fecha_cambio: str | None = Header(default=None, alias="X-Offline-Created-At")):
    tarea_id = tareascloud.crear_tarea(
        limpiar_descripcion(datos.descripcion), identidad["persona_id"],
        datos.fecha_solicitud, limpiar_observaciones(datos.observaciones),
        identidad["usuario_id"],
        str(operacion_id) if operacion_id else None,
        _instante_operacion_offline(fecha_cambio),
    )
    return {"id": tarea_id, "mensaje": "Tarea creada correctamente."}


@router.put("/{tarea_id}")
def actualizar_tarea(tarea_id: int, datos: DatosTareaActualizada,
                     identidad=Depends(identidad_tareas),
                     operacion_id: UUID | None = Header(default=None, alias="Idempotency-Key"),
                     fecha_cambio: str | None = Header(default=None, alias="X-Offline-Created-At")):
    estado = datos.estado.strip().upper()
    if estado not in tareascloud.ESTADOS_TAREA:
        raise HTTPException(status_code=422, detail="Elegí un estado válido para la tarea.")
    actualizada = tareascloud.actualizar_tarea(
        tarea_id, limpiar_descripcion(datos.descripcion), datos.fecha_solicitud,
        estado, limpiar_observaciones(datos.observaciones), identidad["usuario_id"],
        str(operacion_id) if operacion_id else None,
        _instante_operacion_offline(fecha_cambio),
    )
    if not actualizada:
        raise HTTPException(status_code=404, detail="No se encontró esa tarea.")
    return {"mensaje": "Tarea actualizada correctamente."}
