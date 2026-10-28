(() => {
  const params=new URLSearchParams(location.search),id=Number(params.get('planilla'));
  const volver=document.getElementById('volver-fotos');
  volver.href=params.get('volver')==='planillas'?`/app/planillas.html?planilla=${id}`:'/app/entregas.html';
  volver.textContent=params.get('volver')==='planillas'?'← Volver a la planilla':'← Volver a Entregas';
  const token=sessionStorage.getItem('token');
  if(!token){location.replace('/app/');return;}
  if(!Number.isInteger(id)||id<1){document.getElementById('info-fotos-planilla').textContent='Elegí una planilla válida desde Entregas o Planillas existentes.';document.getElementById('fotos-planilla').hidden=true;return;}
  document.getElementById('titulo-fotos-planilla').textContent=`Fotos de entrega · Planilla N.º ${id}`;
  (async()=>{
    try{
      const d=await window.offline100t.solicitarApi(`/entregas/${id}`,{},token);
      document.getElementById('titulo-fotos-planilla').textContent=`Planilla N.º ${d.id} · ${d.obra}`;
      document.getElementById('info-fotos-planilla').textContent='Las fotos pertenecen a esta planilla completa.';
      await window.fotosEntrega.abrir(id);
    }catch(e){
      if ([401,403,404].includes(e.status)) {
        document.getElementById('info-fotos-planilla').textContent=e.message;
        document.getElementById('fotos-planilla').hidden=true;
        return;
      }
      document.getElementById('info-fotos-planilla').textContent='No se pudieron consultar los datos de esta planilla. Podés sacar o elegir fotos y guardarlas en este teléfono; se enviarán cuando vuelva la conexión.';
      await window.fotosEntrega.abrir(id);
    }
  })();
})();
