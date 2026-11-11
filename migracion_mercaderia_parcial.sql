BEGIN;

ALTER TABLE historial_solicitudes
    ADD COLUMN IF NOT EXISTS cantidad_entrega numeric CHECK (cantidad_entrega > 0);

CREATE TABLE IF NOT EXISTS movimientos_mercaderia (
    solicitud_id bigint PRIMARY KEY REFERENCES solicitudes(id) ON DELETE CASCADE,
    retirada numeric NOT NULL CHECK (retirada >= 0),
    entregada numeric NOT NULL CHECK (entregada >= 0 AND entregada <= retirada),
    tarea_retiro_id bigint UNIQUE REFERENCES tareas(id) ON DELETE SET NULL
);

CREATE OR REPLACE VIEW saldos_mercaderia AS
SELECT s.id AS solicitud_id,
       m.solicitud_id IS NOT NULL AS seguimiento,
       COALESCE(m.retirada, CASE WHEN UPPER(s.estado) IN (
           'COMPRADO Y RETIRADO', 'ENTREGADO',
           'COMPRADO A ENTREGAR POR PROVEEDOR/FLETE',
           'COMPRADO A ENTREGAR POR PROVEEDOR', 'COMPRADO A ENTREGAR POR FLETE'
       ) THEN s.cantidad::numeric ELSE 0 END) AS retirada,
       COALESCE(m.entregada, CASE WHEN UPPER(s.estado) = 'ENTREGADO'
           THEN s.cantidad::numeric ELSE 0 END) AS entregada
FROM solicitudes s
LEFT JOIN movimientos_mercaderia m ON m.solicitud_id = s.id;

