-- Notifica solamente después de confirmar la transacción.
CREATE OR REPLACE FUNCTION notificar_comunicacion_100t()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify('comunicaciones_100t', json_build_object(
    'id', NEW.id, 'usuario_id', NEW.usuario_id)::text);
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS comunicacion_100t_insertada ON bloc_notas;
CREATE TRIGGER comunicacion_100t_insertada AFTER INSERT ON bloc_notas
FOR EACH ROW EXECUTE FUNCTION notificar_comunicacion_100t();
