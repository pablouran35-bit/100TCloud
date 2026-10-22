# Cloud: trabajo sin conexión

Desde el inicio: **Preparar teléfono / revisar sincronización**.

1. Ingresar con internet y descargar los datos antes de salir.
2. En un teléfono propio, marcar la opción de conservar la sesión si se necesita reabrir la aplicación sin internet.
3. Consultar y cargar planillas y solicitudes, trabajar con tareas, cambiar compras por selección conjunta y registrar entregas usando la copia descargada.
4. Las fotos se comprimen. La selección queda conservada como borrador; **Guardar fotos** la incorpora a la cola de envío. Se admiten varias fotos por planilla.
5. Al recuperar conexión, abrir 100T para sincronizar. También hay un botón manual. Si otra persona cambió una solicitud incompatible, la cola se detiene y conserva lo pendiente para revisión.

Las nuevas compras disponibles se reflejan localmente en Entregas; una entrega pendiente permite seleccionar esa planilla para adjuntar fotos el mismo día.

## Límites

- El primer ingreso y la preparación requieren internet. No se descargan datos que el usuario no puede consultar en el servidor.
- La copia no contiene cambios de otros dispositivos posteriores a la descarga.
- Administración, permisos, reportes, comunicaciones y edición completa de planillas siguen requiriendo conexión. La edición individual de Compras sin conexión conserva el alcance anterior: cambio de estado; estado y proveedor se pueden cambiar en la selección conjunta.
- Las fotos ya abiertas se conservan. No se descargan todas las fotografías históricas durante la preparación.
- Sin conexión no se envían notificaciones ni se comparten cambios con otros equipos.
- El envío automático requiere la aplicación abierta; al cerrar o bloquear, el sistema del teléfono puede suspenderla.
- No borrar almacenamiento del navegador ni desinstalar con cambios pendientes. Se ofrece exportar respaldo JSON de datos/pendientes, sin token. No hay importación automática de ese archivo.
- La sesión debe renovarse con internet al vencer el token. Cerrar sesión mantiene los pendientes del usuario pero exige ingresar otra vez con conexión.
- Los conflictos se conservan y se pueden reconsultar. Su resolución debe revisar el cambio de oficina; no hay opción que fuerce la sobreescritura.

## Verificación

Pruebas JavaScript con IndexedDB simulado (fake-indexeddb): persistencia al reiniciar scripts, fotos Blob/JPEG, operaciones conjuntas, selección inconsistente rechazada sin alterar datos, cola ordenada, conflicto 409, separación por usuario, creación de planilla y solicitud, compra → entrega → fotos sin conexión. Pruebas existentes de fechas, autorización API de compras y fotos. Sintaxis JavaScript revisada. Preparación y pantalla verificadas en el navegador integrado con datos ficticios.

Pendiente de validación operativa: prueba real en el teléfono del usuario con modo avión. No se generaron instaladores ni se modificaron fuentes Windows/Mac en esta etapa.
