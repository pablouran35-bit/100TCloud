"""Una conexión LISTEN por proceso; no consulta periódicamente los mensajes."""
import json
import logging
import select
from queue import Queue, Full
from threading import Lock, Thread

import conexion

_lock = Lock()
_clientes = set()
_hilo = None

def _publicar(evento):
    with _lock:
        for cola in _clientes:
            try:
                cola.put_nowait(evento)
            except Full:
                # El cliente recarga el historial completo con cualquier evento.
                pass

def _escuchar():
    from time import sleep
    while True:
        db = None
        try:
            db = conexion.conectar()
            db.autocommit = True
            with db.cursor() as cursor:
                cursor.execute('LISTEN comunicaciones_100t')
            _publicar({'tipo': 'reconectado'})
            while True:
                if select.select([db], [], [], 15)[0]:
                    db.poll()
                    while db.notifies:
                        aviso = db.notifies.pop(0)
                        _publicar({'tipo': 'comunicacion', **json.loads(aviso.payload)})
                else:
                    # Detecta desconexiones sin consultar ninguna tabla.
                    with db.cursor() as cursor:
                        cursor.execute('SELECT 1')
        except Exception:
            logging.exception('Se reconectará el canal de comunicaciones')
            sleep(5)
        finally:
            if db is not None:
                db.close()

def suscribir():
    global _hilo
    cola = Queue(maxsize=100)
    with _lock:
        _clientes.add(cola)
        if _hilo is None or not _hilo.is_alive():
            _hilo = Thread(target=_escuchar, daemon=True)
            _hilo.start()
    return cola

def desuscribir(cola):
    with _lock:
        _clientes.discard(cola)
