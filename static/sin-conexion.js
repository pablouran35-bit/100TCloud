(() => {
  const $=id=>document.getElementById(id),api=window.offline100t;
  const u=JSON.parse(sessionStorage.getItem('usuario')||'{}'),token=sessionStorage.getItem('token');
  if(!u.id || !token){location.replace('/app/');return;}
  const detalle=e=>typeof e==='string'?e:(e?.mensaje || e?.message || JSON.stringify(e));
  $('recordar').checked=!!localStorage.getItem('100t-sesion-dispositivo');
  $('recordar').onchange=()=>{if(!$('recordar').checked)localStorage.removeItem('100t-sesion-dispositivo');};
  async function actualizar(){
    const ops=await api.listarPendientes(u.id);$('pendientes').replaceChildren();
    if(!ops.length){$('pendientes').textContent='No hay cambios pendientes.';return;}
    for(const op of ops){
      const li=document.createElement('li');
      li.textContent=`${op.content_type?'Foto de entrega':op.url} · ${op.estado}`;
      const texto=document.createElement('small');texto.textContent=`${new Date(op.creado_en).toLocaleString('es-AR')}${op.error?' · '+detalle(op.error):''}`;li.append(texto);
      if(op.estado==='ERROR' || op.estado==='CONFLICTO'){
        const boton=document.createElement('button');boton.textContent='Revisar con el servidor';
        boton.onclick=async()=>{if(!navigator.onLine){alert('Recuperá conexión para revisar este cambio.');return;}op.estado='PENDIENTE';delete op.error;await api.actualizarPendiente(op);await api.sincronizarPendientes(token);await actualizar();};li.append(boton);
      }
      $('pendientes').append(li);
    }
  }
  $('sincronizar').onclick=async()=>{await api.sincronizarPendientes(token);await actualizar();};
  $('exportar').onclick=async()=>{
    const pendientes=await api.listarPendientes(u.id),datos=await api.listarDatos('',u.id);
    async function serializar(fila){const copia={...fila};if(copia.body instanceof Blob)copia.body={tipo:'blob',mime:copia.body.type,base64:await base64(copia.body)};if(copia.valor instanceof Blob)copia.valor={tipo:'blob',mime:copia.valor.type,base64:await base64(copia.valor)};else if(copia.valor?.blob instanceof Blob)copia.valor={...copia.valor,blob:{tipo:'blob',mime:copia.valor.blob.type,base64:await base64(copia.valor.blob)}};return copia;}
    function base64(blob){return new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=()=>no(r.error);r.readAsDataURL(blob);});}
    const archivo={formato:'100t-respaldo-offline-v1',usuario_id:u.id,creado_en:new Date().toISOString(),pendientes:await Promise.all(pendientes.map(serializar)),datos:await Promise.all(datos.map(serializar))};
    const url=URL.createObjectURL(new Blob([JSON.stringify(archivo)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='100T-pendientes-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  $('preparar').onclick=async()=>{
    const boton=$('preparar');boton.disabled=true;
    try{
      if(!navigator.onLine)throw Error('Conectate a internet para descargar una copia actualizada.');
      if((await api.listarPendientes(u.id)).length){await api.sincronizarPendientes(token);if((await api.listarPendientes(u.id)).length)throw Error('Hay cambios pendientes. Sincronizalos o revisá el conflicto antes de descargar otra copia.');}
      const roles=(u.roles || [u.rol]).map(r=>String(r).toUpperCase()),operador=roles.some(r=>['ADMINISTRADOR','EMPLEADO'].includes(r));
      const rutas=['/planillas/inicial','/planillas','/tareas/inicial','/tareas'];
      if(operador)rutas.push('/compras/inicial','/compras/planillas','/compras/tareas','/compras/dia-compras','/entregas','/entregas/fotos/planillas-entregadas','/recorridos/'+new Date(Date.now()-3*3600000).toISOString().slice(0,10));
      const errores=[];
      async function descargar(ruta){
        const r=await fetch(ruta,{cache:'no-store',headers:{Authorization:'Bearer '+token}});
        const d=await r.json();if(!r.ok)throw Error(detalle(d.detail || r.status));
        await api.guardarDato('respuesta:'+ruta,d,u.id);return d;
      }
      const prefijos={'/planillas':id=>`/planillas/${id}`,'/tareas':id=>`/tareas/${id}`,'/compras/planillas':id=>`/compras/planillas/${id}`,'/compras/tareas':id=>`/compras/tareas/${id}`,'/entregas':id=>`/entregas/${id}`};
      for(const ruta of rutas){
        $('estado').textContent='Descargando: '+ruta;
        try{
          const d=await descargar(ruta);
          if(prefijos[ruta])for(let i=0;i<d.length;i+=4){
            $('estado').textContent=`Descargando ${ruta}: ${Math.min(i+4,d.length)} de ${d.length}`;
            await Promise.all(d.slice(i,i+4).map(f=>descargar(prefijos[ruta](f.id))));
          }
        }catch(e){errores.push(ruta+': '+e.message);}
      }
      if(errores.length)throw Error('Preparación incompleta. Reintentá antes de salir:\n'+errores.join('\n'));
      if(!('serviceWorker' in navigator))throw Error('Este navegador no permite preparar la aplicación sin conexión. Usá Chrome o Safari actualizado.');
      const registro=await navigator.serviceWorker.ready;await registro.update();
      const trabajador=registro.installing || registro.waiting;
      if(trabajador && !['installed','activated'].includes(trabajador.state))await new Promise((ok,no)=>{
        trabajador.addEventListener('statechange',()=>{if(['installed','activated'].includes(trabajador.state))ok();else if(trabajador.state==='redundant')no(Error('No se pudo descargar la aplicación completa. Reintentá con conexión.'));});
      });
      if(!(await caches.match('/app/sin-conexion.html')))throw Error('Todavía no se descargaron todas las pantallas. Reintentá la preparación con conexión.');
      await navigator.storage?.persist?.();
      if($('recordar').checked)localStorage.setItem('100t-sesion-dispositivo',JSON.stringify({token,usuario:u}));
      const ahora=new Date().toISOString();await api.guardarDato('preparado_en',ahora,u.id);
      $('estado').textContent='Datos descargados: '+new Date(ahora).toLocaleString('es-AR')+'. Podés trabajar sin conexión con esta copia.';
    }catch(e){$('estado').textContent=e.message;}finally{boton.disabled=false;}
  };
  api.leerDato('preparado_en',u.id).then(fecha=>{if(fecha)$('estado').textContent='Última preparación: '+new Date(fecha).toLocaleString('es-AR');});
  window.addEventListener('100t:cambios-pendientes',actualizar);actualizar();
})();