CREATE OR REPLACE FUNCTION estado_mercaderia(total numeric, retirada numeric, entregada numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN entregada = total THEN 'ENTREGADO'
                WHEN entregada > 0 THEN 'ENTREGA PARCIAL'
                WHEN retirada = total THEN 'COMPRADO Y RETIRADO'
                ELSE 'COMPRADO CON RETIRO PARCIAL' END;
$$;

-- Protege el saldo frente a ediciones de estado desde clientes anteriores.
CREATE OR REPLACE FUNCTION proteger_saldo_mercaderia() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    saldo movimientos_mercaderia%ROWTYPE;
BEGIN
    SELECT * INTO saldo FROM movimientos_mercaderia WHERE solicitud_id = OLD.id;
    IF FOUND AND (
        NEW.cantidad IS DISTINCT FROM OLD.cantidad
        OR (OLD.proveedor_id IS NOT NULL AND NEW.proveedor_id IS DISTINCT FROM OLD.proveedor_id)
        OR NEW.estado IS DISTINCT FROM estado_mercaderia(OLD.cantidad::numeric, saldo.retirada, saldo.entregada)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023',
            MESSAGE = 'Esta solicitud tiene movimientos de mercadería. Usá las opciones de retiro y entrega.';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS proteger_saldo_mercaderia ON solicitudes;
CREATE TRIGGER proteger_saldo_mercaderia
BEFORE UPDATE OF estado, cantidad, proveedor_id ON solicitudes
FOR EACH ROW EXECUTE FUNCTION proteger_saldo_mercaderia();

CREATE OR REPLACE FUNCTION registrar_retiro_mercaderia(
    p_planilla bigint, p_solicitud bigint, p_cantidad numeric, p_retirada_anterior numeric,
    p_estado_anterior text, p_proveedor bigint, p_usuario bigint, p_observaciones text
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    solicitud solicitudes%ROWTYPE;
    saldo saldos_mercaderia%ROWTYPE;
    proveedor_nombre text;
    articulo text;
    persona bigint;
    tarea bigint;
    restante numeric;
    nueva_retirada numeric;
    nuevo_estado text;
    texto_tarea text;
    estado_tarea text;
BEGIN
    SELECT s.* INTO solicitud FROM solicitudes s
    JOIN planilla_solicitudes ps ON ps.solicitud_id = s.id
    JOIN planillas p ON p.id = ps.planilla_id
    WHERE ps.planilla_id = p_planilla AND s.id = p_solicitud
      AND UPPER(TRIM(p.estado_aprobacion)) = 'APROBADA'
    FOR UPDATE OF s;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'La solicitud no pertenece a una planilla aprobada.';
    END IF;
    SELECT * INTO saldo FROM saldos_mercaderia WHERE solicitud_id = p_solicitud;
    IF COALESCE(solicitud.estado, '') IS DISTINCT FROM COALESCE(p_estado_anterior, '')
        OR saldo.retirada IS DISTINCT FROM p_retirada_anterior THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'El retiro cambió. Volvé a abrir la solicitud.';
    END IF;
    IF UPPER(COALESCE(solicitud.estado, '')) IN ('CANCELADA', 'RECHAZADA', 'ENTREGADO')
        OR p_cantidad IS NULL OR p_cantidad::text IN ('NaN', 'Infinity', '-Infinity')
        OR p_cantidad <= 0 OR p_cantidad > solicitud.cantidad::numeric - saldo.retirada THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Ingresá una cantidad positiva que no supere el saldo por retirar.';
    END IF;
    IF solicitud.proveedor_id IS NOT NULL AND solicitud.proveedor_id IS DISTINCT FROM p_proveedor
        AND (saldo.seguimiento OR UPPER(solicitud.estado) = 'COMPRADO A RETIRAR') THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Registrá el retiro con el proveedor de la compra.';
    END IF;
    SELECT nombre INTO proveedor_nombre FROM proveedores
    WHERE id = p_proveedor AND (activo OR (saldo.seguimiento AND id = solicitud.proveedor_id));
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Elegí el proveedor para registrar el retiro.';
    END IF;
    SELECT nombre INTO articulo FROM productos WHERE id = solicitud.producto_id;
    SELECT persona_id INTO persona FROM usuarios WHERE id = p_usuario;
    nueva_retirada := saldo.retirada + p_cantidad;
    restante := solicitud.cantidad::numeric - nueva_retirada;
    nuevo_estado := estado_mercaderia(solicitud.cantidad::numeric, nueva_retirada, saldo.entregada);
    INSERT INTO movimientos_mercaderia(solicitud_id, retirada, entregada)
    VALUES (p_solicitud, nueva_retirada, saldo.entregada)
    ON CONFLICT (solicitud_id) DO UPDATE SET retirada = EXCLUDED.retirada
    RETURNING tarea_retiro_id INTO tarea;

    IF restante > 0 THEN
        texto_tarea := 'Retirar ' || trim_scale(restante) || ' de ' || articulo || ' de ' || proveedor_nombre;
        IF tarea IS NULL THEN
            INSERT INTO tareas(descripcion, solicitante_id, fecha_solicitud, estado, observaciones)
            VALUES (texto_tarea, persona, (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date,
                    'PENDIENTE', 'Solicitud #' || p_solicitud || ' · Planilla #' || p_planilla)
            RETURNING id, estado INTO tarea, estado_tarea;
            UPDATE movimientos_mercaderia SET tarea_retiro_id = tarea WHERE solicitud_id = p_solicitud;
        ELSE
            UPDATE tareas SET descripcion = texto_tarea,
                estado = CASE WHEN estado = 'EN PROCESO' THEN estado ELSE 'PENDIENTE' END
            WHERE id = tarea RETURNING estado INTO estado_tarea;
        END IF;
        INSERT INTO historial_tareas(tarea_id, estado, fecha_hora, observaciones, usuario_id)
        VALUES (tarea, estado_tarea, CURRENT_TIMESTAMP, texto_tarea, p_usuario);
    ELSIF tarea IS NOT NULL THEN
        UPDATE tareas SET estado = 'FINALIZADA' WHERE id = tarea;
        INSERT INTO historial_tareas(tarea_id, estado, fecha_hora, observaciones, usuario_id)
        VALUES (tarea, 'FINALIZADA', CURRENT_TIMESTAMP, 'Se retiró toda la mercadería.', p_usuario);
    END IF;

    UPDATE solicitudes SET estado = nuevo_estado, proveedor_id = p_proveedor,
        observaciones = p_observaciones WHERE id = p_solicitud;
    INSERT INTO historial_solicitudes(solicitud_id, estado, fecha_hora, observaciones, usuario_id)
    VALUES (p_solicitud, nuevo_estado, CURRENT_TIMESTAMP,
        CONCAT_WS(' · ', 'Retiro: ' || trim_scale(p_cantidad), 'En proveedor: ' || trim_scale(restante),
                  NULLIF(p_observaciones, '')), p_usuario);
    RETURN nuevo_estado;
END;
$$;

CREATE OR REPLACE FUNCTION registrar_entrega_mercaderia(
    p_planilla bigint, p_solicitud bigint, p_cantidad numeric, p_entregada_anterior numeric,
    p_usuario bigint, p_fecha timestamptz
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    solicitud solicitudes%ROWTYPE;
    saldo saldos_mercaderia%ROWTYPE;
    disponible numeric;
    nueva_entregada numeric;
    nuevo_estado text;
BEGIN
    SELECT s.* INTO solicitud FROM solicitudes s
    JOIN planilla_solicitudes ps ON ps.solicitud_id = s.id
    WHERE ps.planilla_id = p_planilla AND s.id = p_solicitud FOR UPDATE OF s;
    IF NOT FOUND OR UPPER(COALESCE(solicitud.estado, '')) NOT IN (
        'COMPRADO Y RETIRADO', 'COMPRADO CON RETIRO PARCIAL', 'ENTREGA PARCIAL',
        'COMPRADO A ENTREGAR POR PROVEEDOR/FLETE', 'COMPRADO A ENTREGAR POR PROVEEDOR',
        'COMPRADO A ENTREGAR POR FLETE'
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'La solicitud ya no está disponible para entregar.';
    END IF;
    SELECT * INTO saldo FROM saldos_mercaderia WHERE solicitud_id = p_solicitud;
    IF (p_entregada_anterior IS NULL AND saldo.seguimiento)
        OR (p_entregada_anterior IS NOT NULL AND saldo.entregada <> p_entregada_anterior) THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'El saldo de entrega cambió. Recargá la planilla.';
    END IF;
    disponible := saldo.retirada - saldo.entregada;
    p_cantidad := COALESCE(p_cantidad, disponible);
    IF p_cantidad::text IN ('NaN', 'Infinity', '-Infinity') OR p_cantidad <= 0 OR p_cantidad > disponible THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'La cantidad a entregar supera lo disponible o no es positiva.';
    END IF;

    nueva_entregada := saldo.entregada + p_cantidad;
    nuevo_estado := estado_mercaderia(solicitud.cantidad::numeric, saldo.retirada, nueva_entregada);
    IF saldo.seguimiento OR nuevo_estado <> 'ENTREGADO' THEN
        INSERT INTO movimientos_mercaderia(solicitud_id, retirada, entregada)
        VALUES (p_solicitud, saldo.retirada, nueva_entregada)
        ON CONFLICT (solicitud_id) DO UPDATE SET entregada = EXCLUDED.entregada;
    END IF;
    UPDATE solicitudes SET estado = nuevo_estado WHERE id = p_solicitud;
    INSERT INTO historial_solicitudes(solicitud_id, estado, fecha_hora, observaciones, usuario_id, cantidad_entrega)
    VALUES (p_solicitud, nuevo_estado, COALESCE(p_fecha, CURRENT_TIMESTAMP),
        'Entrega: ' || trim_scale(p_cantidad) || ' · Pendiente en obra: ' ||
        trim_scale(solicitud.cantidad::numeric - nueva_entregada), p_usuario, p_cantidad);
    RETURN nuevo_estado;
END;
$$;

COMMIT;
