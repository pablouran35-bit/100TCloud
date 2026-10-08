from datetime import datetime, timedelta, timezone

import conexion
import offlinecloud


# Estados válidos para una solicitud.
ESTADOS_SOLICITUD = (
    "PENDIENTE DE COMPRA",
    "SOLICITADO",
    "PENDIENTE",
    "COMPRADO Y RETIRADO",
    "COMPRADO A RETIRAR",
    "SEÑADO A RETIRAR",
    "ENCARGADO",
    "NO DISPONIBLE",
    "COMPRADO A ENTREGAR POR PROVEEDOR/FLETE",
    "ENTREGADO",
    "CANCELADA",
)


class ConflictoSolicitud(Exception):
    """
    Indica que una solicitud cambió en Cloud mientras el usuario
    estaba trabajando sin conexión.
    """

    def __init__(self, solicitud_id, estado_anterior, estado_cloud):
        self.solicitud_id = solicitud_id
        self.estado_anterior = estado_anterior
        self.estado_cloud = estado_cloud

        super().__init__(
            "La solicitud cambió mientras estabas sin conexión."
        )


def fecha_local():
    zona_argentina = timezone(timedelta(hours=-3))
    return datetime.now(zona_argentina).date()


def fecha_compra_objetivo(es_contratista, hoy=None):
    hoy = hoy or fecha_local()

    # Python: lunes=0, martes=1, ..., domingo=6.
    if es_contratista and hoy.weekday() in (0, 1):
        return hoy + timedelta(
            days=8 if hoy.weekday() == 0 else 7
        )

    dias = (1 - hoy.weekday()) % 7

    if dias == 0:
        dias = 7

    return hoy + timedelta(days=dias)


def puede_modificar_fecha(fecha_planilla, es_contratista, hoy=None):
    hoy = hoy or fecha_local()
    objetivo = fecha_compra_objetivo(es_contratista, hoy)

    if es_contratista:
        if hoy.weekday() in (0, 1):
            return fecha_planilla == objetivo

        inicio = hoy - timedelta(days=hoy.weekday() - 2)
        fin = inicio + timedelta(days=4)  # Miércoles a domingo.

    else:
        dias_desde_miercoles = (hoy.weekday() - 2) % 7
        inicio = hoy - timedelta(days=dias_desde_miercoles)
        fin = inicio + timedelta(days=6)  # Miércoles a martes.

    # La PC guarda la fecha en que se creó la planilla; el móvil guarda
    # la próxima fecha de compra. Se aceptan ambas formas en la semana activa.
    return inicio <= fecha_planilla <= fin or fecha_planilla == objetivo


