# Importación de planillas desde Excel

Planilla nueva → Importar Excel. Acepta XLSX hasta 8 MB y 1.000 materiales por hoja.
Elegir archivo, hoja y columnas (si no se reconocen), luego obra. Revisar cantidades,
unidades, artículos y áreas. Las fórmulas usan el resultado guardado por Excel.
Las áreas múltiples deben resolverse manualmente. Se pueden excluir filas.
Empleados y administradores pueden confirmar altas de artículos nuevos; contratistas
eligen artículos existentes. Unidades diferentes requieren confirmación explícita.
El OK crea siempre una planilla separada. Respeta roles, obra asignada y fecha de salida.
Toda la operación se confirma o revierte junta; reintentos del mismo OK no duplican.
Requiere internet. No modifica el archivo Excel y no importa automáticamente ejemplos.

Fuentes Windows y Mac actualizadas; no se generaron instaladores.
Validación: archivo de ejemplo leído sin cambios; pruebas aisladas de permisos,
transacciones, área cero, unidades, deduplicación y SQL PostgreSQL; API autenticada.
