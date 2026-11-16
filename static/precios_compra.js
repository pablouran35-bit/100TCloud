let precioRealActual = null;
let solicitudPrecioReal = null;
let cargaPrecioReal = 0;
async function apiPrecioReal(url, opciones={}) {
  const r = await fetch(url, {...opciones, cache:'no-store', headers:{Authorization:'Bearer '+sessionStorage.getItem('token'),'Content-Type':'application/json'}});
  const datos = await r.json();
  if(!r.ok) throw Error(typeof datos.detail==='string'?datos.detail:'No se pudo guardar el precio.');
  return datos;
}
async function cargarPrecioReal(id) {
  const carga = ++cargaPrecioReal;
  solicitudPrecioReal = id;
  precioRealActual = null;
  const entrada = document.getElementById('precio-real');
  const guardar = document.getElementById('guardar-precio-real');
  entrada.value = '';
  entrada.disabled = guardar.disabled = true;
  document.getElementById('mensaje-precio-real').textContent = 'Cargando precio real…';
  try {
    const datos = await apiPrecioReal('/compras/precios-reales/'+id);
    if(carga !== cargaPrecioReal) return;
    precioRealActual = datos;
    entrada.value = datos.precio_unitario ?? '';
    document.getElementById('unidad-precio-real').textContent = 'Precio real por '+(datos.unidad || 'unidad')+' (ARS)';
    document.getElementById('mensaje-precio-real').textContent = datos.total == null ? 'Sin precio registrado para esta compra.' : 'Total de la solicitud: $ '+datos.total;
    entrada.disabled = guardar.disabled = false;
  } catch(e) {
    if(carga === cargaPrecioReal) document.getElementById('mensaje-precio-real').textContent = 'No se pudo cargar el precio. Necesitás conexión. '+e.message;
  }
}
document.getElementById('guardar-precio-real').onclick = async () => {
  if(!precioRealActual) return;
  const id = solicitudPrecioReal, carga = cargaPrecioReal;
  const boton = document.getElementById('guardar-precio-real');
  boton.disabled = true;
  try {
    const datos = await apiPrecioReal('/compras/precios-reales/'+id, {method:'PUT',body:JSON.stringify({precio_unitario:document.getElementById('precio-real').value,revision:precioRealActual.revision})});
    if(carga !== cargaPrecioReal) return;
    precioRealActual = datos;
    document.getElementById('mensaje-precio-real').textContent = 'Precio guardado. '+(datos.total == null ? 'Sin precio.' : 'Total: $ '+datos.total);
  } catch(e) {
    if(carga === cargaPrecioReal) document.getElementById('mensaje-precio-real').textContent = e.message+' Volvé a abrir la solicitud antes de reintentar.';
  } finally { if(carga === cargaPrecioReal) boton.disabled = false; }
};
