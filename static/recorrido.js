(() => {
 const $=id=>document.getElementById(id),api=window.offline100t,token=sessionStorage.getItem('token');
 if(!token){location.replace('/app/');return;}
 let recorrido=null,ocupado=false;
 $('fecha').value=new Date(Date.now()-3*3600000).toISOString().slice(0,10);
 function bloquear(v){ocupado=v;document.querySelectorAll('main button,main select,main input').forEach(e=>e.disabled=v);}
 function pintar(){
  $('proveedor').replaceChildren(new Option('Elegí un proveedor',''));
  const ids=new Set(recorrido.paradas.map(p=>p.proveedor_id));
  for(const p of recorrido.proveedores || [])if(!ids.has(p.id))$('proveedor').add(new Option(p.nombre,p.id));
  $('paradas').replaceChildren();const hechas=recorrido.paradas.filter(p=>p.visitado).length;
  const faltan=recorrido.paradas.length-hechas;
  $('resumen').textContent=`${hechas} ${hechas===1?'visitado':'visitados'} · ${faltan} ${faltan===1?'pendiente':'pendientes'}`;
  if(!recorrido.paradas.length)$('paradas').textContent='Todavía no agregaste proveedores para este día.';
  recorrido.paradas.forEach((p,i)=>{
    const caja=document.createElement('section');caja.className='parada'+(p.visitado?' visitada':'');
    const titulo=document.createElement('strong');titulo.textContent=`${i+1}. ${p.nombre}`;
    const estado=document.createElement('small');estado.textContent=p.visitado?'✓ Visitado · no hace falta volver':'Pendiente de visitar';
    const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=p.visitado;
    check.onchange=()=>cambiar(lista=>lista[i].visitado=check.checked);
    label.append(check,document.createTextNode('Ya fui a este proveedor'));
    const botones=document.createElement('div');botones.className='botones';
    for(const [texto,delta] of [['↑ Subir',-1],['↓ Bajar',1]]){
      const b=document.createElement('button');b.type='button';b.textContent=texto;b.setAttribute('aria-label',`${texto} ${p.nombre}`);b.disabled=i+delta<0||i+delta>=recorrido.paradas.length;
      b.onclick=()=>cambiar(lista=>{[lista[i],lista[i+delta]]=[lista[i+delta],lista[i]];});botones.append(b);
    }
    const quitar=document.createElement('button');quitar.type='button';quitar.textContent='Quitar parada';quitar.className='quitar';quitar.onclick=()=>cambiar(lista=>lista.splice(i,1));botones.append(quitar);
    caja.append(titulo,estado,label,botones);$('paradas').append(caja);
  });
 }
 async function cargar(){
  if(ocupado)return;bloquear(true);$('mensaje').textContent='Cargando recorrido...';
  try{
    const ruta='/recorridos/'+$('fecha').value,uid=JSON.parse(sessionStorage.getItem('usuario') || '{}').id;
    const pendientes=await api.listarPendientes(uid);
    if(navigator.onLine && !pendientes.some(p=>p.url===ruta)) {
      try {
        const r=await fetch(ruta,{cache:'no-store',signal:AbortSignal.timeout(10000),headers:{Authorization:'Bearer '+token}}),d=await r.json();
        if(!r.ok)throw Object.assign(Error(typeof d.detail==='string'?d.detail:'No se pudo consultar el recorrido.'),{status:r.status});
        recorrido=d;await api.guardarDato('respuesta:'+ruta,d,uid);
      }catch(e){if(e.status)throw e;recorrido=await api.leerDato('respuesta:'+ruta,uid);if(!recorrido)throw e;}
    } else recorrido=await api.solicitarApi(ruta,{},token);
    pintar();$('mensaje').textContent=recorrido.pendiente?'Guardado en este teléfono; pendiente de sincronizar.':'Recorrido actualizado.';
  }
  catch(e){$('paradas').replaceChildren();recorrido=null;$('mensaje').textContent=e.message;}
  finally{bloquear(false);if(recorrido)pintar();}
 }
 async function cambiar(accion){
  if(ocupado||!recorrido)return;
  const anteriores=structuredClone(recorrido),paradas=structuredClone(recorrido.paradas);accion(paradas);bloquear(true);$('mensaje').textContent='Guardando...';
  try{
    const datos=await api.solicitarApi('/recorridos/'+recorrido.fecha,{method:'PUT',body:JSON.stringify({revision:recorrido.revision,paradas:paradas.map(p=>({proveedor_id:p.proveedor_id,visitado:p.visitado}))})},token);
    recorrido={...recorrido,...datos};
    let aviso=datos.pendiente?'Recorrido guardado en este teléfono; se enviará al volver la conexión.':'Recorrido guardado.';
    try { await api.guardarDato('respuesta:/recorridos/'+recorrido.fecha,recorrido,JSON.parse(sessionStorage.getItem('usuario') || '{}').id); }
    catch { aviso+=' No se pudo actualizar la copia offline; liberá espacio en el teléfono.'; }
    $('mensaje').textContent=aviso;
  }catch(e){recorrido=anteriores;$('mensaje').textContent=e.message;}
  finally{bloquear(false);pintar();}
 }
 $('agregar').onclick=()=>{const id=Number($('proveedor').value),p=recorrido?.proveedores.find(p=>p.id===id);if(p)cambiar(lista=>lista.push({proveedor_id:p.id,nombre:p.nombre,visitado:false}));};
 $('fecha').onchange=cargar;$('actualizar').onclick=cargar;
 window.addEventListener('100t:sincronizado',cargar);cargar();
})();
