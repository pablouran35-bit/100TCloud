
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


# ============================================================
# FECHAS Y OPERACIONES SIN CONEXIÓN
# ============================================================

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


# ============================================================
# IDENTIDAD Y PERMISOS
# ============================================================

def identidad_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(
        esquema_bearer
    )
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

    except jwt.ExpiredSignatureError:
        print("ERROR JWT: el token está vencido.")
        raise HTTPException(
            status_code=401,
            detail="El token está vencido."
        )

    except jwt.InvalidSignatureError:
        print("ERROR JWT: la firma del token no coincide.")
        raise HTTPException(
            status_code=401,
            detail="La firma de la sesión no es válida."
        )

    except jwt.InvalidTokenError as error:
        print(f"ERROR JWT: {type(error).__name__}")
        raise HTTPException(
            status_code=401,
            detail="El token no es válido."
        )

    except (KeyError, TypeError, ValueError) as error:
        print(f"ERROR DATOS JWT: {type(error).__name__}")
        raise HTTPException(
            status_code=401,
            detail="Los datos de la sesión no son válidos."
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


def exigir_administrador(identidad):
    """
    La aprobación se autoriza en el servidor, no solamente
    ocultando botones en la pantalla del teléfono.
    """
    if "ADMINISTRADOR" not in identidad["roles"]:
        raise HTTPException(
            status_code=403,
            detail="Solo un administrador puede aprobar planillas."
        )


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


# ============================================================
# MODELOS DE DATOS
# ============================================================

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


class ResolverAprobacion(BaseModel):
    solicitudes_ids: list[int] = Field(min_length=1)
    decision: str = Field(min_length=1, max_length=20)
    motivo: str | None = Field(default=None, max_length=1000)


# ============================================================
# DATOS INICIALES
# ============================================================


# Edición completa: siempre conectada y autorizada en el servidor.
class EdicionAdministrativa(BaseModel):
    anterior: dict
    cambios: dict

@router.get("/administracion/edicion")
def listar_edicion(identidad=Depends(identidad_actual)):
    exigir_administrador(identidad)
    import edicion_planillas_cloud as editor
    return editor.listar(identidad['usuario_id'])

@router.get("/administracion/edicion/{planilla_id}")
def cargar_edicion(planilla_id: int, identidad=Depends(identidad_actual)):
    exigir_administrador(identidad)
    import edicion_planillas_cloud as editor
    try:
        documento, opciones=editor.cargar(planilla_id,identidad['usuario_id'])
        return {'documento':documento,'opciones':opciones}
    except ValueError as error:
        raise HTTPException(404,str(error))

@router.put("/administracion/edicion/{planilla_id}")
def guardar_edicion(planilla_id: int, datos: EdicionAdministrativa, identidad=Depends(identidad_actual)):
    exigir_administrador(identidad)
    import edicion_planillas_cloud as editor
    try:
        return editor.guardar(planilla_id,identidad['usuario_id'],datos.anterior,datos.cambios)
    except PermissionError as error:
        raise HTTPException(403,str(error))
    except (ValueError,KeyError,TypeError) as error:
        raise HTTPException(422,str(error) if isinstance(error,ValueError) else 'Revisá los datos de la planilla.')
    except Exception:
        raise HTTPException(500,'No se pudo guardar la planilla. Volvé a abrirla para verificar su estado.')


@router.get("/inicial")
def datos_iniciales(identidad=Depends(identidad_actual)):
    contratista = es_contratista(identidad)

    productos, areas = planillascloud.obtener_catalogos()

    fecha_objetivo = planillascloud.fecha_compra_objetivo(
        contratista
    )

    hoy = planillascloud.fecha_local()

    return {
        "puede_ver_fotos": not contratista,
        "es_contratista": contratista,
        "puede_editar_planillas": "ADMINISTRADOR" in identidad["roles"],
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


# ============================================================
# APROBACIÓN DE PLANILLAS — SOLO ADMINISTRADORES
#
# IMPORTANTE:
# Estas rutas se declaran antes de las rutas dinámicas
# /{planilla_id}.
# ============================================================

@router.get("/aprobacion/pendientes")
def listar_planillas_para_aprobar(
    identidad=Depends(identidad_actual)
):
    exigir_administrador(identidad)

    try:
        return planillascloud.listar_planillas_para_aprobacion()

    except Exception:
        # No se envían detalles internos de la base de datos al cliente.
        raise HTTPException(
            status_code=500,
            detail="No se pudieron cargar las planillas pendientes."
        )


@router.get("/aprobacion/{planilla_id}")
def ver_planilla_para_aprobar(
    planilla_id: int,
    identidad=Depends(identidad_actual)
):
    exigir_administrador(identidad)

    try:
        planilla = planillascloud.obtener_planilla_para_aprobacion(
            planilla_id
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo cargar el detalle de la planilla."
        )

    if planilla is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró una planilla pendiente "
                "con ese número."
            )
        )

    return planilla


@router.post("/aprobacion/{planilla_id}/resolver")
def resolver_aprobacion(
    planilla_id: int,
    datos: ResolverAprobacion,
    identidad=Depends(identidad_actual)
):
    exigir_administrador(identidad)

    decision = datos.decision.strip().upper()

    if decision not in ("APROBAR", "RECHAZAR"):
        raise HTTPException(
            status_code=422,
            detail="La decisión debe ser APROBAR o RECHAZAR."
        )

    motivo = (datos.motivo or "").strip()

    if decision == "RECHAZAR" and len(motivo) < 3:
        raise HTTPException(
            status_code=422,
            detail="Para rechazar solicitudes, indicá un motivo."
        )

    try:
        resultado = planillascloud.resolver_aprobacion_planilla(
            planilla_id=planilla_id,
            solicitudes_ids=datos.solicitudes_ids,
            decision=decision,
            motivo=motivo,
            usuario_id=identidad["usuario_id"],
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo procesar la aprobación. "
                "No continúes hasta verificar el estado de la planilla."
            )
        )

    return {
        **resultado,
        "mensaje": (
            "Las solicitudes seleccionadas fueron aprobadas."
            if decision == "APROBAR"
            else "Las solicitudes seleccionadas fueron rechazadas."
        ),
    }


# ============================================================
# LISTAR PLANILLAS DEL USUARIO
# ============================================================

@router.get("")
def listar_planillas(identidad=Depends(identidad_actual)):
    contratista = es_contratista(identidad)

    return planillascloud.obtener_planillas_pendientes(
        identidad["persona_id"],
        contratista,
        incluir_finalizadas=not contratista
    )


# ============================================================
# CREAR PLANILLA
# ============================================================

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


# ============================================================
# VER PLANILLA
# ============================================================

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


# ============================================================
# AGREGAR SOLICITUD
# ============================================================

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


# ============================================================
# MODIFICAR SOLICITUD
# ============================================================

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


# ============================================================
# CAMBIAR ESTADO DE SOLICITUD
# ============================================================

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


# ============================================================
# CANCELAR SOLICITUD
# ============================================================

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