def obtener_identidad(usuario_id):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.id,
                    p.activo,
                    p.nombre,
                    p.apellido,
                    u.usuario
                FROM usuarios AS u
                JOIN personas AS p
                    ON p.id = u.persona_id
                WHERE u.id = %s;
            """, (usuario_id,))

            persona = cursor.fetchone()

            if persona is None:
                return None

            cursor.execute("""
                SELECT r.nombre
                FROM usuario_rol AS ur
                JOIN roles AS r
                    ON r.id = ur.rol_id
                WHERE ur.usuario_id = %s
                ORDER BY r.id;
            """, (usuario_id,))

            roles = [
                fila[0].upper()
                for fila in cursor.fetchall()
            ]

            return {
                "persona_id": persona[0],
                "activo": persona[1],
                "nombre": persona[2] or "",
                "apellido": persona[3] or "",
                "nombre_usuario": persona[4] or "",
                "roles": roles,
            }

    finally:
        conexion_db.close()

def obtener_obras_disponibles(persona_id, es_contratista):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            if es_contratista:
                cursor.execute("""
                    SELECT o.id, o.nombre
                    FROM obras AS o
                    JOIN persona_obra AS po
                        ON po.obra_id = o.id
                    WHERE po.persona_id = %s
                      AND o.activo = TRUE
                    ORDER BY o.nombre, o.id;
                """, (persona_id,))

            else:
                cursor.execute("""
                    SELECT id, nombre
                    FROM obras
                    WHERE activo = TRUE
                    ORDER BY nombre, id;
                """)

            return cursor.fetchall()

    finally:
        conexion_db.close()


def obtener_catalogos():
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            cursor.execute("""
                SELECT id, nombre, unidad
                FROM productos
                WHERE activo = TRUE
                ORDER BY nombre, id;
            """)

            productos = cursor.fetchall()

            cursor.execute("""
                SELECT id, nombre
                FROM areas
                WHERE activo = TRUE
                ORDER BY id;
            """)

            areas = cursor.fetchall()

            return productos, areas

    finally:
        conexion_db.close()


def obtener_planillas_pendientes(persona_id, es_contratista):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            filtro_contratista = ""
            parametros = []

            if es_contratista:
                filtro_contratista = """
                    AND EXISTS (
                        SELECT 1
                        FROM persona_obra AS po
                        WHERE po.persona_id = %s
                          AND po.obra_id = p.obra_id
                    )
                """

                parametros.append(persona_id)

            cursor.execute(f"""
                SELECT
                    p.id,
                    p.obra_id,
                    o.nombre,
                    p.fecha_compra,
                    p.estado,
                    p.observaciones,
                    COUNT(*) AS pendientes,
                    array_to_string(
                        array_agg(
                            DISTINCT NULLIF(
                                TRIM(
                                    per.nombre || ' ' || per.apellido
                                ),
                                ''
                            )
                        ) FILTER (WHERE per.id IS NOT NULL),
                        ', '
                    ) AS solicitantes
                FROM planillas AS p
                JOIN obras AS o
                    ON o.id = p.obra_id
                JOIN planilla_solicitudes AS ps
                    ON ps.planilla_id = p.id
                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id
                LEFT JOIN personas AS per
                    ON per.id = s.persona_id
                WHERE UPPER(COALESCE(s.estado, ''))
                    NOT IN ('ENTREGADO', 'CANCELADA')
                  {filtro_contratista}
                GROUP BY
                    p.id,
                    p.obra_id,
                    o.nombre,
                    p.fecha_compra,
                    p.estado,
                    p.observaciones
                ORDER BY
                    p.fecha_compra DESC,
                    o.nombre,
                    p.id DESC;
            """, tuple(parametros))

            filas = cursor.fetchall()

            return [
                {
                    "id": fila[0],
                    "obra_id": fila[1],
                    "obra": fila[2],
                    "fecha_compra": fila[3],
                    "estado": fila[4],
                    "observaciones": fila[5],
                    "pendientes": fila[6],
                    "solicitantes": fila[7] or "",
                    "puede_modificar": puede_modificar_fecha(
                        fila[3],
                        es_contratista
                    ),
                }
                for fila in filas
            ]

    finally:
        conexion_db.close()


def obtener_planilla(planilla_id, persona_id, es_contratista):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            cursor.execute("""
                SELECT
                    p.id,
                    p.obra_id,
                    o.nombre,
                    p.fecha_compra,
                    p.estado,
                    p.observaciones
                FROM planillas AS p
                JOIN obras AS o
                    ON o.id = p.obra_id
                WHERE p.id = %s
                  AND (
                      %s = FALSE
                      OR EXISTS (
                          SELECT 1
                          FROM persona_obra AS po
                          WHERE po.persona_id = %s
                            AND po.obra_id = p.obra_id
                      )
                  );
            """, (
                planilla_id,
                es_contratista,
                persona_id
            ))

            fila = cursor.fetchone()

            if fila is None:
                return None

            cursor.execute("""
                SELECT
                    s.id,
                    s.producto_id,
                    pr.nombre,
                    pr.unidad,
                    s.cantidad,
                    s.area_id,
                    a.nombre,
                    s.observaciones,
                    s.estado,
                    s.fecha_solicitud,
                    pe.nombre,
                    pe.apellido,
                    EXISTS (
                        SELECT 1
                        FROM compras AS c
                        WHERE c.solicitud_id = s.id
                    ) AS tiene_compras
                FROM planilla_solicitudes AS ps
                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id
                JOIN productos AS pr
                    ON pr.id = s.producto_id
                JOIN areas AS a
                    ON a.id = s.area_id
                JOIN personas AS pe
                    ON pe.id = s.persona_id
                WHERE ps.planilla_id = %s
                  AND UPPER(COALESCE(s.estado, '')) <> 'CANCELADA'
                ORDER BY
                    s.fecha_solicitud,
                    s.id;
            """, (planilla_id,))

            solicitudes = [
                {
                    "id": s[0],
                    "producto_id": s[1],
                    "producto": s[2],
                    "unidad": s[3],
                    "cantidad": s[4],
                    "area_id": s[5],
                    "area": s[6],
                    "observaciones": s[7],
                    "estado": s[8],
                    "fecha_solicitud": s[9],
                    "persona": f"{s[10]} {s[11]}".strip(),
                    "tiene_compras": s[12],
                }
                for s in cursor.fetchall()
            ]

            return {
                "id": fila[0],
                "obra_id": fila[1],
                "obra": fila[2],
                "fecha_compra": fila[3],
                "estado": fila[4],
                "observaciones": fila[5],
                "solicitudes": solicitudes,
            }

    finally:
        conexion_db.close()


def crear_planilla(
    obra_id,
    fecha_compra,
    usuario_id=None,
    operacion_id=None
):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "planillas:crear"
            )

            if repetida is not None:
                return tuple(repetida)

            cursor.execute("""
                SELECT id
                FROM planillas
                WHERE obra_id = %s
                  AND fecha_compra = %s
                ORDER BY id DESC
                LIMIT 1;
            """, (
                obra_id,
                fecha_compra
            ))

            existente = cursor.fetchone()

            if existente:
                resultado = (
                    existente[0],
                    False
                )

            else:
                cursor.execute("""
                    INSERT INTO planillas (
                        obra_id,
                        fecha_compra,
                        estado
                    )
                    VALUES (
                        %s,
                        %s,
                        'ABIERTA'
                    )
                    RETURNING id;
                """, (
                    obra_id,
                    fecha_compra
                ))

                resultado = (
                    cursor.fetchone()[0],
                    True
                )

            offlinecloud.finalizar_operacion(
                cursor,
                operacion_id,
                list(resultado)
            )

        conexion_db.commit()

        return resultado

    except Exception:
        conexion_db.rollback()
        raise

    finally:
        conexion_db.close()


def agregar_solicitud(
    planilla_id,
    persona_id,
    usuario_id,
    producto_id,
    area_id,
    cantidad,
    observaciones,
    operacion_id=None,
    fecha_operacion=None
):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "planillas:agregar-solicitud"
            )

            if repetida is not None:
                return repetida

            cursor.execute("""
                SELECT obra_id
                FROM planillas
                WHERE id = %s;
            """, (planilla_id,))

            fila_planilla = cursor.fetchone()

            if fila_planilla is None:
                raise ValueError(
                    "No se encontró esa planilla."
                )

            obra_id = fila_planilla[0]

            cursor.execute("""
                SELECT id
                FROM productos
                WHERE id = %s
                  AND activo = TRUE;
            """, (producto_id,))

            if cursor.fetchone() is None:
                raise ValueError(
                    "El artículo seleccionado no está activo."
                )

            cursor.execute("""
                SELECT id
                FROM areas
                WHERE id = %s
                  AND activo = TRUE;
            """, (area_id,))

            if cursor.fetchone() is None:
                raise ValueError(
                    "El área seleccionada no está activa."
                )

            cursor.execute("""
                INSERT INTO solicitudes (
                    persona_id,
                    obra_id,
                    producto_id,
                    cantidad,
                    observaciones,
                    fecha_solicitud,
                    estado,
                    area_id
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    'PENDIENTE DE COMPRA',
                    %s
                )
                RETURNING id;
            """, (
                persona_id,
                obra_id,
                producto_id,
                cantidad,
                observaciones,
                fecha_operacion,
                area_id
            ))

            solicitud_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO planilla_solicitudes (
                    planilla_id,
                    solicitud_id
                )
                VALUES (%s, %s);
            """, (
                planilla_id,
                solicitud_id
            ))

            cursor.execute("""
                INSERT INTO historial_solicitudes (
                    solicitud_id,
                    estado,
                    fecha_hora,
                    observaciones,
                    usuario_id
                )
                VALUES (
                    %s,
                    'PENDIENTE DE COMPRA',
                    COALESCE(%s, NOW()),
                    'Solicitud creada',
                    %s
                );
            """, (
                solicitud_id,
                fecha_operacion,
                usuario_id
            ))

            offlinecloud.finalizar_operacion(
                cursor,
                operacion_id,
                solicitud_id
            )

        conexion_db.commit()

        return solicitud_id

    except Exception:
        conexion_db.rollback()
        raise

    finally:
        conexion_db.close()


