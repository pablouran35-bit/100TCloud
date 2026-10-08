from datetime import date, datetime, timedelta, timezone

import conexion
import offlinecloud


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
)

ESTADOS_TAREA_ABIERTOS = ("PENDIENTE", "EN PROCESO")

ESTADOS_TAREA = (
    "PENDIENTE",
    "EN PROCESO",
    "FINALIZADA",
    "CANCELADA",
)

ZONA_ARGENTINA = timezone(timedelta(hours=-3))


class ConflictoSolicitudCompra(Exception):
    """
    Indica que una solicitud fue modificada en Cloud
    después de que el dispositivo guardó su cambio offline.

    En este caso NO se debe sobrescribir el estado actual
    de Cloud automáticamente.
    """

    def __init__(
        self,
        solicitud_id,
        estado_anterior,
        estado_cloud,
    ):
        self.solicitud_id = solicitud_id
        self.estado_anterior = estado_anterior
        self.estado_cloud = estado_cloud

        super().__init__(
            "La solicitud de compra cambió mientras "
            "el dispositivo estaba sin conexión."
        )


def _fecha_texto(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()

    if isinstance(valor, date):
        return valor.isoformat()

    return str(valor or "")


def _fecha_hora_texto(valor):
    if isinstance(valor, datetime):
        return valor.astimezone(
            ZONA_ARGENTINA
        ).strftime("%d/%m/%Y %H:%M")

    return str(valor or "")


# ==========================================================
# DÍA DE COMPRAS
# ==========================================================

def fecha_dia_compras(hoy=None):
    """
    Determina cuál es el martes correspondiente al Día de Compras.

    Si hoy es martes:
        devuelve hoy.

    Si hoy es miércoles, jueves, viernes, sábado, domingo
    o lunes:
        devuelve el próximo martes.
    """

    if hoy is None:
        hoy = datetime.now(ZONA_ARGENTINA).date()

    dias_hasta_martes = (1 - hoy.weekday()) % 7

    return hoy + timedelta(days=dias_hasta_martes)


def martes_correspondiente(fecha_planilla):
    """
    Convierte la fecha almacenada en una planilla al martes
    de compra que le corresponde.

    La PC puede guardar la fecha en que se creó la planilla,
    mientras que Cloud puede guardar directamente la fecha
    del próximo martes.
    """

    if fecha_planilla is None:
        return None

    if isinstance(fecha_planilla, datetime):
        fecha_planilla = fecha_planilla.date()

    dias_hasta_martes = (
        1 - fecha_planilla.weekday()
    ) % 7

    return fecha_planilla + timedelta(
        days=dias_hasta_martes
    )


def listar_solicitudes_dia_compras():
    """
    Devuelve las solicitudes que deben formar parte
    del Día de Compras.

    REGLAS:

    1. Solicitudes de planillas anteriores al Día de Compras:
       solamente aparecen si todavía están pendientes.

    2. Solicitudes de planillas correspondientes al
       Día de Compras:
       aparecen todas, sin importar su estado.

    3. Solicitudes cuya última modificación de estado
       ocurrió durante el Día de Compras:
       también aparecen.

    4. Las solicitudes CANCELADAS no aparecen.

    5. Para solicitudes de fechas anteriores, los estados
       considerados finalizados son:

        COMPRADO Y RETIRADO
        ENTREGADO
        CANCELADA
    """

    fecha_objetivo = fecha_dia_compras()

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            cursor.execute("""
                WITH ultima_modificacion AS (
                    SELECT
                        hs.solicitud_id,
                        MAX(hs.fecha_hora) AS ultima_fecha
                    FROM historial_solicitudes AS hs
                    GROUP BY hs.solicitud_id
                )

                SELECT
                    s.id,
                    ps.planilla_id,
                    s.cantidad,
                    pr.nombre,
                    o.nombre,
                    s.estado,
                    p.fecha_compra,
                    um.ultima_fecha

                FROM planilla_solicitudes AS ps

                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id

                JOIN planillas AS p
                    ON p.id = ps.planilla_id

                JOIN obras AS o
                    ON o.id = p.obra_id

                JOIN productos AS pr
                    ON pr.id = s.producto_id

                LEFT JOIN ultima_modificacion AS um
                    ON um.solicitud_id = s.id

                WHERE

                    UPPER(
                        COALESCE(s.estado, '')
                    ) <> 'CANCELADA'

                    AND

                    (

                        -- ==================================
                        -- 1. SOLICITUDES DEL DÍA DE COMPRAS
                        -- ==================================
                        (
                            p.fecha_compra::date = %s
                        )

                        OR

                        -- ==================================
                        -- 2. SOLICITUDES ANTERIORES
                        --    QUE SIGUEN PENDIENTES
                        -- ==================================
                        (
                            p.fecha_compra::date < %s

                            AND

                            UPPER(
                                COALESCE(s.estado, '')
                            ) NOT IN (
                                'COMPRADO Y RETIRADO',
                                'ENTREGADO',
                                'CANCELADA'
                            )
                        )

                        OR

                        -- ==================================
                        -- 3. SOLICITUDES MODIFICADAS
                        --    EL MISMO DÍA DE COMPRAS
                        -- ==================================
                        (
                            um.ultima_fecha IS NOT NULL

                            AND

                            (
                                um.ultima_fecha
                                AT TIME ZONE 'America/Argentina/Buenos_Aires'
                            )::date = %s
                        )
                    )

                ORDER BY
                    o.nombre,
                    pr.nombre,
                    s.id;
            """, (
                fecha_objetivo,
                fecha_objetivo,
                fecha_objetivo,
            ))

            solicitudes = [
                {
                    "id": fila[0],
                    "planilla_id": fila[1],
                    "cantidad": fila[2],
                    "producto": fila[3],
                    "obra": fila[4],
                    "estado": fila[5] or "",
                    "fecha_planilla": _fecha_texto(
                        fila[6]
                    ),
                    "ultima_modificacion":
                        _fecha_hora_texto(
                            fila[7]
                        ),
                }
                for fila in cursor.fetchall()
            ]

            return {
                "fecha_compra":
                    fecha_objetivo.isoformat(),

                "solicitudes":
                    solicitudes,
            }

    finally:
        conexion_db.close()


# ==========================================================
# PROVEEDORES
# ==========================================================

def obtener_proveedores_activos():
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre
                FROM proveedores
                WHERE activo = TRUE
                ORDER BY nombre, id;
            """)

            return [
                {
                    "id": fila[0],
                    "nombre": fila[1]
                }
                for fila in cursor.fetchall()
            ]

    finally:
        conexion_db.close()


# ==========================================================
# PLANILLAS DE COMPRA
# ==========================================================

def listar_planillas_compra():
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.id,
                    o.nombre,
                    p.fecha_compra,
                    COUNT(s.id)
                FROM planillas AS p

                JOIN obras AS o
                    ON o.id = p.obra_id

                JOIN planilla_solicitudes AS ps
                    ON ps.planilla_id = p.id

                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id

                WHERE UPPER(
                    COALESCE(s.estado, '')
                ) NOT IN (
                    'COMPRADO Y RETIRADO',
                    'ENTREGADO',
                    'CANCELADA'
                )

                GROUP BY
                    p.id,
                    o.nombre,
                    p.fecha_compra

                ORDER BY p.id DESC;
            """)

            return [
                {
                    "id": fila[0],
                    "obra": fila[1],
                    "fecha_compra": _fecha_texto(
                        fila[2]
                    ),
                    "solicitudes": fila[3]
                }
                for fila in cursor.fetchall()
            ]

    finally:
        conexion_db.close()


