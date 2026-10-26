# Recorrido de proveedores

Acceso desde Compras → Recorrido de proveedores. Agregar proveedores registrados, subir/bajar su orden, quitar paradas y tildar/destildar «Ya fui». Las pendientes quedan amarillas y las visitadas verdes, con texto de estado además del color.

Se guarda automáticamente cada cambio, separado por usuario y día. La misma cuenta puede preparar el recorrido en PC y consultarlo/continuarlo desde Cloud. Marcar la visita no modifica solicitudes ni estados de compra.

Cloud descarga el recorrido del día en Preparar teléfono. También se conserva el día que se abre conectado. Sin internet se requieren esos datos previos; los cambios se encolan en orden y se sincronizan al abrir la aplicación con conexión. Una revisión incompatible de otro dispositivo devuelve conflicto 409 y conserva lo pendiente para revisión en la pantalla de sincronización.

Servidor y escritorio comparten el servicio recorrido_proveedores.py. Tabla aditiva recorridos_proveedores, idempotencia en operaciones_offline, comprobación de cuenta activa/rol empleado o administrador y bloqueo/revisión antes de guardar. No se modifican tablas de compras ni solicitudes.

Windows y Mac actualizados en fuente; no se generaron instaladores ni se ejecutaron compilaciones nativas macOS.