def _solicitud_editable(cursor, planilla_id, solicitud_id):
    cursor.execute("""
        SELECT
            s.estado,
            EXISTS (
                SELECT 1
                FROM compras AS c
                WHERE c.solicitud_id = s.id
            )
        FROM planilla_solicitudes AS ps
        JOIN solicitudes AS s
            ON s.id = ps.solicitud_id
        WHERE ps.planilla_id = %s
          AND s.id = %s
        FOR UPDATE OF s;
    """, (
        planilla_id,
        solicitud_id
    ))

    fila = cursor.fetchone()

    if fila is None:
        raise ValueError(
            "No se encontró esa solicitud dentro de la planilla."
        )

    estado, tiene_compras = fila

    if (estado or "").upper() == "ENTREGADO":
        raise ValueError(
            "No se puede modificar ni cancelar una solicitud entregada."
        )

    if (estado or "").upper() == "CANCELADA":
        raise ValueError(
            "La solicitud ya está cancelada."
        )

    if tiene_compras:
        raise ValueError(
            "La solicitud ya tiene una compra registrada; "
            "no se puede modificar ni cancelar."
        )

    return estado or "PENDIENTE DE COMPRA"


def actualizar_solicitud(
    planilla_id,
    solicitud_id,
    usuario_id,
    producto_id,
    area_id,
    cantidad,
    observaciones,
    operacion_id=None,
    fecha_operacion=None
):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "planillas:modificar-solicitud"
            )

            if repetida is not None:
                return repetida

            estado = _solicitud_editable(
                cursor,
                planilla_id,
                solicitud_id
            )

            cursor.execute("""
                SELECT id
                FROM productos
                WHERE id = %s
                  AND activo = TRUE;
            """, (producto_id,))

            if cursor.fetchone() is None:
                raise ValueError(
                    "El artículo seleccionado no está activo."
                )

            cursor.execute("""
                SELECT id
                FROM areas
                WHERE id = %s
                  AND activo = TRUE;
            """, (area_id,))

            if cursor.fetchone() is None:
                raise ValueError(
                    "El área seleccionada no está activa."
                )

            cursor.execute("""
                UPDATE solicitudes
                SET producto_id = %s,
                    area_id = %s,
                    cantidad = %s,
                    observaciones = %s
                WHERE id = %s;
            """, (
                producto_id,
                area_id,
                cantidad,
                observaciones,
                solicitud_id
            ))

            cursor.execute("""
                INSERT INTO historial_solicitudes (
                    solicitud_id,
                    estado,
                    fecha_hora,
                    observaciones,
                    usuario_id
                )
                VALUES (
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    'Solicitud modificada desde Planillas',
                    %s
                );
            """, (
                solicitud_id,
                estado,
                fecha_operacion,
                usuario_id
            ))

            offlinecloud.finalizar_operacion(
                cursor,
                operacion_id,
                True
            )

        conexion_db.commit()

        return True

    except Exception:
        conexion_db.rollback()
        raise

    finally:
        conexion_db.close()


