# Exportación de consultas a Excel

Reportes incluye «Exportar a Excel» después de realizar una consulta con resultados. Incluye los encabezados, filtros aplicados, cantidad de resultados y fecha de exportación. Se exporta la instantánea consultada; no se vuelve a ejecutar la consulta. Cambiar un filtro sin aplicarlo no altera el archivo de la consulta anterior.

Archivo XLSX real, cantidades/identificadores numéricos, fechas de Excel (horas normalizadas a Argentina cuando la fuente tiene zona), encabezado fijo, autofiltro y observaciones como texto. Contenido que comienza con =, +, - o @ se almacena como texto de origen y no como fórmula.

Cloud: descarga mediante POST autenticado /reportes/exportar-excel. Cuenta activa de empleado/administrador; máximo 20.000 filas y 20MB por exportación. Si se supera, solicita aplicar filtros; nunca recorta resultados silenciosamente. Reportes sigue requiriendo conexión.

Windows y Mac: botón en cada tabla de reportes (solicitudes, solicitudes por obra, compras, entregas, obras); conserva orden visible y filtros capturados al consultar. Diálogo para elegir destino .xlsx y escritura temporal antes de reemplazar el archivo elegido. No requiere instalar Excel ni bibliotecas adicionales para generar el archivo.

El generador compartido exportar_reportes_excel.py usa ZIP/XML del estándar XLSX con la biblioteca de Python. La verificación utiliza openpyxl solo como lector. Fuentes Windows/Mac actualizadas sin compilar instaladores.
