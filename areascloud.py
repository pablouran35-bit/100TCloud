import conexion


def obtener_areas():
    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        SELECT id, nombre
        FROM areas
        WHERE activo = TRUE
        ORDER BY id;
    """)

    areas = cursor.fetchall()

    cursor.close()
    conexion_db.close()

    return areas


def obtener_areas_administracion():
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre, activo
                FROM areas
                ORDER BY nombre;
            """)

            return cursor.fetchall()
    finally:
        conexion_db.close()


def crear_area(nombre):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO areas (nombre, activo)
                VALUES (%s, TRUE)
                RETURNING id;
            """, (nombre,))

            area_id = cursor.fetchone()[0]

        conexion_db.commit()
        return area_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_area(area_id, nombre):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE areas
                SET nombre = %s
                WHERE id = %s;
            """, (nombre, area_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def cambiar_estado_area(area_id, activo):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE areas
                SET activo = %s
                WHERE id = %s;
            """, (activo, area_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()
