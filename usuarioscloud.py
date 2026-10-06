import conexion


def obtener_usuarios():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT u.id, u.usuario, p.id, p.nombre, p.apellido,
                       p.telefono, p.email, p.activo,
                       COALESCE(
                           array_agg(r.nombre ORDER BY r.nombre)
                               FILTER (WHERE r.id IS NOT NULL),
                           ARRAY[]::TEXT[]
                       ) AS roles
                FROM usuarios AS u
                JOIN personas AS p ON p.id = u.persona_id
                LEFT JOIN usuario_rol AS ur ON ur.usuario_id = u.id
                LEFT JOIN roles AS r ON r.id = ur.rol_id
                GROUP BY u.id, u.usuario, p.id, p.nombre, p.apellido,
                         p.telefono, p.email, p.activo
                ORDER BY p.apellido, p.nombre, u.usuario;
            """)
            return cursor.fetchall()
    finally:
        conexion_db.close()


def obtener_roles():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM roles ORDER BY nombre;")
            return cursor.fetchall()
    finally:
        conexion_db.close()


def obtener_personas_sin_usuario():
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.nombre, p.apellido, p.telefono, p.email
                FROM personas AS p
                WHERE p.activo = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM usuarios AS u WHERE u.persona_id = p.id
                  )
                ORDER BY p.apellido, p.nombre;
            """)
            return cursor.fetchall()
    finally:
        conexion_db.close()


def _asignar_roles(cursor, usuario_id, rol_ids):
    cursor.execute("SELECT id FROM roles WHERE id = ANY(%s);", (rol_ids,))
    if len(cursor.fetchall()) != len(set(rol_ids)):
        raise ValueError("Uno o más roles seleccionados no existen.")

    cursor.execute("DELETE FROM usuario_rol WHERE usuario_id = %s;", (usuario_id,))
    for rol_id in set(rol_ids):
        cursor.execute("""
            INSERT INTO usuario_rol (usuario_id, rol_id)
            VALUES (%s, %s);
        """, (usuario_id, rol_id))


def crear_usuario(usuario, contrasena_hash, rol_ids, persona_id=None,
                  nombre=None, apellido=None, telefono=None, email=None):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            if persona_id is None:
                cursor.execute("""
                    INSERT INTO personas (nombre, apellido, telefono, email, activo)
                    VALUES (%s, %s, %s, %s, TRUE)
                    RETURNING id;
                """, (nombre, apellido, telefono, email))
                persona_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    SELECT id FROM personas WHERE id = %s AND activo = TRUE;
                """, (persona_id,))
                if cursor.fetchone() is None:
                    raise ValueError("La persona seleccionada no está disponible.")
                cursor.execute("""
                    SELECT 1 FROM usuarios WHERE persona_id = %s;
                """, (persona_id,))
                if cursor.fetchone() is not None:
                    raise ValueError("Esa persona ya tiene una cuenta de usuario.")

            cursor.execute("""
                INSERT INTO usuarios (usuario, persona_id, contrasena_hash)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (usuario, persona_id, contrasena_hash))
            usuario_id = cursor.fetchone()[0]
            _asignar_roles(cursor, usuario_id, rol_ids)

        conexion_db.commit()
        return usuario_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_usuario(usuario_id, nombre, apellido, telefono, email, rol_ids):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE personas AS p
                SET nombre = %s, apellido = %s, telefono = %s, email = %s
                FROM usuarios AS u
                WHERE u.id = %s AND p.id = u.persona_id;
            """, (nombre, apellido, telefono, email, usuario_id))
            if cursor.rowcount == 0:
                return 0
            _asignar_roles(cursor, usuario_id, rol_ids)

        conexion_db.commit()
        return 1
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def cambiar_estado_usuario(usuario_id, activo):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE personas AS p
                SET activo = %s
                FROM usuarios AS u
                WHERE u.id = %s AND p.id = u.persona_id;
            """, (activo, usuario_id))
            filas = cursor.rowcount
        conexion_db.commit()
        return filas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_contrasena(usuario_id, contrasena_hash):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE usuarios
                SET contrasena_hash = %s
                WHERE id = %s;
            """, (contrasena_hash, usuario_id))
            filas = cursor.rowcount
        conexion_db.commit()
        return filas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def obtener_hash_contrasena(usuario_id):
    conexion_db = conexion.conectar()
    try:
        with conexion_db.cursor() as cursor:
            cursor.execute(
                "SELECT contrasena_hash FROM usuarios WHERE id = %s;",
                (usuario_id,)
            )
            fila = cursor.fetchone()
            return fila[0] if fila else None
    finally:
        conexion_db.close()
