-- Ejecutar una sola vez en Supabase antes de habilitar la sincronización offline.
-- La clave y el resultado se confirman en la misma transacción que cada cambio,
-- para que reenviar una solicitud después de perder la conexión no la duplique.
CREATE TABLE IF NOT EXISTS operaciones_offline (
    operacion_id UUID PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
    recurso TEXT NOT NULL,
    resultado JSONB,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS operaciones_offline_creada_en_idx
    ON operaciones_offline (creada_en);