def obtener_planilla_compra(planilla_id):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.id,
                    o.nombre,
                    p.fecha_compra
                FROM planillas AS p

                JOIN obras AS o
                    ON o.id = p.obra_id

                WHERE p.id = %s;
            """, (planilla_id,))

            planilla = cursor.fetchone()

            if planilla is None:
                return None

            cursor.execute("""
                SELECT
                    s.id,
                    s.cantidad,
                    pr.nombre,
                    s.estado,
                    s.proveedor_id,
                    pv.nombre,
                    s.observaciones
                FROM planilla_solicitudes AS ps

                JOIN solicitudes AS s
                    ON s.id = ps.solicitud_id

                JOIN productos AS pr
                    ON pr.id = s.producto_id

                LEFT JOIN proveedores AS pv
                    ON pv.id = s.proveedor_id

                WHERE ps.planilla_id = %s

                  AND UPPER(
                      COALESCE(s.estado, '')
                  ) NOT IN (
                      'COMPRADO Y RETIRADO',
                      'ENTREGADO',
                      'CANCELADA'
                  )

                ORDER BY s.id;
            """, (planilla_id,))

            solicitudes = cursor.fetchall()

            ids = [
                fila[0]
                for fila in solicitudes
            ]

            historiales = {
                solicitud_id: []
                for solicitud_id in ids
            }

            if ids:
                cursor.execute("""
                    SELECT
                        hs.solicitud_id,
                        hs.fecha_hora,
                        hs.estado,
                        COALESCE(
                            NULLIF(
                                TRIM(
                                    p.nombre || ' ' || p.apellido
                                ),
                                ''
                            ),
                            u.usuario,
                            'Usuario no disponible'
                        ),
                        hs.observaciones
                    FROM historial_solicitudes AS hs

                    LEFT JOIN usuarios AS u
                        ON u.id = hs.usuario_id

                    LEFT JOIN personas AS p
                        ON p.id = u.persona_id

                    WHERE hs.solicitud_id = ANY(%s)

                    ORDER BY hs.id;
                """, (ids,))

                for registro in cursor.fetchall():
                    historiales[
                        registro[0]
                    ].append({
                        "fecha_hora":
                            _fecha_hora_texto(
                                registro[1]
                            ),
                        "estado":
                            registro[2],
                        "usuario":
                            registro[3],
                        "observaciones":
                            registro[4] or "",
                    })

            return {
                "id": planilla[0],
                "obra": planilla[1],
                "fecha_compra":
                    _fecha_texto(planilla[2]),
                "solicitudes": [
                    {
                        "id": fila[0],
                        "cantidad": fila[1],
                        "producto": fila[2],
                        "estado": fila[3],
                        "proveedor_id": fila[4],
                        "proveedor": fila[5] or "",
                        "observaciones":
                            fila[6] or "",
                        "historial":
                            historiales[fila[0]],
                    }
                    for fila in solicitudes
                ],
            }

    finally:
        conexion_db.close()


# ==========================================================
# ACTUALIZAR SOLICITUD ONLINE
# ==========================================================

def actualizar_solicitud_compra(
    planilla_id,
    solicitud_id,
    estado,
    proveedor_id,
    observaciones,
    usuario_id,
    operacion_id=None,
    fecha_operacion=None
):
    """
    Gestión NORMAL/ONLINE de una solicitud de compra.

    Puede modificar:
    - estado
    - proveedor
    - observaciones

    Esta función se mantiene para el funcionamiento online.
    Los cambios offline de estado utilizan
    actualizar_estado_solicitud_compra().
    """

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "compras:solicitud"
            )

            if repetida is not None:
                return repetida

            cursor.execute("""
                SELECT s.estado
                FROM solicitudes AS s

                JOIN planilla_solicitudes AS ps
                    ON ps.solicitud_id = s.id

                WHERE ps.planilla_id = %s
                  AND s.id = %s

                FOR UPDATE OF s;
            """, (
                planilla_id,
                solicitud_id
            ))

            fila = cursor.fetchone()

            if fila is None:
                return False

            if (
                fila[0] or ""
            ).upper() == "CANCELADA":
                raise ValueError(
                    "La solicitud está cancelada "
                    "y no se puede gestionar."
                )

            if proveedor_id is not None:
                cursor.execute("""
                    SELECT id
                    FROM proveedores
                    WHERE id = %s
                      AND activo = TRUE;
                """, (proveedor_id,))

                if cursor.fetchone() is None:
                    raise ValueError(
                        "El proveedor seleccionado "
                        "no está activo."
                    )

            cursor.execute("""
                UPDATE solicitudes
                SET estado = %s,
                    proveedor_id = %s,
                    observaciones = %s
                WHERE id = %s;
            """, (
                estado,
                proveedor_id,
                observaciones,
                solicitud_id
            ))

            cursor.execute("""
                INSERT INTO historial_solicitudes
                    (
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
                    %s,
                    %s
                );
            """, (
                solicitud_id,
                estado,
                fecha_operacion,
                observaciones,
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


# ==========================================================
# ACTUALIZAR ESTADO OFFLINE
# ==========================================================

def actualizar_estado_solicitud_compra(
    planilla_id,
    solicitud_id,
    estado_nuevo,
    estado_anterior,
    usuario_id,
    operacion_id=None,
    fecha_operacion=None
):
    """
    Cambia SOLAMENTE el estado de una solicitud.

    Esta función está pensada especialmente para operaciones
    realizadas sin conexión.

    El dispositivo informa:
        estado_anterior = estado que tenía cuando se desconectó
        estado_nuevo    = estado elegido sin conexión

    Cloud compara estado_anterior con el estado actual.

    Si coinciden:
        aplica el cambio.

    Si no coinciden:
        genera ConflictoSolicitudCompra y NO modifica nada.
    """

    estado_nuevo = (
        estado_nuevo or ""
    ).strip().upper()

    estado_anterior = (
        estado_anterior or ""
    ).strip().upper()

    if estado_nuevo not in ESTADOS_SOLICITUD:
        raise ValueError(
            "El estado seleccionado no es válido."
        )

    if not estado_anterior:
        raise ValueError(
            "No se recibió el estado anterior "
            "de la solicitud."
        )

    if estado_anterior not in ESTADOS_SOLICITUD:
        raise ValueError(
            "El estado anterior de la solicitud "
            "no es válido."
        )

    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:

            repetida = offlinecloud.iniciar_operacion(
                cursor,
                operacion_id,
                usuario_id,
                "compras:cambiar-estado"
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
                    "No se encontró esa solicitud "
                    "dentro de la planilla."
                )

            estado_cloud = (
                fila[0] or "PENDIENTE DE COMPRA"
            ).strip().upper()

            # --------------------------------------------------
            # DETECCIÓN DE CONFLICTO
            # --------------------------------------------------

            if estado_cloud != estado_anterior:
                raise ConflictoSolicitudCompra(
                    solicitud_id,
                    estado_anterior,
                    estado_cloud
                )

            if estado_cloud == "ENTREGADO":
                raise ValueError(
                    "La solicitud ya fue entregada "
                    "y no se puede modificar."
                )

            if estado_cloud == "CANCELADA":
                raise ValueError(
                    "La solicitud está cancelada "
                    "y no se puede modificar."
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
                    'Estado modificado desde Compras',
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


# ==========================================================
# TAREAS
# ==========================================================

def listar_tareas_compra():
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.id,
                    t.descripcion,
                    t.fecha_solicitud,
                    t.estado,
                    t.observaciones,
                    p.nombre,
                    p.apellido
                FROM tareas AS t

                LEFT JOIN personas AS p
                    ON p.id = t.solicitante_id

                WHERE UPPER(t.estado)
                    IN ('PENDIENTE', 'EN PROCESO')

                ORDER BY t.id DESC;
            """)

            return [
                {
                    "id": fila[0],
                    "descripcion": fila[1],
                    "fecha_solicitud":
                        _fecha_texto(fila[2]),
                    "estado": fila[3],
                    "observaciones":
                        fila[4] or "",
                    "solicitante":
                        f"{fila[5] or ''} "
                        f"{fila[6] or ''}".strip(),
                }
                for fila in cursor.fetchall()
            ]

    finally:
        conexion_db.close()


