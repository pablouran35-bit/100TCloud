import conexion


def obtener_proveedores(incluir_inactivos=False):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            if incluir_inactivos:
                cursor.execute("""
                    SELECT id, nombre, telefono, email, observaciones,
                           activo, contacto, whatsapp
                    FROM proveedores
                    ORDER BY nombre, id;
                """)
            else:
                cursor.execute("""
                    SELECT id, nombre, telefono, email, observaciones,
                           activo, contacto, whatsapp
                    FROM proveedores
                    WHERE activo = TRUE
                    ORDER BY nombre, id;
                """)

            return cursor.fetchall()
    finally:
        conexion_db.close()


def crear_proveedor(nombre, telefono=None, email=None, observaciones=None,
                    contacto=None, whatsapp=None):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO proveedores
                    (nombre, telefono, email, observaciones, contacto, whatsapp)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (nombre, telefono, email, observaciones, contacto, whatsapp))
            proveedor_id = cursor.fetchone()[0]

        conexion_db.commit()
        return proveedor_id
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def actualizar_proveedor(proveedor_id, nombre, telefono=None, email=None,
                         observaciones=None, contacto=None, whatsapp=None):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE proveedores
                SET nombre = %s,
                    telefono = %s,
                    email = %s,
                    observaciones = %s,
                    contacto = %s,
                    whatsapp = %s
                WHERE id = %s;
            """, (nombre, telefono, email, observaciones, contacto, whatsapp,
                  proveedor_id))
            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()


def cambiar_estado_proveedor(proveedor_id, activo):
    conexion_db = conexion.conectar()

    try:
        with conexion_db.cursor() as cursor:
            cursor.execute("""
                UPDATE proveedores
                SET activo = %s
                WHERE id = %s;
            """, (activo, proveedor_id))
            filas_modificadas = cursor.rowcount

        conexion_db.commit()
        return filas_modificadas
    except Exception:
        conexion_db.rollback()
        raise
    finally:
        conexion_db.close()
