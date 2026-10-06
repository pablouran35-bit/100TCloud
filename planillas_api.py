import os
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import planillascloud


load_dotenv()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

router = APIRouter(prefix="/planillas", tags=["Planillas"])
esquema_bearer = HTTPBearer(auto_error=False)
ZONA_ARGENTINA = timezone(timedelta(hours=-3))


def _instante_operacion_offline(valor):
    if not valor:
        return None

    try:
        instante = datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        )

        if instante.tzinfo is None:
            raise ValueError

    except (AttributeError, TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="La fecha del cambio sin conexión no es válida."
        )

    ahora = datetime.now(timezone.utc)
    instante_utc = instante.astimezone(timezone.utc)

    if (
        instante_utc > ahora + timedelta(minutes=5)
        or instante_utc < ahora - timedelta(days=30)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "El cambio sin conexión tiene más de 30 días "
                "o una fecha futura incorrecta."
            )
        )

    return instante_utc


def _fecha_operacion_offline(valor):
    instante = _instante_operacion_offline(valor)

    return (
        instante.astimezone(ZONA_ARGENTINA).date()
        if instante
        else None
    )


def identidad_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)
):
    if credenciales is None:
        raise HTTPException(
            status_code=401,
            detail="Necesitás iniciar sesión."
        )

    try:
        datos = jwt.decode(
            credenciales.credentials,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        usuario_id = int(datos["sub"])

    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="La sesión venció o no es válida."
        )

    identidad = planillascloud.obtener_identidad(usuario_id)

    if identidad is None or not identidad["activo"]:
        raise HTTPException(
            status_code=401,
            detail="La cuenta no está activa."
        )

    if not set(identidad["roles"]).intersection(
        {"ADMINISTRADOR", "EMPLEADO", "CONTRATISTA"}
    ):
        raise HTTPException(
            status_code=403,
            detail="No tenés permiso para usar Planillas."
        )

    identidad["usuario_id"] = usuario_id

    return identidad


def es_contratista(identidad):
    roles = identidad["roles"]

    return (
        "CONTRATISTA" in roles
        and "ADMINISTRADOR" not in roles
        and "EMPLEADO" not in roles
    )


def comprobar_obra(obra_id, identidad, contratista):
    obras = planillascloud.obtener_obras_disponibles(
        identidad["persona_id"],
        contratista
    )

    if not any(obra[0] == obra_id for obra in obras):
        raise HTTPException(
            status_code=403,
            detail="No tenés acceso a esa obra."
        )


class NuevaPlanilla(BaseModel):
    obra_id: int
    fecha_compra: date | None = None


class NuevaSolicitud(BaseModel):
    producto_id: int
    area_id: int
    cantidad: float = Field(gt=0)
    observaciones: str | None = None


class MotivoCancelacion(BaseModel):
    motivo: str = Field(min_length=3, max_length=1000)


class CambioEstadoSolicitud(BaseModel):
    estado: str = Field(min_length=1, max_length=100)
    estado_anterior: str = Field(min_length=1, max_length=100)


@router.get("/inicial")
def datos_iniciales(identidad=Depends(identidad_actual)):
    contratista = es_contratista(identidad)

    productos, areas = planillascloud.obtener_catalogos()

    fecha_objetivo = planillascloud.fecha_compra_objetivo(
        contratista
    )

    hoy = planillascloud.fecha_local()

    return {
        "obras": [
            {
                "id": obra[0],
                "nombre": obra[1]
            }
            for obra in planillascloud.obtener_obras_disponibles(
                identidad["persona_id"],
                contratista
            )
        ],
        "productos": [
            {
                "id": producto[0],
                "nombre": producto[1],
                "unidad": producto[2]
            }
            for producto in productos
        ],
        "areas": [
            {
                "id": area[0],
                "nombre": area[1]
            }
            for area in areas
        ],
        "fecha_compra_nueva": fecha_objetivo,
        "aviso_contratista": (
            contratista
            and hoy.weekday() in (0, 1)
        ),
    }


@router.get("")
def listar_planillas(identidad=Depends(identidad_actual)):
    contratista = es_contratista(identidad)

    return planillascloud.obtener_planillas_pendientes(
        identidad["persona_id"],
        contratista
    )


@router.post("", status_code=201)
def crear_planilla(
    datos: NuevaPlanilla,
    identidad=Depends(identidad_actual),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    contratista = es_contratista(identidad)

    comprobar_obra(
        datos.obra_id,
        identidad,
        contratista
    )

    fecha_creacion = _fecha_operacion_offline(
        fecha_cambio
    )

    fecha_objetivo = planillascloud.fecha_compra_objetivo(
        contratista,
        fecha_creacion
    )

    if datos.fecha_compra is not None:

        if (
            fecha_creacion is None
            or datos.fecha_compra != fecha_objetivo
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "La fecha de compra guardada no coincide "
                    "con la semana permitida para crear la planilla."
                )
            )

        fecha_compra = datos.fecha_compra

    else:
        fecha_compra = planillascloud.fecha_compra_objetivo(
            contratista
        )

    planilla_id, creada = planillascloud.crear_planilla(
        datos.obra_id,
        fecha_compra,
        identidad["usuario_id"],
        str(operacion_id) if operacion_id else None,
    )

    return {
        "id": planilla_id,
        "fecha_compra": fecha_compra,
        "creada": creada,
        "mensaje": (
            "Planilla creada correctamente."
            if creada
            else
            "Ya había una planilla para esa obra y fecha; "
            "la abrimos para agregar solicitudes."
        ),
    }


