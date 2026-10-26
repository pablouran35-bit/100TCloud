CREATE TABLE IF NOT EXISTS recorridos_proveedores (
 usuario_id BIGINT NOT NULL REFERENCES usuarios(id),
 fecha DATE NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
 paradas JSONB NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(paradas)='array'),
 actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(usuario_id,fecha)
);
