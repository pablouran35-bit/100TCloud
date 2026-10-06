import conexion


def obtener_productos(incluir_inactivos=False):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            if incluir_inactivos:
                cursor.execute("""
                    SELECT id, nombre, unidad, activo, observaciones
                    FROM productos
                    ORDER BY nombre;
                """)
            else:
                cursor.execute("""
                    SELECT id, nombre, unidad, activo, observaciones
                    FROM productos
                    WHERE activo = TRUE
                    ORDER BY nombre;
                """)

            return cursor.fetchall()
    finally:
        conexion_db.close()


def crear_producto(nombre, unidad, observaciones=None):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO productos (nombre, unidad, observaciones)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (nombre, unidad, observaciones))

            producto_id = cursor.fetchone()[0]

        conexion_db.commit()
        return producto_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_producto(
    producto_id,
    nombre,
    unidad,
    observaciones=None
):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE productos
                SET nombre = %s,
                    unidad = %s,
                    observaciones = %s
                WHERE id = %s;
            """, (nombre, unidad, observaciones, producto_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def cambiar_estado_producto(producto_id, activo):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE productos
                SET activo = %s
                WHERE id = %s;
            """, (activo, producto_id))

            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()