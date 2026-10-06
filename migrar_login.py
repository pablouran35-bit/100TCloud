import conexion


conexion_db = conexion.conectar()
cursor = conexion_db.cursor()

try:
    cursor.execute("""
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS contrasena_hash TEXT;
    """)

    conexion_db.commit()
    print("Columna de contraseña creada correctamente.")

except Exception:
    conexion_db.rollback()
    raise

finally:
    cursor.close()
    conexion_db.close()