(() => {
  const $=id=>document.getElementById(id);let revision=0;
  async function cargar(){
    const actual=++revision,select=$('planilla-fotos-dia');
    select.disabled=true;$('abrir-fotos-dia').disabled=true;select.replaceChildren();$('mensaje-fotos-dia').textContent='Buscando planillas con entregas registradas...';
    try{
      const fecha=$('fecha-fotos-entrega').value;
      const d=await window.offline100t.solicitarApi('/entregas/fotos/planillas-entregadas'+(fecha?'?fecha='+encodeURIComponent(fecha):''),{},sessionStorage.getItem('token'));
      if(actual!==revision)return;
      $('fecha-fotos-entrega').value=d.fecha;
      select.add(new Option(d.planillas.length?'Elegí una planilla':'No hubo entregas registradas ese día',''));
      for(const p of d.planillas)select.add(new Option(`Planilla N.º ${p.id} · ${p.obra}`,p.id));
      select.disabled=!d.planillas.length;$('mensaje-fotos-dia').textContent=d.planillas.length?'Elegí la planilla para consultar o agregar sus fotos.':'Para fotos de planillas anteriores, entrá en Planillas existentes.';
      if(d.copia_local)$('mensaje-fotos-dia').textContent=d.planillas.length?'Se muestran las entregas guardadas en este teléfono para ese día.':'No hay una copia local de las entregas de ese día. Descargalas con conexión.';
    }catch(e){if(actual===revision)$('mensaje-fotos-dia').textContent=e.message;}
  }
  $('fecha-fotos-entrega').addEventListener('change',cargar);
  $('planilla-fotos-dia').addEventListener('change',()=>$('abrir-fotos-dia').disabled=!$('planilla-fotos-dia').value);
  $('abrir-fotos-dia').onclick=()=>{const id=Number($('planilla-fotos-dia').value);if(Number.isInteger(id)&&id>0)location.href=`/app/fotos_planilla.html?planilla=${id}&volver=entregas`;};
  window.cargarPlanillasFotosDia=cargar;if(sessionStorage.getItem('token'))cargar();
})();
