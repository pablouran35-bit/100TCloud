import os

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import usuarioscloud
from administracion_api import requiere_administrador
from seguridad import crear_hash_contrasena, verificar_contrasena


load_dotenv()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

router = APIRouter(tags=["Administración de usuarios"])
esquema_bearer = HTTPBearer(auto_error=False)


class DatosUsuario(BaseModel):
    usuario: str
    contrasena: str
    rol_ids: list[int]
    persona_id: int | None = None
    nombre: str | None = None
    apellido: str | None = None
    telefono: str | None = None
    email: str | None = None


class DatosActualizacionUsuario(BaseModel):
    nombre: str
    apellido: str
    telefono: str | None = None
    email: str | None = None
    rol_ids: list[int]


class DatosContrasena(BaseModel):
    contrasena: str


class EstadoUsuario(BaseModel):
    activo: bool


class DatosCambioContrasena(BaseModel):
    contrasena_actual: str
    contrasena_nueva: str


def limpiar_opcional(valor):
    return valor.strip() if valor and valor.strip() else None


def validar_roles(rol_ids):
    if not rol_ids:
        raise HTTPException(status_code=422, detail="Asigná al menos un rol.")


@router.get("/administracion/usuarios")
def listar_usuarios(_administrador=Depends(requiere_administrador)):
    usuarios = usuarioscloud.obtener_usuarios()
    roles = usuarioscloud.obtener_roles()
    personas = usuarioscloud.obtener_personas_sin_usuario()
    return {
        "usuarios": [
            {
                "id": u[0], "usuario": u[1], "persona_id": u[2],
                "nombre": u[3], "apellido": u[4], "telefono": u[5],
                "email": u[6], "activo": u[7], "roles": u[8],
            }
            for u in usuarios
        ],
        "roles": [{"id": r[0], "nombre": r[1]} for r in roles],
        "personas_disponibles": [
            {
                "id": p[0], "nombre": p[1], "apellido": p[2],
                "telefono": p[3], "email": p[4],
            }
            for p in personas
        ],
    }


@router.post("/administracion/usuarios", status_code=201)
def crear_usuario(datos: DatosUsuario,
                  _administrador=Depends(requiere_administrador)):
    usuario = datos.usuario.strip()
    validar_roles(datos.rol_ids)
    if not usuario:
        raise HTTPException(status_code=422, detail="El nombre de usuario no puede quedar vacío.")
    if not datos.contrasena.strip():
        raise HTTPException(status_code=422, detail="La contraseña inicial no puede quedar vacía.")

    if datos.persona_id is None and not (datos.nombre or "").strip():
        raise HTTPException(status_code=422, detail="Completá el nombre de la persona.")
    if datos.persona_id is None and not (datos.apellido or "").strip():
        raise HTTPException(status_code=422, detail="Completá el apellido de la persona.")
    if datos.persona_id is not None and any(
        limpiar_opcional(valor)
        for valor in (datos.nombre, datos.apellido, datos.telefono, datos.email)
    ):
        raise HTTPException(
            status_code=422,
            detail="Elegí una persona existente o completá los datos de una nueva, no ambas opciones."
        )

    try:
        usuario_id = usuarioscloud.crear_usuario(
            usuario,
            crear_hash_contrasena(datos.contrasena),
            datos.rol_ids,
            persona_id=datos.persona_id,
            nombre=limpiar_opcional(datos.nombre),
            apellido=limpiar_opcional(datos.apellido),
            telefono=limpiar_opcional(datos.telefono),
            email=limpiar_opcional(datos.email),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except Exception as error:
        if getattr(error, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Ese nombre de usuario ya está usado.")
        raise
    return {"id": usuario_id, "mensaje": "Usuario creado correctamente."}


@router.put("/administracion/usuarios/{usuario_id}")
def modificar_usuario(usuario_id: int, datos: DatosActualizacionUsuario,
                      _administrador=Depends(requiere_administrador)):
    validar_roles(datos.rol_ids)
    nombre = datos.nombre.strip()
    apellido = datos.apellido.strip()
    if not nombre or not apellido:
        raise HTTPException(status_code=422, detail="Nombre y apellido son obligatorios.")
    try:
        filas = usuarioscloud.actualizar_usuario(
            usuario_id, nombre, apellido,
            limpiar_opcional(datos.telefono),
            limpiar_opcional(datos.email), datos.rol_ids
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró ese usuario.")
    return {"mensaje": "Usuario modificado correctamente."}


@router.patch("/administracion/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(usuario_id: int, datos: EstadoUsuario,
                           _administrador=Depends(requiere_administrador)):
    filas = usuarioscloud.cambiar_estado_usuario(usuario_id, datos.activo)
    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró ese usuario.")
    return {"mensaje": "Estado del usuario actualizado correctamente."}


@router.put("/administracion/usuarios/{usuario_id}/contrasena")
def restablecer_contrasena(usuario_id: int, datos: DatosContrasena,
                           _administrador=Depends(requiere_administrador)):
    if not datos.contrasena.strip():
        raise HTTPException(status_code=422, detail="La contraseña no puede quedar vacía.")
    filas = usuarioscloud.actualizar_contrasena(
        usuario_id, crear_hash_contrasena(datos.contrasena)
    )
    if filas == 0:
        raise HTTPException(status_code=404, detail="No se encontró ese usuario.")
    return {"mensaje": "Contraseña actualizada correctamente."}


@router.post("/auth/cambiar-contrasena")
def cambiar_contrasena(datos: DatosCambioContrasena,
                       credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)):
    if credenciales is None:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión.")
    try:
        contenido_token = jwt.decode(
            credenciales.credentials, JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )
        usuario_id = int(contenido_token["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="La sesión venció o no es válida.")

    if not verificar_contrasena(
        datos.contrasena_actual,
        usuarioscloud.obtener_hash_contrasena(usuario_id)
    ):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    if not datos.contrasena_nueva.strip():
        raise HTTPException(status_code=422, detail="La contraseña nueva no puede quedar vacía.")

    usuarioscloud.actualizar_contrasena(
        usuario_id, crear_hash_contrasena(datos.contrasena_nueva)
    )
    return {"mensaje": "Contraseña cambiada correctamente."}
