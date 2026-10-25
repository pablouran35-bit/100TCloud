"""Fotografías de referencia del material pedido, vinculadas a una solicitud."""
from fotos_planillas import FotosPlanillas

class FotosSolicitudes(FotosPlanillas):
    tabla_fotos='fotos_solicitudes'
    campo_recurso='solicitud_id'
    def autorizar(self,q,usuario_id,recurso_id=None):
        self.ejecutar(q,"""SELECT COALESCE(NULLIF(TRIM(COALESCE(p.nombre,'') || ' ' || COALESCE(p.apellido,'')),''),u.usuario)
          FROM usuarios u JOIN personas p ON p.id=u.persona_id
          WHERE u.id=%s AND p.activo=TRUE AND EXISTS (
            SELECT 1 FROM solicitudes s WHERE s.id=%s AND (
              EXISTS (SELECT 1 FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id
                      WHERE ur.usuario_id=u.id AND UPPER(TRIM(r.nombre)) IN ('ADMINISTRADOR','EMPLEADO'))
              OR (EXISTS (SELECT 1 FROM usuario_rol ur JOIN roles r ON r.id=ur.rol_id
                         WHERE ur.usuario_id=u.id AND UPPER(TRIM(r.nombre))='CONTRATISTA')
                  AND EXISTS (SELECT 1 FROM persona_obra po WHERE po.persona_id=p.id AND po.obra_id=s.obra_id))
            ))""",(usuario_id,recurso_id))
        fila=q.fetchone()
        if not fila:raise PermissionError('No tenés acceso a las fotos de esta solicitud.')
        return fila[0]
    def planilla(self,q,sid):
        self.ejecutar(q,'SELECT id FROM solicitudes WHERE id=%s',(sid,))
        if not q.fetchone():raise ValueError('La solicitud no existe.')
