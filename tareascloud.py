from datetime import date, datetime

import conexion
import offlinecloud


ESTADOS_TAREA = ("PENDIENTE", "EN PROCESO", "FINALIZADA", "CANCELADA")


def _fecha_texto(valor):
    if isinstance(valor, (date, datetime)):
        return valor.date().isoformat() if isinstance(valor, datetime) else valor.isoformat()
    return str(valor or "")


def _fecha_hora_texto(valor):
    return valor.isoformat(sep=" ", timespec="minutes") if isinstance(valor, datetime) else str(valor or "")


def listar_tareas():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT t.id, t.descripcion, t.solicitante_id,
                       p.nombre, p.apellido, t.fecha_solicitud,
                       t.estado, t.observaciones
                FROM tareas AS t
                JOIN personas AS p ON p.id = t.solicitante_id
                ORDER BY t.id DESC;
            """)
            return [
                {
                    "id": fila[0], "descripcion": fila[1],
                    "solicitante_id": fila[2],
                    "solicitante": f"{fila[3]} {fila[4]}".strip(),
                    "fecha_solicitud": _fecha_texto(fila[5]),
                    "estado": fila[6], "observaciones": fila[7] or "",
                }
                for fila in cursor.fetchall()
            ]
    finally:
        conexion_db.close()


def obtener_tarea(tarea_id):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT t.id, t.descripcion, t.solicitante_id,
                       p.nombre, p.apellido, t.fecha_solicitud,
                       t.estado, t.observaciones
                FROM tareas AS t
                JOIN personas AS p ON p.id = t.solicitante_id
                WHERE t.id = %s;
            """, (tarea_id,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            cursor.execute("""
                SELECT ht.fecha_hora, ht.estado,
                       COALESCE(NULLIF(TRIM(p.nombre || ' ' || p.apellido), ''), u.usuario, 'Usuario no disponible'),
                       ht.observaciones
                FROM historial_tareas AS ht
                LEFT JOIN usuarios AS u ON u.id = ht.usuario_id
                LEFT JOIN personas AS p ON p.id = u.persona_id
                WHERE ht.tarea_id = %s
                ORDER BY ht.id;
            """, (tarea_id,))
            historial = [
                {
                    "fecha_hora": _fecha_hora_texto(registro[0]),
                    "estado": registro[1], "usuario": registro[2],
                    "observaciones": registro[3] or "",
                }
                for registro in cursor.fetchall()
            ]
            return {
                "id": fila[0], "descripcion": fila[1],
                "solicitante_id": fila[2],
                "solicitante": f"{fila[3]} {fila[4]}".strip(),
                "fecha_solicitud": _fecha_texto(fila[5]),
                "estado": fila[6], "observaciones": fila[7] or "",
                "historial": historial,
            }
    finally:
        conexion_db.close()


def crear_tarea(descripcion, solicitante_id, fecha_solicitud, observaciones,
                usuario_id, operacion_id=None, fecha_operacion=None):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            repetida = offlinecloud.iniciar_operacion(
                cursor, operacion_id, usuario_id, "tareas:crear"
            )
            if repetida is not None:
                return repetida
            cursor.execute("""
                INSERT INTO tareas
                    (descripcion, solicitante_id, fecha_solicitud, estado, observaciones)
                VALUES (%s, %s, %s, 'PENDIENTE', %s)
                RETURNING id;
            """, (descripcion, solicitante_id, fecha_solicitud, observaciones))
            tarea_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO historial_tareas
                    (tarea_id, estado, fecha_hora, observaciones, usuario_id)
                VALUES (%s, 'PENDIENTE', COALESCE(%s, NOW()), %s, %s);
            """, (tarea_id, fecha_operacion, observaciones, usuario_id))
            offlinecloud.finalizar_operacion(cursor, operacion_id, tarea_id)
        conexion_db.commit()
        return tarea_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_tarea(tarea_id, descripcion, fecha_solicitud, estado,
                     observaciones, usuario_id, operacion_id=None,
                     fecha_operacion=None):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            repetida = offlinecloud.iniciar_operacion(
                cursor, operacion_id, usuario_id, "tareas:modificar"
            )
            if repetida is not None:
                return repetida
            cursor.execute("""
                UPDATE tareas
                SET descripcion = %s,
                    fecha_solicitud = %s,
                    estado = %s,
                    observaciones = %s
                WHERE id = %s;
            """, (descripcion, fecha_solicitud, estado, observaciones, tarea_id))
            if cursor.rowcount == 0:
                return False
            cursor.execute("""
                INSERT INTO historial_tareas
                    (tarea_id, estado, fecha_hora, observaciones, usuario_id)
                VALUES (%s, %s, COALESCE(%s, NOW()), %s, %s);
            """, (tarea_id, estado, fecha_operacion, observaciones, usuario_id))
            offlinecloud.finalizar_operacion(cursor, operacion_id, True)
        conexion_db.commit()
        return True
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()
