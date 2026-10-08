from datetime import date, datetime, timedelta, timezone

import conexion


# ==========================================================
# ZONA HORARIA ARGENTINA
# ==========================================================

ZONA_ARGENTINA = timezone(timedelta(hours=-3))


# ==========================================================
# FORMATEAR FECHA
# ==========================================================

def _fecha_texto(valor):
    if isinstance(valor, (date, datetime)):
        if isinstance(valor, datetime):
            return valor.date().isoformat()

        return valor.isoformat()

    return str(valor or "")


# ==========================================================
# FORMATEAR HORA
# ==========================================================

def _hora_texto(valor):
    if isinstance(valor, datetime):

        # Si PostgreSQL devuelve un datetime con zona horaria,
        # lo convertimos explícitamente a la hora argentina.
        if valor.tzinfo is not None:
            valor = valor.astimezone(ZONA_ARGENTINA)

        return valor.strftime("%H:%M")

    return str(valor or "")


# ==========================================================
# LISTAR COMUNICACIONES
# ==========================================================

def listar_comunicaciones(fecha=None):

    if fecha is None:
        fecha = datetime.now(ZONA_ARGENTINA).date()

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    usuario_id,
                    nombre_usuario,
                    fecha,
                    hora,
                    texto
                FROM bloc_notas
                WHERE fecha = %s
                ORDER BY hora ASC, id ASC;
                """,
                (fecha,)
            )

            return [
                {
                    "id": fila[0],
                    "usuario_id": fila[1],
                    "nombre_usuario": fila[2],
                    "fecha": _fecha_texto(fila[3]),
                    "hora": _hora_texto(fila[4]),
                    "texto": fila[5],
                }
                for fila in cursor.fetchall()
            ]

    finally:
        conexion_db.close()


# ==========================================================
# AGREGAR COMUNICACIÓN
# ==========================================================

def agregar_comunicacion(
    usuario_id,
    nombre_usuario,
    texto
):

    texto = texto.strip()

    if not texto:
        raise ValueError(
            "La comunicación no puede quedar vacía."
        )

    if len(texto) > 4000:
        raise ValueError(
            "La comunicación no puede superar "
            "los 4000 caracteres."
        )

    ahora = datetime.now(ZONA_ARGENTINA)

    fecha_actual = ahora.date()

    conexion_db = conexion.conectar()

    try:

        with conexion_db.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO bloc_notas (
                    usuario_id,
                    nombre_usuario,
                    fecha,
                    hora,
                    texto
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id;
                """,
                (
                    usuario_id,
                    nombre_usuario,
                    fecha_actual,
                    ahora,
                    texto,
                )
            )

            comunicacion_id = cursor.fetchone()[0]

        conexion_db.commit()

        return comunicacion_id

    except Exception:

        conexion_db.rollback()

        raise

    finally:

        conexion_db.close()