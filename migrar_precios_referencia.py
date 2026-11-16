import conexion
from precios_referencia import migrar

if __name__ == '__main__':
    migrar(conexion.conectar)
    print('Precios de referencia: esquema listo. No se modificaron compras ni precios existentes.')
