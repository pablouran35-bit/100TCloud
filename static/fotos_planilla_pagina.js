(() => {
  const params=new URLSearchParams(location.search),id=Number(params.get('planilla'));
  const volver=document.getElementById('volver-fotos');
  volver.href=params.get('volver')==='planillas'?`/app/planillas.html?planilla=${id}`:'/app/entregas.html';
  volver.textContent=params.get('volver')==='planillas'?'← Volver a la planilla':'← Volver a Entregas';
  const token=sessionStorage.getItem('token');
  if(!token){location.replace('/app/');return;}
  if(!Number.isInteger(id)||id<1){document.getElementById('info-fotos-planilla').textContent='Elegí una planilla válida desde Entregas o Planillas existentes.';document.getElementById('fotos-planilla').hidden=true;return;}
  (async()=>{
    try{
      const r=await fetch(`/entregas/${id}`,{cache:'no-store',headers:{Authorization:'Bearer '+token}}),d=await r.json();
      if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'No se pudo consultar la planilla.');
      document.getElementById('titulo-fotos-planilla').textContent=`Planilla N.º ${d.id} · ${d.obra}`;
      document.getElementById('info-fotos-planilla').textContent='Las fotos pertenecen a esta planilla completa.';
      window.fotosEntrega.abrir(id);
    }catch(e){document.getElementById('info-fotos-planilla').textContent=e.message;document.getElementById('fotos-planilla').hidden=true;}
  })();
})();
