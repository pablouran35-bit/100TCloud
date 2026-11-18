let parcialSolicitud=null,parcialPlanilla=null,parcialIntento=null;
function prepararCompraParcial(solicitud){
  const boton=document.getElementById('abrir-compra-parcial');
  boton.hidden=!['PENDIENTE DE COMPRA','PENDIENTE','SOLICITADO','ENCARGADO','NO DISPONIBLE'].includes((solicitud.estado||'').trim().toUpperCase())||solicitud.seguimiento;
}
document.getElementById('abrir-compra-parcial').onclick=()=>{
  parcialSolicitud=structuredClone(solicitudActual);parcialPlanilla=planillaActual.id;parcialIntento=null;
  document.getElementById('parcial-titulo').textContent=`Comprar parte de ${parcialSolicitud.cantidad} · ${parcialSolicitud.producto}`;
  document.getElementById('parcial-cantidad').value='';document.getElementById('parcial-saldo').textContent='El resto seguirá pendiente en esta planilla.';
  document.getElementById('parcial-mensaje').textContent='';
  const prov=document.getElementById('parcial-proveedor');prov.replaceChildren(new Option('Elegí proveedor',''));
  for(const p of proveedores)prov.add(new Option(p.nombre,p.id));
  document.getElementById('parcial-estado').selectedIndex=0;
  document.getElementById('compra-parcial-dialogo').showModal();
};
document.getElementById('parcial-cerrar').onclick=()=>document.getElementById('compra-parcial-dialogo').close();
document.getElementById('parcial-cantidad').oninput=()=>{
  const n=Number(document.getElementById('parcial-cantidad').value.replace(',','.'));
  document.getElementById('parcial-saldo').textContent=Number.isFinite(n)&&n>0?`Quedarán pendientes: ${(Number(parcialSolicitud.cantidad)-n).toLocaleString('es-AR')}`:'Ingresá cuánto comprás ahora.';
};
document.getElementById('form-compra-parcial').onsubmit=async e=>{
  e.preventDefault();const boton=document.getElementById('parcial-guardar'),msg=document.getElementById('parcial-mensaje');
  const cantidad=document.getElementById('parcial-cantidad').value.trim().replace(',','.');
  if(!/^\d+(?:\.\d{1,6})?$/.test(cantidad)||Number(cantidad)<=0||Number(cantidad)>=Number(parcialSolicitud.cantidad)){msg.textContent='Ingresá una cantidad positiva menor que la pendiente.';return;}
  const datos={cantidad,cantidad_anterior:String(parcialSolicitud.cantidad),estado_anterior:parcialSolicitud.estado,proveedor_id:Number(document.getElementById('parcial-proveedor').value),estado_compra:document.getElementById('parcial-estado').value};
  if(!datos.proveedor_id){msg.textContent='Elegí el proveedor de esta compra.';return;}
  const contenido=JSON.stringify(datos);
  if(parcialIntento?.contenido!==contenido)parcialIntento={contenido,clave:crypto.randomUUID()};
  boton.disabled=true;document.getElementById('parcial-cerrar').disabled=true;msg.textContent='Guardando…';let guardado=false;
  try{
    const respuesta=await fetch(`/compras-parciales/${parcialPlanilla}/${parcialSolicitud.id}`,{method:'POST',cache:'no-store',headers:{Authorization:'Bearer '+sessionStorage.getItem('token'),'Content-Type':'application/json','Idempotency-Key':parcialIntento.clave},body:contenido});
    const r=await respuesta.json();if(!respuesta.ok)throw Error(typeof r.detail==='string'?r.detail:'No se pudo registrar la compra parcial.');
    guardado=true;document.getElementById('compra-parcial-dialogo').close();dialogoSolicitud.close();
    planillaActual=await llamarApi('/compras/planillas/'+parcialPlanilla);mostrarSolicitudes();
    await Promise.all([cargarPlanillas(),cargarDiaCompras()]);mensaje('mensaje-solicitudes-compra',r.mensaje);
  }catch(error){
    const texto=guardado?'La compra se guardó; volvé a abrir la planilla para ver el saldo.':error.message+' Si se interrumpió la conexión, reintentá sin cambiar los datos.';
    msg.textContent=texto;if(guardado)mensaje('mensaje-solicitudes-compra',texto,true);
  }finally{boton.disabled=false;document.getElementById('parcial-cerrar').disabled=false;}
};
document.getElementById('compra-parcial-dialogo').addEventListener('cancel',e=>{if(document.getElementById('parcial-guardar').disabled)e.preventDefault();});