@router.get("/{planilla_id}")
def ver_planilla(
    planilla_id: int,
    identidad=Depends(identidad_actual)
):
    contratista = es_contratista(identidad)

    planilla = planillascloud.obtener_planilla(
        planilla_id,
        identidad["persona_id"],
        contratista
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    planilla["puede_modificar"] = (
        planillascloud.puede_modificar_fecha(
            planilla["fecha_compra"],
            contratista
        )
    )

    return planilla


@router.post("/{planilla_id}/solicitudes", status_code=201)
def agregar_solicitud(
    planilla_id: int,
    datos: NuevaSolicitud,
    identidad=Depends(identidad_actual),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    contratista = es_contratista(identidad)

    planilla = planillascloud.obtener_planilla(
        planilla_id,
        identidad["persona_id"],
        contratista
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    if not planillascloud.puede_modificar_fecha(
        planilla["fecha_compra"],
        contratista,
        _fecha_operacion_offline(fecha_cambio)
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo se pueden agregar solicitudes "
                "a una planilla de la semana actual."
            )
        )

    observaciones = (
        datos.observaciones.strip()
        if datos.observaciones
        and datos.observaciones.strip()
        else None
    )

    try:
        solicitud_id = planillascloud.agregar_solicitud(
            planilla_id,
            identidad["persona_id"],
            identidad["usuario_id"],
            datos.producto_id,
            datos.area_id,
            datos.cantidad,
            observaciones,
            str(operacion_id) if operacion_id else None,
            _instante_operacion_offline(fecha_cambio),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "id": solicitud_id,
        "mensaje": "Solicitud agregada a la planilla."
    }


@router.put("/{planilla_id}/solicitudes/{solicitud_id}")
def modificar_solicitud(
    planilla_id: int,
    solicitud_id: int,
    datos: NuevaSolicitud,
    identidad=Depends(identidad_actual),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    contratista = es_contratista(identidad)

    planilla = planillascloud.obtener_planilla(
        planilla_id,
        identidad["persona_id"],
        contratista
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    if not planillascloud.puede_modificar_fecha(
        planilla["fecha_compra"],
        contratista,
        _fecha_operacion_offline(fecha_cambio)
    ):
        raise HTTPException(
            status_code=403,
            detail="Esta planilla es solo para consulta."
        )

    observaciones = (
        datos.observaciones.strip()
        if datos.observaciones
        and datos.observaciones.strip()
        else None
    )

    try:
        planillascloud.actualizar_solicitud(
            planilla_id,
            solicitud_id,
            identidad["usuario_id"],
            datos.producto_id,
            datos.area_id,
            datos.cantidad,
            observaciones,
            str(operacion_id) if operacion_id else None,
            _instante_operacion_offline(fecha_cambio),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "mensaje": "Solicitud modificada correctamente."
    }


@router.patch("/{planilla_id}/solicitudes/{solicitud_id}/estado")
def cambiar_estado_solicitud(
    planilla_id: int,
    solicitud_id: int,
    datos: CambioEstadoSolicitud,
    identidad=Depends(identidad_actual),
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
    Cambia únicamente el estado de una solicitud.

    Este endpoint es el utilizado por las operaciones que pueden
    sincronizarse desde modo offline.

    estado_anterior es obligatorio para poder detectar si la solicitud
    cambió en Cloud mientras el dispositivo estaba desconectado.
    """

    contratista = es_contratista(identidad)

    planilla = planillascloud.obtener_planilla(
        planilla_id,
        identidad["persona_id"],
        contratista
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    instante_operacion = _instante_operacion_offline(
        fecha_cambio
    )

    if not planillascloud.puede_modificar_fecha(
        planilla["fecha_compra"],
        contratista,
        instante_operacion
    ):
        raise HTTPException(
            status_code=403,
            detail="Esta planilla es solo para consulta."
        )

    estado = datos.estado.strip().upper()
    estado_anterior = datos.estado_anterior.strip().upper()

    try:
        planillascloud.actualizar_estado_solicitud(
            planilla_id,
            solicitud_id,
            estado,
            estado_anterior,
            identidad["usuario_id"],
            str(operacion_id) if operacion_id else None,
            instante_operacion,
        )

    except planillascloud.ConflictoSolicitud as conflicto:
        raise HTTPException(
            status_code=409,
            detail={
                "tipo": "CONFLICTO_SINCRONIZACION",
                "solicitud_id": conflicto.solicitud_id,
                "estado_anterior": conflicto.estado_anterior,
                "estado_cloud": conflicto.estado_cloud,
                "mensaje": (
                    "La solicitud cambió en Cloud mientras "
                    "el dispositivo estaba sin conexión."
                ),
            }
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "mensaje": "Estado de solicitud actualizado correctamente."
    }


@router.patch("/{planilla_id}/solicitudes/{solicitud_id}/cancelar")
def cancelar_solicitud(
    planilla_id: int,
    solicitud_id: int,
    datos: MotivoCancelacion,
    identidad=Depends(identidad_actual),
    operacion_id: UUID | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    fecha_cambio: str | None = Header(
        default=None,
        alias="X-Offline-Created-At"
    )
):
    contratista = es_contratista(identidad)

    planilla = planillascloud.obtener_planilla(
        planilla_id,
        identidad["persona_id"],
        contratista
    )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró esa planilla."
        )

    if not planillascloud.puede_modificar_fecha(
        planilla["fecha_compra"],
        contratista,
        _fecha_operacion_offline(fecha_cambio)
    ):
        raise HTTPException(
            status_code=403,
            detail="Esta planilla es solo para consulta."
        )

    try:
        planillascloud.cancelar_solicitud(
            planilla_id,
            solicitud_id,
            identidad["usuario_id"],
            datos.motivo.strip(),
            str(operacion_id) if operacion_id else None,
            _instante_operacion_offline(fecha_cambio),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "mensaje": "Solicitud cancelada correctamente."
    }