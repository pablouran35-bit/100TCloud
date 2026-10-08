
from datetime import datetime, timedelta, timezone
import os

from areas_api import router as router_areas
from articulos_api import router as router_articulos
from proveedores_api import router as router_proveedores
from planillas_api import router as router_planillas
from usuarios_api import router as router_usuarios
from tareas_api import router as router_tareas
from compras_api import router as router_compras
from entregas_api import router as router_entregas
from reportes_api import router as router_reportes
from administracion_api import router as router_administracion
from bloc_notas_api import router as router_bloc_notas

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import conexion
from seguridad import verificar_contrasena


load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("Falta JWT_SECRET_KEY en el archivo .env")

ALGORITHM = "HS256"
DURACION_SESION_HORAS = 12


app = FastAPI(
    title="100TCloud",
    version="1.0.0"
)


app.mount(
    "/app",
    StaticFiles(directory="static", html=True),
    name="app"
)


app.include_router(router_administracion)
app.include_router(router_articulos)
app.include_router(router_areas)
app.include_router(router_proveedores)
app.include_router(router_planillas)
app.include_router(router_usuarios)
app.include_router(router_tareas)
app.include_router(router_compras)
app.include_router(router_entregas)
app.include_router(router_reportes)
app.include_router(router_bloc_notas)


class DatosInicioSesion(BaseModel):
    usuario: str
    contrasena: str


@app.get("/")
def inicio():
    return {
        "mensaje": "100TCloud API en funcionamiento"
    }


@app.post("/auth/login")
def iniciar_sesion(datos: DatosInicioSesion):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.usuario,
                    u.contrasena_hash,
                    p.nombre,
                    p.apellido,
                    p.activo
                FROM usuarios AS u
                JOIN personas AS p
                    ON p.id = u.persona_id
                WHERE u.usuario = %s
                """,
                (datos.usuario,)
            )

            usuario_db = cursor.fetchone()

            if usuario_db is None:
                raise HTTPException(
                    status_code=401,
                    detail="Usuario o contraseña incorrectos."
                )

            (
                usuario_id,
                nombre_usuario,
                hash_guardado,
                nombre,
                apellido,
                persona_activa
            ) = usuario_db

            contrasena_valida = verificar_contrasena(
                datos.contrasena,
                hash_guardado
            )

            if not persona_activa or not contrasena_valida:
                raise HTTPException(
                    status_code=401,
                    detail="Usuario o contraseña incorrectos."
                )

            cursor.execute(
                """
                SELECT r.nombre
                FROM usuario_rol AS ur
                JOIN roles AS r
                    ON r.id = ur.rol_id
                WHERE ur.usuario_id = %s
                ORDER BY r.id
                """,
                (usuario_id,)
            )

            roles = [
                fila[0]
                for fila in cursor.fetchall()
            ]

            if not roles:
                raise HTTPException(
                    status_code=403,
                    detail="El usuario todavía no tiene un rol asignado."
                )

    finally:
        conexion_db.close()


    vence = datetime.now(timezone.utc) + timedelta(
        hours=DURACION_SESION_HORAS
    )


    token = jwt.encode(
        {
            "sub": str(usuario_id),
            "roles": roles,
            "exp": vence
        },
        JWT_SECRET_KEY,
        algorithm=ALGORITHM
    )


    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario_id,
            "nombre_usuario": nombre_usuario,
            "nombre": nombre,
            "apellido": apellido,
            "roles": roles
        }
    }