def actualizar_estado_solicitud(
    planilla_id,
    solicitud_id,
    estado_nuevo,
    estado_anterior,
    usuario_id,
    operacion_id=None,
    fecha_operacion=None
):
    """
    Cambia únicamente el estado de una solicitud.

    Esta función está pensada especialmente para operaciones que pueden
    sincronizarse desde modo offline.

    estado_anterior representa el estado que tenía la solicitud en el
    dispositivo cuando el usuario realizó el cambio.

    Si Cloud ya tiene otro estado, NO se pisa el cambio y se informa
    un conflicto.
    """

    estado_nuevo = (estado_nuevo or "").strip().upper()
    estado_anterior = (estado_anterior or "").strip().upper()

    if estado_nuevo not in ESTADOS_SOLICITUD:
        raise ValueError(
            "El estado seleccionado no es válido."
        )

    if not estado_anterior:
        raise ValueError(
            "No se recibió el estado anterior de la solicitud."
        )

    if estado_anterior not in ESTADOS_SOLICITUD:
        raise ValueError(
            "El estado anterior de la solicitud no es válido."
        )

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "planillas:cambiar-estado"
            )

            if repetida is not None:
                return repetida

            cursor.execute("""
                SELECT s.estado
                FROM planilla_solicitudes AS ps
                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id
                WHERE ps.planilla_id = %s
                  AND s.id = %s
                FOR UPDATE OF s;
            """, (
                planilla_id,
                solicitud_id
            ))

            fila = cursor.fetchone()

            if fila is None:
                raise ValueError(
                    "No se encontró esa solicitud dentro de la planilla."
                )

            estado_actual = (
                fila[0] or "PENDIENTE DE COMPRA"
            ).strip().upper()

            # Esta es la comprobación fundamental del sistema offline.
            #
            # Si el estado que encontramos en Cloud ya no coincide con
            # el estado que tenía el usuario cuando hizo su operación,
            # no sobrescribimos nada.
            if estado_actual != estado_anterior:
                raise ConflictoSolicitud(
                    solicitud_id,
                    estado_anterior,
                    estado_actual
                )

            if estado_actual == "ENTREGADO":
                raise ValueError(
                    "La solicitud ya fue entregada y no se puede modificar."
                )

            if estado_actual == "CANCELADA":
                raise ValueError(
                    "La solicitud está cancelada y no se puede modificar."
                )

            cursor.execute("""
                UPDATE solicitudes
                SET estado = %s
                WHERE id = %s;
            """, (
                estado_nuevo,
                solicitud_id
            ))

            cursor.execute("""
                INSERT INTO historial_solicitudes (
                    solicitud_id,
                    estado,
                    fecha_hora,
                    observaciones,
                    usuario_id
                )
                VALUES (
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    'Estado modificado desde Planillas',
                    %s
                );
            """, (
                solicitud_id,
                estado_nuevo,
                fecha_operacion,
                usuario_id
            ))

            offlinecloud.finalizar_operacion(
                cursor,
                operacion_id,
                True
            )

        conexion_db.commit()

        return True

    except Exception:
        conexion_db.rollback()
        raise

    finally:
        conexion_db.close()


