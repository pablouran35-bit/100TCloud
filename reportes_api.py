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


# Exportar la instantánea mostrada: no volver a consultar y cambiar los resultados.
from fastapi import Request,Response
from pydantic import BaseModel,Field,ValidationError
from planillas_api import identidad_actual
from exportar_reportes_excel import crear_excel,CAMPOS
from datetime import datetime,timedelta,timezone

class FiltroExcel(BaseModel):
    campo:str=Field(max_length=100)
    valor:str=Field(max_length=2000)
class ConsultaExcel(BaseModel):
    tipo:str
    filas:list[dict[str,str|int|float|bool|None]]=Field(max_length=20000)
    filtros:list[FiltroExcel]=Field(default_factory=list,max_length=30)

@router.post('/exportar-excel')
async def exportar_consulta_excel(request:Request,identidad=Depends(identidad_actual)):
    if not set(identidad['roles']).intersection({'EMPLEADO','ADMINISTRADOR'}):
        raise HTTPException(403,'Solo empleados y administradores pueden exportar reportes.')
    contenido=bytearray()
    async for parte in request.stream():
        if len(contenido)+len(parte)>20*1024*1024:raise HTTPException(413,'La consulta es muy grande. Aplicá más filtros antes de exportar.')
        contenido.extend(parte)
    try:datos=ConsultaExcel.model_validate_json(bytes(contenido))
    except ValidationError:raise HTTPException(422,'Consulta inválida o demasiado grande para exportar. Aplicá más filtros.')
    if datos.tipo not in CAMPOS:raise HTTPException(422,'Tipo de reporte inválido.')
    campos=CAMPOS[datos.tipo];encabezados=[p[0] for p in campos]
    filas=[[f.get(campo) for _,campo in campos] for f in datos.filas]
    from starlette.concurrency import run_in_threadpool
    archivo=await run_in_threadpool(crear_excel,'100T · '+datos.tipo.capitalize(),encabezados,filas,[(f.campo,f.valor) for f in datos.filtros])
    nombre='100T_'+datos.tipo+'_'+datetime.now(timezone(timedelta(hours=-3))).strftime('%Y%m%d_%H%M%S')+'.xlsx'
    return Response(archivo,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{nombre}"','Cache-Control':'private, no-store'})
