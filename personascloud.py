import conexion


# ==========================================================
# CREAR PERSONA
# ==========================================================

def crear_persona(nombre, apellido, telefono=None, email=None):

    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        INSERT INTO personas (
            nombre,
            apellido,
            telefono,
            email
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """, (
        nombre,
        apellido,
        telefono,
        email
    ))

    persona_id = cursor.fetchone()[0]

    conexion_db.commit()

    cursor.close()
    conexion_db.close()

    return persona_id


# ==========================================================
# OBTENER PERSONAS
# ==========================================================

def obtener_personas():

    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        SELECT
            id,
            nombre,
            apellido,
            telefono,
            email,
            activo
        FROM personas
        ORDER BY apellido, nombre;
    """)

    personas = cursor.fetchall()

    cursor.close()
    conexion_db.close()

    return personas


# ==========================================================
# OBTENER UNA PERSONA
# ==========================================================

def obtener_persona(persona_id):

    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        SELECT
            id,
            nombre,
            apellido,
            telefono,
            email,
            activo
        FROM personas
        WHERE id = %s;
    """, (persona_id,))

    persona = cursor.fetchone()

    cursor.close()
    conexion_db.close()

    return persona


# ==========================================================
# ACTUALIZAR PERSONA
# ==========================================================

def actualizar_persona(
    persona_id,
    nombre,
    apellido,
    telefono=None,
    email=None
):

    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        UPDATE personas
        SET
            nombre = %s,
            apellido = %s,
            telefono = %s,
            email = %s
        WHERE id = %s;
    """, (
        nombre,
        apellido,
        telefono,
        email,
        persona_id
    ))

    filas_modificadas = cursor.rowcount

    conexion_db.commit()

    cursor.close()
    conexion_db.close()

    return filas_modificadas


# ==========================================================
# DESACTIVAR PERSONA
# ==========================================================

def desactivar_persona(persona_id):

    conexion_db = conexion.conectar()
    cursor = conexion_db.cursor()

    cursor.execute("""
        UPDATE personas
        SET activo = FALSE
        WHERE id = %s;
    """, (persona_id,))

    filas_modificadas = cursor.rowcount

    conexion_db.commit()

    cursor.close()
    conexion_db.close()

    return filas_modificadas