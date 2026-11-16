"""Precios orientativos compartidos. No registra pagos ni modifica compras."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MIGRACION = """
CREATE TABLE IF NOT EXISTS precios_referencia_productos (
    producto_id bigint PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
    precio_unitario numeric(16,2) NOT NULL CHECK (precio_unitario >= 0),
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
ESTADOS_PENDIENTES = (
    'PENDIENTE DE COMPRA', 'SOLICITADO', 'PENDIENTE', 'ENCARGADO', 'NO DISPONIBLE'
)


def normalizar_precio(valor):
    if valor is None or str(valor).strip() == '':
        return None
    texto = str(valor).strip()
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        numero = Decimal(texto)
        if not numero.is_finite() or numero < 0 or numero > Decimal('99999999999999.99'):
            raise ValueError
        if numero != numero.quantize(Decimal('0.01')):
            raise ValueError
        return numero.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise ValueError('Ingresá un precio válido, no negativo y con hasta dos decimales.') from None


def moneda(valor):
    if valor is None:
        return 'Sin precio'
    return '$ ' + f'{Decimal(str(valor)):,.2f}'.translate(str.maketrans(',.', '.,'))


def migrar(conectar):
    db = conectar()
    try:
        cur = db.cursor()
        cur.execute(MIGRACION)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def listar_articulos(conectar):
    db = conectar()
    try:
        cur = db.cursor()
        cur.execute('''SELECT p.id, p.nombre, p.unidad, p.activo, r.precio_unitario
                       FROM productos p LEFT JOIN precios_referencia_productos r
                         ON r.producto_id = p.id ORDER BY p.nombre, p.id''')
        return [dict(zip(('id', 'nombre', 'unidad', 'activo', 'precio_unitario'), f))
                for f in cur.fetchall()]
    finally:
        db.close()


def guardar_precio(conectar, producto_id, valor):
    precio = normalizar_precio(valor)
    db = conectar()
    try:
        cur = db.cursor()
        cur.execute('SELECT id FROM productos WHERE id = %s FOR UPDATE', (producto_id,))
        if cur.fetchone() is None:
            raise LookupError('No se encontró ese artículo.')
        if precio is None:
            cur.execute('DELETE FROM precios_referencia_productos WHERE producto_id = %s', (producto_id,))
        else:
            cur.execute('''INSERT INTO precios_referencia_productos (producto_id, precio_unitario)
                           VALUES (%s, %s) ON CONFLICT (producto_id) DO UPDATE
                           SET precio_unitario = EXCLUDED.precio_unitario,
                               actualizado_en = CURRENT_TIMESTAMP''', (producto_id, precio))
        db.commit()
        return precio
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def opciones_filtros(conectar):
    db = conectar()
    try:
        cur = db.cursor()
        cur.execute('SELECT id, nombre FROM obras ORDER BY nombre')
        obras = [dict(zip(('id', 'nombre'), f)) for f in cur.fetchall()]
        cur.execute('''SELECT p.id, o.nombre, p.fecha_compra, p.obra_id
                       FROM planillas p JOIN obras o ON o.id = p.obra_id
                       ORDER BY p.fecha_compra DESC, p.id DESC''')
        planillas = [dict(zip(('id', 'obra', 'fecha_compra', 'obra_id'), f)) for f in cur.fetchall()]
        return {'obras': obras, 'planillas': planillas}
    finally:
        db.close()


def resumir(filas):
    articulos = {}
    for solicitud_id, producto_id, nombre, unidad, cantidad, precio in filas:
        item = articulos.setdefault(producto_id, {
            'id': producto_id, 'nombre': nombre, 'unidad': unidad,
            'cantidad': Decimal(0), 'precio_unitario': precio, 'solicitudes': 0,
        })
        item['cantidad'] += Decimal(str(cantidad))
        item['solicitudes'] += 1
    total = Decimal('0.00')
    faltantes = 0
    solicitudes_sin_precio = 0
    for item in articulos.values():
        precio = item['precio_unitario']
        item['subtotal'] = None if precio is None else (
            item['cantidad'] * Decimal(str(precio))
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if precio is None:
            faltantes += 1
            solicitudes_sin_precio += item['solicitudes']
        else:
            total += item['subtotal']
    return {'articulos': list(articulos.values()), 'total_estimado': total,
            'articulos_sin_precio': faltantes, 'solicitudes_sin_precio': solicitudes_sin_precio,
            'solicitudes': sum(i['solicitudes'] for i in articulos.values()),
            'completo': faltantes == 0}


def estimar(conectar, fecha=None, obra_id=None, planilla_id=None, solo_aprobadas=False):
    filtros = ["UPPER(TRIM(COALESCE(p.estado_aprobacion, 'PENDIENTE'))) IN ('APROBADA', 'PENDIENTE')"]
    parametros = list(ESTADOS_PENDIENTES)
    if fecha:
        fecha = date.fromisoformat(str(fecha))
        filtros.append('CAST(p.fecha_compra AS date) = %s')
        parametros.append(fecha)
    for columna, valor in (('obra_id', obra_id), ('id', planilla_id)):
        if valor is not None:
            filtros.append(f'p.{columna} = %s')
            parametros.append(int(valor))
    if solo_aprobadas:
        filtros.append("UPPER(TRIM(p.estado_aprobacion)) = 'APROBADA'")
    sql = '''SELECT s.id, pr.id, pr.nombre, pr.unidad, s.cantidad, r.precio_unitario
             FROM solicitudes s JOIN productos pr ON pr.id = s.producto_id
             LEFT JOIN precios_referencia_productos r ON r.producto_id = pr.id
             WHERE UPPER(TRIM(COALESCE(s.estado, ''))) IN (%s, %s, %s, %s, %s)
               AND EXISTS (SELECT 1 FROM planilla_solicitudes ps
                           JOIN planillas p ON p.id = ps.planilla_id
                           WHERE ps.solicitud_id = s.id AND ''' + ' AND '.join(filtros) + ''')
             ORDER BY pr.nombre, pr.id, s.id'''
    db = conectar()
    try:
        cur = db.cursor()
        cur.execute(sql, tuple(parametros))
        return resumir(cur.fetchall())
    finally:
        db.close()
