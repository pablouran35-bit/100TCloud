from pwdlib import PasswordHash


gestor_contrasenas = PasswordHash.recommended()


def crear_hash_contrasena(contrasena: str) -> str:
    return gestor_contrasenas.hash(contrasena)


def verificar_contrasena(
    contrasena: str,
    hash_guardado: str | None
) -> bool:
    if not hash_guardado:
        return False

    return gestor_contrasenas.verify(
        contrasena,
        hash_guardado
    )