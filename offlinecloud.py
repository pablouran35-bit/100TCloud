"""Ayudas para que una operación offline repetida no duplique cambios."""

from psycopg2.extras import Json


def iniciar_operacion(cursor, operacion_id, usuario_id, recurso):
    """Reserva una clave dentro de la misma transacción que el cambio real.

    Devuelve el resultado ya guardado si el teléfono reenvía una operación que
    el servidor había terminado antes de que llegara la respuesta al teléfono.
    """
    if not operacion_id:
        return None

    cursor.execute(
        """
        INSERT INTO operaciones_offline
            (operacion_id, usuario_id, recurso, resultado)
        VALUES (%s, %s, %s, NULL)
        ON CONFLICT (operacion_id) DO NOTHING
        RETURNING operacion_id;
        """,
        (operacion_id, usuario_id, recurso),
    )
    if cursor.fetchone() is not None:
        return None

    cursor.execute(
        """
        SELECT usuario_id, recurso, resultado
        FROM operaciones_offline
        WHERE operacion_id = %s;
        """,
        (operacion_id,),
    )
    guardada = cursor.fetchone()
    if guardada is None:
        raise RuntimeError("No se pudo recuperar la operación de sincronización.")
    if guardada[0] != usuario_id or guardada[1] != recurso:
        raise ValueError("La clave de sincronización ya pertenece a otro cambio.")
    if guardada[2] is None:
        raise RuntimeError("La operación anterior todavía no terminó; se puede reintentar.")
    return guardada[2]


def finalizar_operacion(cursor, operacion_id, resultado):
    if not operacion_id:
        return
    cursor.execute(
        """
        UPDATE operaciones_offline
        SET resultado = %s
        WHERE operacion_id = %s;
        """,
        (Json(resultado), operacion_id),
    )
