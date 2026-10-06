from datetime import date, datetime, timedelta, timezone

import conexion
import offlinecloud


ZONA_ARGENTINA = timezone(timedelta(hours=-3))


ESTADOS_DISPONIBLES = (
    "COMPRADO Y RETIRADO",
    "COMPRADO A ENTREGAR POR PROVEEDOR/FLETE",
)


def _fecha_texto(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor or "")


def _fecha_hora_texto(valor):
    return valor.astimezone(ZONA_ARGENTINA).strftime("%d/%m/%Y %H:%M") if isinstance(valor, datetime) else str(valor or "")


def listar_planillas_disponibles():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, o.nombre, p.fecha_compra, COUNT(s.id)
                FROM planillas AS p
                JOIN obras AS o ON o.id = p.obra_id
                JOIN planilla_solicitudes AS ps ON ps.planilla_id = p.id
                JOIN solicitudes AS s ON s.id = ps.solicitud_id
                WHERE UPPER(COALESCE(s.estado, '')) = ANY(%s)
                GROUP BY p.id, o.nombre, p.fecha_compra
                ORDER BY p.id DESC;
            """, ([estado.upper() for estado in ESTADOS_DISPONIBLES],))
            return [
                {"id": fila[0], "obra": fila[1], "fecha_compra": _fecha_texto(fila[2]),
                 "disponibles": fila[3]}
                for fila in cursor.fetchall()
            ]
    finally:
        conexion_db.close()


def obtener_planilla(planilla_id):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, o.nombre, p.fecha_compra
                FROM planillas AS p
                JOIN obras AS o ON o.id = p.obra_id
                WHERE p.id = %s;
            """, (planilla_id,))
            planilla = cursor.fetchone()
            if planilla is None:
                return None
            cursor.execute("""
                SELECT s.id, s.cantidad, pr.nombre, s.estado,
                       s.observaciones, a.id, a.nombre
                FROM planilla_solicitudes AS ps
                JOIN solicitudes AS s ON s.id = ps.solicitud_id
                JOIN productos AS pr ON pr.id = s.producto_id
                LEFT JOIN areas AS a ON a.id = s.area_id
                WHERE ps.planilla_id = %s
                  AND UPPER(COALESCE(s.estado, '')) = ANY(%s)
                ORDER BY s.id;
            """, (planilla_id, [estado.upper() for estado in ESTADOS_DISPONIBLES]))
            solicitudes = cursor.fetchall()
            ids = [fila[0] for fila in solicitudes]
            historiales = {solicitud_id: [] for solicitud_id in ids}
            if ids:
                cursor.execute("""
                    SELECT hs.solicitud_id, hs.fecha_hora, hs.estado,
                           COALESCE(NULLIF(TRIM(p.nombre || ' ' || p.apellido), ''), u.usuario, 'Usuario no disponible'),
                           hs.observaciones
                    FROM historial_solicitudes AS hs
                    LEFT JOIN usuarios AS u ON u.id = hs.usuario_id
                    LEFT JOIN personas AS p ON p.id = u.persona_id
                    WHERE hs.solicitud_id = ANY(%s)
                    ORDER BY hs.id;
                """, (ids,))
                for registro in cursor.fetchall():
                    historiales[registro[0]].append({
                        "fecha_hora": _fecha_hora_texto(registro[1]),
                        "estado": registro[2], "usuario": registro[3],
                        "observaciones": registro[4] or "",
                    })
            return {
                "id": planilla[0], "obra": planilla[1],
                "fecha_compra": _fecha_texto(planilla[2]),
                "solicitudes": [
                    {"id": fila[0], "cantidad": fila[1], "producto": fila[2],
                     "estado": fila[3], "observaciones": fila[4] or "",
                     "area_id": fila[5], "area": fila[6] or "",
                     "historial": historiales[fila[0]]}
                    for fila in solicitudes
                ],
            }
    finally:
        conexion_db.close()


def registrar_entrega(planilla_id, solicitud_ids, usuario_id, operacion_id=None,
                      fecha_operacion=None):
    ids = set(solicitud_ids)
    if not ids:
        raise ValueError("Seleccioná al menos una solicitud para entregar.")
    estados = [estado.upper() for estado in ESTADOS_DISPONIBLES]
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            repetida = offlinecloud.iniciar_operacion(
                cursor, operacion_id, usuario_id, "entregas:registrar"
            )
            if repetida is not None:
                return repetida
            cursor.execute("""
                SELECT s.id
                FROM planilla_solicitudes AS ps
                JOIN solicitudes AS s ON s.id = ps.solicitud_id
                WHERE ps.planilla_id = %s
                  AND s.id = ANY(%s)
                  AND UPPER(COALESCE(s.estado, '')) = ANY(%s)
                FOR UPDATE OF s;
            """, (planilla_id, list(ids), estados))
            disponibles = {fila[0] for fila in cursor.fetchall()}
            if disponibles != ids:
                raise ValueError("Una o más solicitudes ya no están disponibles para entregar.")
            for solicitud_id in sorted(ids):
                cursor.execute("""
                    UPDATE solicitudes SET estado = 'ENTREGADO'
                    WHERE id = %s;
                """, (solicitud_id,))
                cursor.execute("""
                    INSERT INTO historial_solicitudes
                        (solicitud_id, estado, fecha_hora, observaciones, usuario_id)
                    VALUES (%s, 'ENTREGADO', COALESCE(%s, NOW()), 'Entrega registrada desde Entregas', %s);
                """, (solicitud_id, fecha_operacion, usuario_id))
            offlinecloud.finalizar_operacion(cursor, operacion_id, len(ids))
        conexion_db.commit()
        return len(ids)
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()
