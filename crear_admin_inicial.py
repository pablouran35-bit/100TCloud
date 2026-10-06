from getpass import getpass

import conexion
from seguridad import crear_hash_contrasena


nombre = input("Nombre para mostrar en la app: ").strip()
apellido = input("Apellido para mostrar en la app: ").strip()

if not nombre or not apellido:
    print("El nombre y el apellido no pueden quedar vacíos.")
    raise SystemExit

contrasena = getpass(
    "Contraseña inicial para admin (escribí 1234): "
)
confirmacion = getpass("Volvé a escribir la contraseña: ")

if contrasena != confirmacion:
    print("Las contraseñas no coinciden. No se creó la cuenta.")
    raise SystemExit

hash_contrasena = crear_hash_contrasena(contrasena)

conexion_db = conexion.conectar()

try:
    with conexion_db.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM usuarios WHERE usuario = %s",
            ("admin",)
        )

        if cursor.fetchone() is not None:
            print("Ya existe el usuario admin. No se hicieron cambios.")
            raise SystemExit

        cursor.execute(
            """
            INSERT INTO personas (nombre, apellido, activo)
            VALUES (%s, %s, TRUE)
            RETURNING id
            """,
            (nombre, apellido)
        )
        persona_id = cursor.fetchone()[0]

        cursor.execute(
            "SELECT id FROM roles WHERE nombre = %s",
            ("ADMINISTRADOR",)
        )
        rol = cursor.fetchone()

        if rol is None:
            cursor.execute(
                """
                INSERT INTO roles (nombre)
                VALUES (%s)
                RETURNING id
                """,
                ("ADMINISTRADOR",)
            )
            rol_id = cursor.fetchone()[0]
        else:
            rol_id = rol[0]

        cursor.execute(
            """
            INSERT INTO usuarios (
                usuario,
                persona_id,
                contrasena_hash
            )
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("admin", persona_id, hash_contrasena)
        )
        usuario_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO usuario_rol (usuario_id, rol_id)
            VALUES (%s, %s)
            """,
            (usuario_id, rol_id)
        )

    conexion_db.commit()
    print("Cuenta admin creada correctamente.")

except SystemExit:
    conexion_db.rollback()
    raise

except Exception:
    conexion_db.rollback()
    raise

finally:
    conexion_db.close()