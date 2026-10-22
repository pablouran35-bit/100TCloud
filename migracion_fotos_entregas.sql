BEGIN;
CREATE TABLE IF NOT EXISTS fotos_entrega_planillas (
    id UUID PRIMARY KEY,
    planilla_id BIGINT NOT NULL REFERENCES planillas(id),
    usuario_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_nombre TEXT NOT NULL,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imagen BYTEA NOT NULL CHECK (octet_length(imagen) <= 460800),
    miniatura BYTEA NOT NULL,
    ancho INTEGER NOT NULL CHECK (ancho BETWEEN 1 AND 1280),
    alto INTEGER NOT NULL CHECK (alto BETWEEN 1 AND 1280),
    huella TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fotos_entrega_planilla_fecha_idx
    ON fotos_entrega_planillas(planilla_id,creada_en);
COMMIT;
