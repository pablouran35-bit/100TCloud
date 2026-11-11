from datetime import date, datetime, timedelta, timezone

from psycopg2.errors import InvalidParameterValue

import conexion
import offlinecloud


ZONA_ARGENTINA = timezone(timedelta(hours=-3))


ESTADOS_DISPONIBLES = (
    "COMPRADO Y RETIRADO",
    "COMPRADO A ENTREGAR POR PROVEEDOR/FLETE",
    "COMPRADO A ENTREGAR POR PROVEEDOR",
    "COMPRADO A ENTREGAR POR FLETE",
    "COMPRADO CON RETIRO PARCIAL",
    "ENTREGA PARCIAL",
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
                JOIN saldos_mercaderia AS sm ON sm.solicitud_id = s.id
                WHERE UPPER(COALESCE(s.estado, '')) = ANY(%s)
                  AND (sm.retirada > sm.entregada OR s.estado = 'ENTREGA PARCIAL')
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
                       s.observaciones, a.id, a.nombre, sm.retirada, sm.entregada, sm.seguimiento, s.cantidad::numeric - sm.entregada
                FROM planilla_solicitudes AS ps
                JOIN solicitudes AS s ON s.id = ps.solicitud_id
                JOIN productos AS pr ON pr.id = s.producto_id
                JOIN saldos_mercaderia AS sm ON sm.solicitud_id = s.id
                LEFT JOIN areas AS a ON a.id = s.area_id
                WHERE ps.planilla_id = %s
                  AND UPPER(COALESCE(s.estado, '')) = ANY(%s)
                  AND (sm.retirada > sm.entregada OR s.estado = 'ENTREGA PARCIAL')
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
                     "retirada": str(fila[7]), "entregada": str(fila[8]), "seguimiento": fila[9],
                     "disponible": str(fila[7] - fila[8]), "pendiente_obra": str(fila[10]),
                     "historial": historiales[fila[0]]}
                    for fila in solicitudes
                ],
            }
    finally:
        conexion_db.close()


def registrar_entrega(planilla_id, solicitud_ids, usuario_id, operacion_id=None,
                      fecha_operacion=None, cantidades=None):
    ids = sorted(set(solicitud_ids))
    if not ids:
        raise ValueError("Seleccioná al menos una solicitud para entregar.")
    cantidades = cantidades or {}
    conexion_db = conexion.conectar()
    try:
        with conexion_db, conexion_db.cursor() as cursor:
            repetida = offlinecloud.iniciar_operacion(
                cursor, operacion_id, usuario_id, "entregas:registrar"
            )
            if repetida is not None:
                return repetida
            for solicitud_id in ids:
                cantidad, anterior = cantidades.get(solicitud_id, (None, None))
                cursor.execute("""
                    SELECT registrar_entrega_mercaderia(%s, %s, %s, %s, %s, %s)
                """, (planilla_id, solicitud_id, cantidad, anterior, usuario_id, fecha_operacion))
            offlinecloud.finalizar_operacion(cursor, operacion_id, len(ids))
            return len(ids)
    except InvalidParameterValue as error:
        raise ValueError(error.diag.message_primary) from error
    finally:
        conexion_db.close()
