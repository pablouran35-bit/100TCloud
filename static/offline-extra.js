/* Datos privados por usuario; fotos comprimidas y cola durable en IndexedDB. */
(() => {
  const api = window.offline100t;
  const usuario = () => JSON.parse(sessionStorage.getItem('usuario') || '{}');
  const aviso = () => window.dispatchEvent(new CustomEvent('100t:cambios-pendientes'));

  async function transaccion(accion) {
    // Abrir primero por la API asegura que existan los almacenes de la versión 1.
    await api.listarPendientes(usuario().id);
    const db = await new Promise((ok, no) => { const r=indexedDB.open('100TComprasLocal',1);r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error); });
    return new Promise((ok,no) => {
      const tx=db.transaction(['pendientes','datos_locales'],'readwrite');
      try { accion(tx.objectStore('pendientes'),tx.objectStore('datos_locales')); }
      catch(e) { tx.abort();db.close();no(e);return; }
      tx.oncomplete=()=>{db.close();aviso();ok();};
      tx.onerror=tx.onabort=()=>{db.close();no(tx.error || Error('No se pudo guardar en el teléfono. Liberá espacio y reintentá.'));};
    });
  }

  api.guardarFoto = async (planilla,id,blob,conBloqueo=false) => {
    if(!conBloqueo && navigator.locks)return navigator.locks.request('100t-operaciones',()=>api.guardarFoto(planilla,id,blob,true));
    const u=usuario();if(!u.id || !(blob instanceof Blob))throw Error('Iniciá sesión antes de guardar fotos.');
    const url=`/entregas/${planilla}/fotos/${id}`, ahora=new Date().toISOString();
    const anteriores=await api.listarPendientes(u.id);
    const op={id,operacion_id:id,usuario_id:u.id,url,method:'PUT',body:blob,content_type:'image/jpeg',estado:'PENDIENTE',orden:Math.max(Date.now(),...anteriores.map(p=>(p.orden || 0)+1)),intentos:0,creado_en:ahora};
    const foto={id,creada_en:ahora,usuario:`${u.nombre || ''} ${u.apellido || ''}`.trim(),pendiente:true};
    await transaccion((pendientes,datos)=>{
      pendientes.put(op);
      const clave=`${u.id}:foto-local:${planilla}:${id}`;
      datos.put({clave,usuario_id:u.id,actualizado_en:ahora,valor:{...foto,blob}});
      datos.delete(`${u.id}:borrador-foto:${planilla}:${id}`);
    });
    if(navigator.onLine)window.dispatchEvent(new CustomEvent('100t:sincronizar-pendientes'));
    return {pendiente:true};
  };

  api.fotosApi = async (ruta,op={}) => {
    const u=usuario(), token=sessionStorage.getItem('token');
    if(op.method==='PUT') {
      const m=ruta.match(/^\/entregas\/(\d+)\/fotos\/([\da-f-]+)$/i);
      if(!m)throw Error('Planilla de fotos inválida.');
      return Response.json(await api.guardarFoto(m[1],m[2],op.body));
    }
    const lista=ruta.match(/^\/entregas\/(\d+)\/fotos$/);
    if(lista) {
      let filas=[];
      try { filas=await api.solicitarApi(ruta,{},token); }
      catch(e) { if(e.status)throw e; }
      const locales=await api.listarDatos(`foto-local:${lista[1]}:`,u.id);
      const pendientes=await api.listarPendientes(u.id), ids=new Set(pendientes.map(p=>p.id));
      const salida=[...filas];
      for(const f of locales) if(!salida.some(r=>r.id===f.valor.id)) {
        const {blob,...meta}=f.valor;salida.push({...meta,pendiente:ids.has(meta.id)});
      }
      return Response.json(salida);
    }
    const img=ruta.match(/^\/entregas\/(\d+)\/fotos\/([\da-f-]+)(?:\?miniatura=true)?$/i);
    if(!img)throw Error('Ruta de foto inválida.');
    const local=await api.leerDato(`foto-local:${img[1]}:${img[2]}`,u.id);
    if(local?.blob)return new Response(local.blob);
    const clave=`imagen:${ruta}`;
    try {
      if(!navigator.onLine)throw Error('Sin conexión');
      const r=await fetch(ruta,{cache:'no-store',headers:{Authorization:'Bearer '+token}});
      if(!r.ok)throw Object.assign(Error('No se pudo consultar la foto.'),{status:r.status});
      const blob=await r.blob();await api.guardarDato(clave,blob,u.id);return new Response(blob);
    }catch(e){
      if(e.status)throw e;
      const blob=await api.leerDato(clave,u.id);if(blob)return new Response(blob);
      throw Error('Esta foto todavía no está descargada en el teléfono. Abrila con conexión para conservar una copia.');
    }
  };

  // Las entregas registradas localmente también deben permitir adjuntar fotos.
  const solicitar=api.solicitarApi.bind(api);
  api.solicitarApi=async (ruta,op={},token='') => {
    let d;
    const esLectura=!op.method || op.method.toUpperCase()==='GET';
    try {
      d=await (!esLectura && navigator.locks
        ? navigator.locks.request('100t-operaciones',()=>solicitar(ruta,op,token))
        : solicitar(ruta,op,token));
    } catch(e) {
      if(!navigator.onLine && /^\/entregas\/fotos\/planillas-entregadas(?:\?|$)/.test(ruta)) {
        const fecha=new URL(ruta,location.origin).searchParams.get('fecha') || new Date(Date.now()-3*3600000).toISOString().slice(0,10);
        d={fecha,planillas:[],copia_local:true};
      } else throw e;
    }
    if(/^\/entregas\/fotos\/planillas-entregadas(?:\?|$)/.test(ruta)) {
      const fecha=new URL(ruta,location.origin).searchParams.get('fecha') || d.fecha;
      const pendientes=await api.listarPendientes(usuario().id);
      for(const p of pendientes) {
        const m=p.url.match(/^\/entregas\/(\d+)\/solicitudes$/);
        const dia=new Date(new Date(p.creado_en).getTime()-3*3600000).toISOString().slice(0,10);
        if(m && p.method==='PATCH' && dia===fecha) {
          const detalle=await api.leerDato(`respuesta:/entregas/${m[1]}`,usuario().id);
          if(detalle && !d.planillas.some(r=>String(r.id)===m[1]))d.planillas.push({id:Number(m[1]),obra:detalle.obra});
        }
      }
    }
    return d;
  };

  // Reintentos mientras la aplicación está abierta; también tras volver del bloqueo.
  const sincronizar=()=>{if(navigator.onLine && !document.hidden)api.sincronizarPendientes(sessionStorage.getItem('token')).catch(()=>{});};
  setInterval(sincronizar,30000);
  document.addEventListener('visibilitychange',sincronizar);
  window.addEventListener('focus',sincronizar);
})();
