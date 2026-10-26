(() => {
 const $=id=>document.getElementById(id),token=sessionStorage.getItem('token');if(!token){location.replace('/app/');return;}
 let cats=null,preview=null,ocupado=false,operacion=null,archivoLeido=null;
 const campos=['cantidad','descripcion','unidad','area','presentacion','observaciones'];
 const etiquetas={cantidad:'Cantidad a pedir',descripcion:'Descripción / material',unidad:'Unidad',area:'Área',presentacion:'Presentación',observaciones:'Observaciones'};
 function mensaje(t){$('mensaje').textContent=t;}
 function bloquear(v){ocupado=v;document.querySelectorAll('main button,main input,main select,main textarea').forEach(e=>e.disabled=v);$('confirmar').disabled=v||!preview?.filas.length;}
 async function api(ruta,op={}){
  if(!navigator.onLine)throw Error('Conectate a internet para importar. Si ya intentaste guardar, conservá esta vista y reintentá.');
  const r=await fetch(ruta,{...op,cache:'no-store',headers:{...op.headers,Authorization:'Bearer '+token}}),d=await r.json();
  if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'No se pudo completar la importación.');return d;
 }
 function catalogos(d){
  cats=d;$('crear-nuevos').parentElement.hidden=!d.puede_crear_articulos;const anterior=$('obra').value || new URLSearchParams(location.search).get('obra');
  $('obra').replaceChildren(new Option('Elegí la obra',''));for(const o of d.obras)$('obra').add(new Option(o.nombre,o.id));
  if(d.obras.some(o=>String(o.id)===anterior))$('obra').value=anterior;
  $('fecha').textContent='Fecha de salida de la nueva planilla: '+d.fecha_compra;
 }
 async function leer(manual=false){
  const archivo=$('archivo').files[0]||archivoLeido;if(!archivo||ocupado)return mensaje('Elegí un archivo .xlsx.');
  if(!archivo.name.toLowerCase().endsWith('.xlsx')||archivo.size>8*1024*1024)return mensaje('Elegí un .xlsx de hasta 8 MB.');
  if(preview&&!confirm('Se reemplazará la vista previa y sus correcciones. Todavía no se guardó ninguna planilla. ¿Continuar?'))return;
  bloquear(true);mensaje('Leyendo archivo...');
  try{
   const params=new URLSearchParams();
   if(manual){params.set('hoja',$('hoja').value);params.set('encabezado',$('encabezado').value);const mapa={};for(const campo of campos)mapa[campo]=Number($('col-'+campo).value);params.set('columnas',JSON.stringify(mapa));}
   else if($('hoja').value)params.set('hoja',$('hoja').value);
   const d=await api('/importar-excel/leer'+(params.size?'?'+params:''),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:archivo});
   preview=d;archivoLeido=archivo;operacion=null;catalogos(d.catalogos);$('crear-nuevos').checked=false;
   $('mapeo').hidden=false;$('hoja').replaceChildren();for(const h of d.hojas)$('hoja').add(new Option(h.nombre+(h.oculta?' (oculta)':''),h.nombre));$('hoja').value=d.hoja;$('encabezado').value=d.encabezado;
   $('columnas').replaceChildren();for(const campo of campos){const label=document.createElement('label');label.textContent=etiquetas[campo];const select=document.createElement('select');select.id='col-'+campo;select.add(new Option('No usar',0));for(const c of d.opciones_columnas)select.add(new Option(c.nombre,c.id));select.value=d.columnas[campo]||0;label.append(select);$('columnas').append(label);}
   $('avisos').textContent=d.avisos.join('\n');$('avisos').hidden=!d.avisos.length;pintar();mensaje('Revisá los materiales, áreas y artículos. Todavía no se guardó nada.');
  }catch(e){preview=null;$('filas').replaceChildren();mensaje(e.message);}finally{bloquear(false);}
 }
 function resumen(){
  const elegidas=preview.filas.filter(f=>f.usar),nuevos=elegidas.filter(f=>f.crear_nuevo).length;
  $('resumen').textContent=`${elegidas.length} solicitudes seleccionadas · ${nuevos} artículos nuevos`;
 }
 function pintar(){
  $('filas').replaceChildren();let abiertas=0;
  preview.filas.forEach((f,i)=>{
   const detalles=document.createElement('details'),sum=document.createElement('summary'),incluir=document.createElement('input'),texto=document.createElement('span');incluir.type='checkbox';incluir.checked=f.usar;
   const actualizar=()=>{texto.textContent=` Fila ${f.fila_excel} · ${f.descripcion} · ${f.cantidad || '?'} ${f.unidad} · Área: ${cats.areas.find(a=>a.id===f.area_id)?.nombre || 'REVISAR'}${f.crear_nuevo?' · Nuevo artículo':''}`;detalles.className=f.area_id==null?'fila-error':'';resumen();};
   incluir.onclick=e=>e.stopPropagation();incluir.onchange=()=>{f.usar=incluir.checked;resumen();};sum.append(incluir,texto);detalles.append(sum);$('filas').append(detalles);actualizar();
   let armado=false;
   detalles.addEventListener('toggle',()=>{
    if(!detalles.open||armado)return;armado=true;
    const info=document.createElement('p');info.className='advertencia';info.textContent='Área del Excel: '+(f.area_original || 'sin indicar')+'. '+f.problemas.join(' ');detalles.append(info);
    const grid=document.createElement('div');grid.className='grid';detalles.append(grid);
    for(const [campo,titulo] of [['descripcion','Descripción'],['cantidad','Cantidad revisada'],['unidad','Unidad del Excel']]){
      const label=document.createElement('label');label.textContent=titulo;const e=document.createElement('input');e.value=f[campo];if(campo==='cantidad'){e.type='number';e.step='any';e.min='0';}e.oninput=()=>{f[campo]=e.value;f.unidad_confirmada=false;actualizar();};label.append(e);grid.append(label);
    }
    const lArea=document.createElement('label');lArea.textContent='Área del sistema';const area=document.createElement('select');area.add(new Option('Elegí un área',''));for(const a of cats.areas)area.add(new Option(`${a.id} · ${a.nombre}`,a.id));area.value=f.area_id==null?'':f.area_id;area.onchange=()=>{f.area_id=area.value===''?null:Number(area.value);actualizar();};lArea.append(area);grid.append(lArea);
    const lProd=document.createElement('label');lProd.textContent='Artículo del sistema';const producto=document.createElement('select');producto.add(new Option('Elegí un artículo',''));if(cats.puede_crear_articulos)producto.add(new Option('Crear artículo nuevo con la descripción y unidad indicadas','nuevo'));for(const p of cats.productos)producto.add(new Option(`${p.nombre} [${p.unidad}]`,p.id));producto.value=f.crear_nuevo?'nuevo':(f.producto_id??'');producto.onchange=()=>{f.crear_nuevo=producto.value==='nuevo';f.producto_id=producto.value&&producto.value!=='nuevo'?Number(producto.value):null;f.unidad_confirmada=false;actualizar();};lProd.append(producto);grid.append(lProd);
    const lUnidad=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=f.unidad_confirmada;check.onchange=()=>f.unidad_confirmada=check.checked;lUnidad.append(check,document.createTextNode(' Revisé la cantidad si la unidad del artículo es diferente'));detalles.append(lUnidad);
    for(const [campo,titulo] of [['presentacion','Presentación / empaque'],['observaciones','Observaciones']]){const l=document.createElement('label');l.textContent=titulo;const e=document.createElement('textarea');e.value=f[campo];e.maxLength=1000;e.oninput=()=>f[campo]=e.value;l.append(e);detalles.append(l);}
    const duplicar=document.createElement('button');duplicar.type='button';duplicar.className='secundario';duplicar.textContent='Duplicar para otra área (revisar cantidades)';duplicar.onclick=()=>{preview.filas.push({...structuredClone(f),cantidad:'',area_id:null,usar:true,problemas:['División manual: ajustá las cantidades para no repetir el total.']});pintar();};detalles.append(duplicar);
   });
   if(f.area_id==null&&abiertas++<3)detalles.open=true;
  });resumen();
 }
 $('leer').onclick=()=>leer(false);$('aplicar-mapeo').onclick=()=>leer(true);
 $('hoja').onchange=()=>leer(false);
 $('archivo').onchange=()=>{if(preview&&!confirm('¿Descartar la vista previa para elegir otro archivo?')){$('archivo').value='';return;}preview=null;archivoLeido=null;operacion=null;$('hoja').replaceChildren();$('mapeo').hidden=true;$('filas').replaceChildren();$('confirmar').disabled=true;};
 $('confirmar').onclick=async()=>{
  if(ocupado||!preview)return;const filas=preview.filas.filter(f=>f.usar),obra=Number($('obra').value);
  if(!obra||!filas.length)return mensaje('Elegí una obra y al menos un material.');
  for(const f of filas){if(!f.descripcion.trim()||!Number.isFinite(Number(f.cantidad))||Number(f.cantidad)<=0||f.area_id==null||(!f.crear_nuevo&&!f.producto_id))return mensaje(`Revisá la fila ${f.fila_excel}: descripción, cantidad, artículo y área son obligatorios.`);}
  if(filas.some(f=>f.crear_nuevo)&&!$('crear-nuevos').checked)return mensaje('Confirmá la creación de los artículos nuevos marcados.');
  if(!confirm(`¿Crear una planilla NUEVA con ${filas.length} solicitudes para ${cats.obras.find(o=>o.id===obra)?.nombre}, con salida ${cats.fecha_compra}?`))return;
  const cuerpo=JSON.stringify({obra_id:obra,fecha_compra:cats.fecha_compra,archivo:archivoLeido.name,hoja:preview.hoja,confirmar_nuevos:$('crear-nuevos').checked,filas:filas.map(({usar,problemas,...f})=>f)});
  if(!operacion||operacion.cuerpo!==cuerpo)operacion={cuerpo,id:crypto.randomUUID()};bloquear(true);mensaje('Guardando toda la importación...');
  try{const r=await api('/importar-excel/confirmar',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':operacion.id},body:cuerpo});alert(r.mensaje);location.href='/app/planillas.html?planilla='+r.id;}
  catch(e){mensaje(e.message+' La vista previa se conserva; no vuelvas a cargar el mismo archivo para reintentar.');bloquear(false);}
 };
 api('/importar-excel/catalogos').then(d=>{if(!preview)catalogos(d);}).catch(e=>mensaje(e.message));
})();