def cancelar_solicitud(
    planilla_id,
    solicitud_id,
    usuario_id,
    motivo,
    operacion_id=None,
    fecha_operacion=None
):
    motivo = (motivo or "").strip()

    if len(motivo) < 3:
        raise ValueError(
            "Escribí el motivo de la cancelación."
        )

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "planillas:cancelar-solicitud"
            )

            if repetida is not None:
                return repetida

            _solicitud_editable(
                cursor,
                planilla_id,
                solicitud_id
            )

            cursor.execute("""
                UPDATE solicitudes
                SET estado = 'CANCELADA'
                WHERE id = %s;
            """, (solicitud_id,))

            cursor.execute("""
                INSERT INTO historial_solicitudes (
                    solicitud_id,
                    estado,
                    fecha_hora,
                    observaciones,
                    usuario_id
                )
                VALUES (
                    %s,
                    'CANCELADA',
                    COALESCE(%s, NOW()),
                    %s,
                    %s
                );
            """, (
                solicitud_id,
                fecha_operacion,
                f"Cancelada desde Planillas: {motivo}",
                usuario_id
            ))

            offlinecloud.finalizar_operacion(
                cursor,
                operacion_id,
                True
            )

        conexion_db.commit()

        return True

    except Exception:
        conexion_db.rollback()
        raise

    finally:
        conexion_db.close()