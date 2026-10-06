import os

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import obrascloud


load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

if not JWT_SECRET_KEY:
    raise RuntimeError("Falta JWT_SECRET_KEY en el archivo .env")

router = APIRouter(
    prefix="/administracion",
    tags=["Administración"]
)

esquema_bearer = HTTPBearer(auto_error=False)


def requiere_administrador(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)
):
    if credenciales is None:
        raise HTTPException(
            status_code=401,
            detail="Necesitás iniciar sesión."
        )

    try:
        datos_token = jwt.decode(
            credenciales.credentials,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="La sesión venció o no es válida."
        )

    roles = datos_token.get("roles", [])

    if "ADMINISTRADOR" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Solo un administrador puede gestionar usuarios."
        )


def requiere_administracion(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)
):
    if credenciales is None:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión.")
    try:
        datos_token = jwt.decode(
            credenciales.credentials,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="La sesión venció o no es válida.")
    roles = datos_token.get("roles", [])
    if not set(roles).intersection({"ADMINISTRADOR", "EMPLEADO"}):
        raise HTTPException(
            status_code=403,
            detail="Esta sección es solo para empleados y administradores."
        )


class DatosObra(BaseModel):
    nombre: str
    direccion: str | None = None
    observaciones: str | None = None


class EstadoObra(BaseModel):
    activo: bool


class ContratistasObra(BaseModel):
    persona_ids: list[int] = Field(default_factory=list)


@router.get("/obras")
def listar_obras(
    _administrador=Depends(requiere_administracion)
):
    obras = obrascloud.obtener_obras(incluir_inactivas=True)

    return [
        {
            "id": obra[0],
            "nombre": obra[1],
            "direccion": obra[2],
            "activo": obra[3],
            "observaciones": obra[4],
            "contratistas": obra[5]
        }
        for obra in obras
    ]


@router.post("/obras", status_code=201)
def crear_obra(
    datos: DatosObra,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre de la obra no puede quedar vacío."
        )

    obra_id = obrascloud.crear_obra(
        nombre,
        datos.direccion,
        datos.observaciones
    )

    return {
        "id": obra_id,
        "mensaje": "Obra creada correctamente."
    }


@router.put("/obras/{obra_id}")
def modificar_obra(
    obra_id: int,
    datos: DatosObra,
    _administrador=Depends(requiere_administracion)
):
    nombre = datos.nombre.strip()

    if not nombre:
        raise HTTPException(
            status_code=422,
            detail="El nombre de la obra no puede quedar vacío."
        )

    filas = obrascloud.actualizar_obra(
        obra_id,
        nombre,
        datos.direccion,
        datos.observaciones
    )

    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró esa obra.")

    return {"mensaje": "Obra modificada correctamente."}


@router.patch("/obras/{obra_id}/estado")
def cambiar_estado_obra(
    obra_id: int,
    datos: EstadoObra,
    _administrador=Depends(requiere_administracion)
):
    filas = obrascloud.cambiar_estado_obra(obra_id, datos.activo)

    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró esa obra.")

    return {"mensaje": "Estado de la obra actualizado correctamente."}


@router.get("/obras/{obra_id}/contratistas")
def obtener_contratistas_obra(
    obra_id: int,
    _administrador=Depends(requiere_administracion)
):
    filas = obrascloud.obtener_contratistas_obra(obra_id)
    if filas is None:
        raise HTTPException(status_code=404, detail="No se encontró esa obra.")
    return [
        {
            "persona_id": fila[0],
            "nombre": f"{fila[2]}, {fila[1]}".strip(", "),
            "usuario": fila[3],
            "activo": fila[4],
            "asignado": fila[5],
        }
        for fila in filas
    ]


@router.put("/obras/{obra_id}/contratistas")
def guardar_contratistas_obra(
    obra_id: int,
    datos: ContratistasObra,
    _administrador=Depends(requiere_administracion)
):
    try:
        guardada = obrascloud.guardar_contratistas_obra(
            obra_id, datos.persona_ids
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not guardada:
        raise HTTPException(status_code=404, detail="No se encontró esa obra.")
    return {"mensaje": "Contratistas asignados correctamente."}