def obtener_tarea_compra(tarea_id):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.id,
                    t.descripcion,
                    t.fecha_solicitud,
                    t.estado,
                    t.observaciones,
                    p.nombre,
                    p.apellido
                FROM tareas AS t

                LEFT JOIN personas AS p
                    ON p.id = t.solicitante_id

                WHERE t.id = %s
                  AND UPPER(t.estado)
                      IN ('PENDIENTE', 'EN PROCESO');
            """, (tarea_id,))

            fila = cursor.fetchone()

            if fila is None:
                return None

            cursor.execute("""
                SELECT
                    ht.fecha_hora,
                    ht.estado,
                    COALESCE(
                        NULLIF(
                            TRIM(
                                p.nombre || ' ' || p.apellido
                            ),
                            ''
                        ),
                        u.usuario,
                        'Usuario no disponible'
                    ),
                    ht.observaciones
                FROM historial_tareas AS ht

                LEFT JOIN usuarios AS u
                    ON u.id = ht.usuario_id

                LEFT JOIN personas AS p
                    ON p.id = u.persona_id

                WHERE ht.tarea_id = %s

                ORDER BY ht.id;
            """, (tarea_id,))

            historial = [
                {
                    "fecha_hora":
                        _fecha_hora_texto(r[0]),
                    "estado":
                        r[1],
                    "usuario":
                        r[2],
                    "observaciones":
                        r[3] or "",
                }
                for r in cursor.fetchall()
            ]

            return {
                "id": fila[0],
                "descripcion": fila[1],
                "fecha_solicitud":
                    _fecha_texto(fila[2]),
                "estado": fila[3],
                "observaciones":
                    fila[4] or "",
                "solicitante":
                    f"{fila[5] or ''} "
                    f"{fila[6] or ''}".strip(),
                "historial":
                    historial,
            }

    finally:
        conexion_db.close()


def actualizar_tarea_compra(
    tarea_id,
    estado,
    observaciones,
    usuario_id,
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
                "compras:tarea"
            )

            if repetida is not None:
                return repetida

            cursor.execute("""
                UPDATE tareas
                SET estado = %s,
                    observaciones = %s
                WHERE id = %s
                  AND UPPER(estado)
                      IN ('PENDIENTE', 'EN PROCESO');
            """, (
                estado,
                observaciones,
                tarea_id
            ))

            if cursor.rowcount == 0:
                return False

            cursor.execute("""
                INSERT INTO historial_tareas
                    (
                        tarea_id,
                        estado,
                        fecha_hora,
                        observaciones,
                        usuario_id
                    )
                VALUES (
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    %s,
                    %s
                );
            """, (
                tarea_id,
                estado,
                fecha_operacion,
                observaciones,
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