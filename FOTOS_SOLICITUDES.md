# Fotos por solicitud

- Cloud: «Agregar solicitud y fotos» guarda la solicitud y abre cámara/galería. También hay acceso desde el detalle existente y desde Compras.
- Windows/Mac: «GUARDAR Y AGREGAR FOTOS», luego elegir archivos, revisar y subir. Acceso desde Planillas existentes y desde Compras.
- Varias imágenes por solicitud, comprimidas a JPEG (máximo 1280px y 450KB), sin EXIF/GPS.
- Las fotos del pedido pertenecen a la solicitud. Las fotos de entrega siguen perteneciendo a la planilla.
- Cloud conserva borradores y envíos pendientes en IndexedDB. La cola espera el ID confirmado de la solicitud antes de enviar sus fotos.
- Empleados/administradores activos: acceso a solicitudes. Contratistas: solo solicitudes de obras asignadas. El servidor valida cada lectura y escritura, también las miniaturas.
- Tabla adicional fotos_solicitudes; migración aditiva migracion_fotos_solicitudes.sql. No se modifican solicitudes existentes.
- Windows/Mac actualizados en fuente. No se generaron instaladores. Los instaladores anteriores no contienen estos cambios.
