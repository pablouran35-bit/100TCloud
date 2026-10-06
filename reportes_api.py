import os

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import reportescloud

load_dotenv()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

router = APIRouter(prefix="/reportes", tags=["Reportes"])
esquema_bearer = HTTPBearer(auto_error=False)


def requiere_empleado_o_administrador(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
):
    if credenciales is None:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión.")
    try:
        datos = jwt.decode(credenciales.credentials, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="La sesión venció o no es válida.")
    if not set(datos.get("roles", [])).intersection({"ADMINISTRADOR", "EMPLEADO"}):
        raise HTTPException(status_code=403, detail="Solo empleados y administradores pueden consultar los reportes.")


def filtros_fecha(desde, hasta):
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=422, detail="La fecha desde no puede ser posterior a la fecha hasta.")


@router.get("/catalogos")
def catalogos(_=Depends(requiere_empleado_o_administrador)):
    return reportescloud.obtener_catalogos()


@router.get("/solicitudes")
def reporte_solicitudes(
    obra_id: int | None = None, persona_id: int | None = None,
    producto_id: int | None = None, proveedor_id: int | None = None,
    area_id: int | None = None, estado: str | None = None,
    desde: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hasta: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _=Depends(requiere_empleado_o_administrador),
):
    filtros_fecha(desde, hasta)
    return reportescloud.solicitudes(obra_id, persona_id, producto_id,
                                     proveedor_id, area_id, estado, desde, hasta)


@router.get("/compras")
def reporte_compras(
    planilla_id: int | None = None, obra_id: int | None = None,
    producto_id: int | None = None, proveedor_id: int | None = None,
    estado: str | None = None,
    desde: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hasta: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _=Depends(requiere_empleado_o_administrador),
):
    filtros_fecha(desde, hasta)
    return reportescloud.compras(planilla_id, obra_id, producto_id,
                                 proveedor_id, estado, desde, hasta)


@router.get("/entregas")
def reporte_entregas(
    entrega_id: int | None = None, obra_id: int | None = None,
    producto_id: int | None = None, usuario_id: int | None = None,
    desde: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    hasta: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _=Depends(requiere_empleado_o_administrador),
):
    filtros_fecha(desde, hasta)
    return reportescloud.entregas(entrega_id, obra_id, producto_id,
                                  usuario_id, desde, hasta)


@router.get("/obras")
def reporte_obras(_=Depends(requiere_empleado_o_administrador)):
    return reportescloud.obras()
