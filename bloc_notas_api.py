
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from planillas_api import identidad_actual, es_contratista

import bloc_notascloud


router = APIRouter(
    prefix="/bloc-notas",
    tags=["Bloc de Comunicación"]
)


def identidad_bloc_notas(
    identidad=Depends(identidad_actual)
):
    roles = set(identidad["roles"])

    if (
        es_contratista(identidad)
        or not roles.intersection(
            {"ADMINISTRADOR", "EMPLEADO"}
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "El Bloc de Comunicación está disponible "
                "para empleados y administradores."
            )
        )

    return identidad


class DatosComunicacion(BaseModel):
    texto: str = Field(
        min_length=1,
        max_length=4000
    )


@router.get("")
def listar_comunicaciones(
    _identidad=Depends(identidad_bloc_notas)
):
    return bloc_notascloud.listar_comunicaciones()


@router.post("", status_code=201)
def agregar_comunicacion(
    datos: DatosComunicacion,
    identidad=Depends(identidad_bloc_notas)
):
    texto = datos.texto.strip()

    if not texto:
        raise HTTPException(
            status_code=422,
            detail="La comunicación no puede quedar vacía."
        )

    # Usamos directamente el nombre y apellido de la persona.
    # No usamos el nombre de usuario de inicio de sesión.
    nombre_completo = (
        f"{identidad.get('nombre', '')} "
        f"{identidad.get('apellido', '')}"
    ).strip()

    # Solo como respaldo, por si alguna identidad antigua
    # no tuviera nombre o apellido.
    if not nombre_completo:
        nombre_completo = identidad.get(
            "nombre_usuario",
            str(identidad["usuario_id"])
        )

    try:
        comunicacion_id = bloc_notascloud.agregar_comunicacion(
            usuario_id=identidad["usuario_id"],
            nombre_usuario=nombre_completo,
            texto=texto,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    return {
        "id": comunicacion_id,
        "mensaje": "Comunicación agregada correctamente."
    }