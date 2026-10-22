(() => {
  const $=id=>document.getElementById(id);
  let pid=null,generacion=0,pendientes=[],urls=[],subiendo=false;
  const sesion=sessionStorage.getItem('token');
  function aviso(texto){$('mensaje-fotos').textContent=texto;}
  async function api(ruta,op={}){
    const r=await fetch(ruta,{...op,cache:'no-store',headers:{...op.headers,Authorization:'Bearer '+sesion}});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw Error(typeof d.detail==='string'?d.detail:'No se pudo completar la operación.');}
    return r;
  }
  function liberar(){urls.forEach(URL.revokeObjectURL);urls=[];}
  function pintarPendientes(){
    $('fotos-pendientes').replaceChildren();
    pendientes.forEach(f=>{
      const caja=document.createElement('figure'),img=document.createElement('img'),quitar=document.createElement('button');
      img.src=f.url;img.alt='Foto lista para subir';
      quitar.type='button';quitar.textContent='Quitar';quitar.onclick=()=>{if(subiendo)return;URL.revokeObjectURL(f.url);pendientes=pendientes.filter(x=>x!==f);pintarPendientes();};
      caja.append(img,quitar);$('fotos-pendientes').append(caja);
    });
    $('subir-fotos').disabled=!pendientes.length||subiendo;
    $('subir-fotos').textContent=`Subir fotos (${pendientes.length})`;
  }
  async function comprimir(file){
    if(file.size>40*1024*1024)throw Error('La imagen original supera 40 MB. Elegí una más pequeña.');
    let imagen;
    try{imagen=await createImageBitmap(file,{imageOrientation:'from-image'});}
    catch{
      const u=URL.createObjectURL(file);
      try{imagen=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=()=>rej(Error('No se pudo leer esta foto. Usá JPG, PNG o WebP.'));i.src=u;});}
      finally{URL.revokeObjectURL(u);}
    }
    const w=imagen.width,h=imagen.height,escala=Math.min(1,1280/Math.max(w,h));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(w*escala));canvas.height=Math.max(1,Math.round(h*escala));
    const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(imagen,0,0,canvas.width,canvas.height);imagen.close?.();
    let blob;
    for(const calidad of [.78,.68,.58,.48]){blob=await new Promise(res=>canvas.toBlob(res,'image/jpeg',calidad));if(blob&&blob.size<=450*1024)break;}
    if(!blob||blob.size>450*1024)throw Error('No se pudo reducir esta imagen. Elegí otra foto.');
    canvas.width=canvas.height=1;
    return blob;
  }
  async function seleccionar(evento){
    const archivos=[...evento.target.files];evento.target.value='';if(!pid||subiendo)return;
    const actual=generacion;aviso('Preparando fotos...');
    for(const archivo of archivos){
      try{const blob=await comprimir(archivo);if(actual!==generacion)return;pendientes.push({id:crypto.randomUUID(),blob,url:URL.createObjectURL(blob)});pintarPendientes();}
      catch(e){aviso(e.message);return;}
    }
    aviso('Revisá las fotos y tocá Subir fotos para guardarlas.');
  }
  async function cargar(){
    const actual=generacion,planilla=pid;liberar();$('fotos-guardadas').replaceChildren();
    const listado=await (await api(`/entregas/${planilla}/fotos`)).json();
    if(actual!==generacion)return;
    if(!listado.length){$('fotos-guardadas').textContent='Todavía no hay fotos de esta planilla.';return;}
    for(const f of listado){
      if(actual!==generacion)return;
      const caja=document.createElement('figure'),boton=document.createElement('button'),img=document.createElement('img'),pie=document.createElement('figcaption');
      boton.type='button';boton.className='foto-abrir';boton.setAttribute('aria-label','Ampliar foto de entrega');
      img.alt='Foto de entrega';
      const fecha=new Date(f.creada_en.replace(' ','T'));pie.textContent=`${f.usuario} · ${Number.isNaN(fecha.getTime())?f.creada_en:fecha.toLocaleString('es-AR')}`;
      boton.append(img);caja.append(boton,pie);$('fotos-guardadas').append(caja);
      try{const blob=await (await api(`/entregas/${planilla}/fotos/${f.id}?miniatura=true`)).blob();if(actual!==generacion)return;const u=URL.createObjectURL(blob);urls.push(u);img.src=u;}
      catch{img.alt='No se pudo cargar la vista previa';}
      boton.onclick=async()=>{
        try{const blob=await (await api(`/entregas/${planilla}/fotos/${f.id}`)).blob();const u=URL.createObjectURL(blob);$('foto-ampliada').src=u;$('foto-datos').textContent=pie.textContent;$('dialogo-foto').showModal();$('dialogo-foto').addEventListener('close',()=>{URL.revokeObjectURL(u);$('foto-ampliada').removeAttribute('src');},{once:true});}
        catch(e){aviso(e.message);}
      };
    }
  }
  window.fotosEntrega={
    abrir(id){if(subiendo||(pid===id&&pendientes.length))return;generacion++;pid=id;pendientes.forEach(f=>URL.revokeObjectURL(f.url));pendientes=[];pintarPendientes();aviso('Cargando fotos...');cargar().then(()=>aviso('')).catch(e=>aviso(e.message));}
  };
  $('camara-foto').onchange=seleccionar;$('galeria-foto').onchange=seleccionar;
  $('abrir-camara').onclick=()=>$('camara-foto').click();$('abrir-galeria').onclick=()=>$('galeria-foto').click();
  $('cerrar-foto').onclick=()=>$('dialogo-foto').close();
  $('subir-fotos').onclick=async()=>{
    if(subiendo||!pendientes.length)return;
    subiendo=true;pintarPendientes();
    const controles=[...document.querySelectorAll('main button,main input')].map(e=>[e,e.disabled]);controles.forEach(([e])=>e.disabled=true);
    let cantidad=0;
    try{
      for(const f of [...pendientes]){
        aviso(`Subiendo foto ${cantidad+1}...`);
        await api(`/entregas/${pid}/fotos/${f.id}`,{method:'PUT',headers:{'Content-Type':'image/jpeg'},body:f.blob});
        pendientes=pendientes.filter(x=>x!==f);URL.revokeObjectURL(f.url);cantidad++;
      }
      await cargar();aviso(`${cantidad} foto(s) guardada(s) en esta planilla.`);
    }catch(e){aviso(`${cantidad} foto(s) confirmada(s). ${e.message} Las pendientes quedan disponibles para reintentar sin duplicarlas.`);}
    finally{subiendo=false;controles.forEach(([e,valor])=>e.disabled=valor);pintarPendientes();}
  };
  $('volver-planillas').addEventListener('click',e=>{
    if(subiendo||(pendientes.length&&!confirm('Hay fotos sin subir. ¿Descartarlas y volver?'))){e.stopImmediatePropagation();return;}
    generacion++;pendientes.forEach(f=>URL.revokeObjectURL(f.url));pendientes=[];liberar();
  },true);
  window.addEventListener('beforeunload',e=>{if(pendientes.length){e.preventDefault();e.returnValue='';}});
})();
