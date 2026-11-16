const $=id=>document.getElementById(id);
let documento=null,planilla=null;
async function api(ruta,opciones={}) {
  const r=await fetch('/corregir-articulos/'+ruta,{...opciones,cache:'no-store',headers:{Authorization:'Bearer '+sessionStorage.getItem('token'),'Content-Type':'application/json'}});
  const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'No se pudo completar la corrección.');return d;
}
function seleccionar(){
  const s=documento.solicitudes.find(s=>String(s.id)===$('solicitud').value);
  $('detalle').textContent=`${s.cantidad} ${s.unidad} · ${s.estado}\nObservaciones: ${s.observaciones || 'Sin observaciones'}`;
  $('buscar-articulo').value='';filtrar();$('articulo').value='';
}
function filtrar(){
  const consulta=$('buscar-articulo').value.trim().toLocaleLowerCase('es');
  const elegido=$('articulo').value;
  $('articulo').replaceChildren(new Option('Elegí el artículo correcto',''));
  for(const p of documento.productos)if(String(p.id)===elegido||p.nombre.toLocaleLowerCase('es').includes(consulta))$('articulo').add(new Option(`${p.nombre} · ${p.unidad}`,p.id));
  $('articulo').value=elegido;
}
$('buscar-planilla').onsubmit=async e=>{
  e.preventDefault();$('correccion').hidden=true;documento=null;planilla=null;$('mensaje').textContent='Cargando…';
  try{
    const id=Number($('numero').value);const datos=await api(id);
    documento=datos;planilla=id;$('solicitud').replaceChildren();
    for(const s of documento.solicitudes)$('solicitud').add(new Option(`#${s.id} · ${s.cantidad} · ${s.articulo}`,s.id));
    seleccionar();$('correccion').hidden=false;$('mensaje').textContent='';
  }catch(e){$('mensaje').textContent=e.message;}
};
$('solicitud').onchange=seleccionar;$('buscar-articulo').oninput=filtrar;
$('correccion').onsubmit=async e=>{
  e.preventDefault();if(!documento||!$('articulo').value)return;
  const doc=documento,id=planilla,s=doc.solicitudes.find(s=>String(s.id)===$('solicitud').value),nuevo=Number($('articulo').value);
  $('guardar').disabled=true;
  try{
    const r=await api(`${id}/${s.id}`,{method:'PUT',body:JSON.stringify({producto_anterior:s.producto_id,producto_nuevo:nuevo})});
    if(doc!==documento)return;
    s.producto_id=nuevo;s.articulo=doc.productos.find(p=>p.id===nuevo).nombre;
    [...$('solicitud').options].find(o=>o.value===String(s.id)).textContent=`#${s.id} · ${s.cantidad} · ${s.articulo}`;
    $('mensaje').textContent=r.mensaje;
  }catch(e){$('mensaje').textContent=e.message;}
  finally{$('guardar').disabled=false;}
};
