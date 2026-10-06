import conexion


def obtener_obras(incluir_inactivas=False):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            if incluir_inactivas:
                cursor.execute("""
                    SELECT o.id, o.nombre, o.direccion, o.activo, o.observaciones,
                           COALESCE((
                               SELECT string_agg(c.nombre, ', ' ORDER BY c.nombre)
                               FROM (
                                   SELECT DISTINCT concat_ws(' ', p.nombre, p.apellido) AS nombre
                                   FROM persona_obra AS po
                                   JOIN personas AS p ON p.id = po.persona_id
                                   JOIN usuarios AS u ON u.persona_id = p.id
                                   JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                                   JOIN roles AS r ON r.id = ur.rol_id
                                   WHERE po.obra_id = o.id
                                     AND UPPER(r.nombre) = 'CONTRATISTA'
                               ) AS c
                           ), '') AS contratistas
                    FROM obras AS o
                    ORDER BY o.nombre;
                """)
            else:
                cursor.execute("""
                    SELECT o.id, o.nombre, o.direccion, o.activo, o.observaciones,
                           COALESCE((
                               SELECT string_agg(c.nombre, ', ' ORDER BY c.nombre)
                               FROM (
                                   SELECT DISTINCT concat_ws(' ', p.nombre, p.apellido) AS nombre
                                   FROM persona_obra AS po
                                   JOIN personas AS p ON p.id = po.persona_id
                                   JOIN usuarios AS u ON u.persona_id = p.id
                                   JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                                   JOIN roles AS r ON r.id = ur.rol_id
                                   WHERE po.obra_id = o.id
                                     AND UPPER(r.nombre) = 'CONTRATISTA'
                               ) AS c
                           ), '') AS contratistas
                    FROM obras AS o
                    WHERE o.activo = TRUE
                    ORDER BY o.nombre;
                """)

            return cursor.fetchall()
    finally:
        conexion_db.close()


def crear_obra(nombre, direccion=None, observaciones=None):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO obras (nombre, direccion, observaciones)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (nombre, direccion, observaciones))

            obra_id = cursor.fetchone()[0]

        conexion_db.commit()
        return obra_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_obra(obra_id, nombre, direccion=None, observaciones=None):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE obras
                SET nombre = %s,
                    direccion = %s,
                    observaciones = %s
                WHERE id = %s;
            """, (nombre, direccion, observaciones, obra_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def cambiar_estado_obra(obra_id, activo):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE obras
                SET activo = %s
                WHERE id = %s;
            """, (activo, obra_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def obtener_contratistas_obra(obra_id):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("SELECT id FROM obras WHERE id = %s;", (obra_id,))
            if cursor.fetchone() is None:
                return None
            cursor.execute("""
                SELECT p.id, p.nombre, p.apellido, u.usuario, p.activo,
                       EXISTS (
                           SELECT 1 FROM persona_obra AS po
                           WHERE po.persona_id = p.id AND po.obra_id = %s
                       ) AS asignado
                FROM personas AS p
                JOIN usuarios AS u ON u.persona_id = p.id
                JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                JOIN roles AS r ON r.id = ur.rol_id
                WHERE UPPER(r.nombre) = 'CONTRATISTA'
                  AND (p.activo = TRUE OR EXISTS (
                      SELECT 1 FROM persona_obra AS po
                      WHERE po.persona_id = p.id AND po.obra_id = %s
                  ))
                ORDER BY p.apellido, p.nombre, u.usuario;
            """, (obra_id, obra_id))
            return cursor.fetchall()
    finally:
        conexion_db.close()


def guardar_contratistas_obra(obra_id, persona_ids):
    ids = sorted(set(persona_ids))
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("SELECT id FROM obras WHERE id = %s FOR UPDATE;", (obra_id,))
            if cursor.fetchone() is None:
                return False
            if ids:
                cursor.execute("""
                    SELECT DISTINCT p.id
                    FROM personas AS p
                    JOIN usuarios AS u ON u.persona_id = p.id
                    JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                    JOIN roles AS r ON r.id = ur.rol_id
                    WHERE UPPER(r.nombre) = 'CONTRATISTA'
                      AND p.id = ANY(%s)
                      AND (p.activo = TRUE OR EXISTS (
                          SELECT 1 FROM persona_obra AS po
                          WHERE po.persona_id = p.id AND po.obra_id = %s
                      ));
                """, (ids, obra_id))
                validos = {fila[0] for fila in cursor.fetchall()}
                if validos != set(ids):
                    raise ValueError("Elegí únicamente contratistas activos con usuario.")
            cursor.execute("DELETE FROM persona_obra WHERE obra_id = %s;", (obra_id,))
            for persona_id in ids:
                cursor.execute("""
                    INSERT INTO persona_obra (persona_id, obra_id)
                    VALUES (%s, %s);
                """, (persona_id, obra_id))
        conexion_db.commit()
        return True
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()
