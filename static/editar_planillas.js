const token=sessionStorage.getItem('token');
const $=id=>document.getElementById(id);
let lista=[], original=null, opciones=null, planillaId=null;
if(!token) location.replace('/app/');
async function api(url,method='GET',body){
  const respuesta=await fetch('/planillas/administracion/edicion'+url,{method,cache:'no-store',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  const datos=await respuesta.json();
  if(!respuesta.ok) throw Error(typeof datos.detail==='string'?datos.detail:'No se pudo completar la operación.');
  return datos;
}
function mensaje(texto){$('mensaje').textContent=texto;}
function mostrarLista(){
  const filtro=$('buscar').value.toLocaleLowerCase(); $('planillas').replaceChildren();
  for(const p of lista.filter(p=>(p.id+' '+p.obra).toLocaleLowerCase().includes(filtro))){
    const opt=document.createElement('option'); opt.value=p.id; opt.textContent=`${p.id} · ${p.obra} · ${p.fecha_compra}`;$('planillas').append(opt);
  }
}
function campo(parent,id,titulo,valor,catalogo=null,tipo='text'){
  const label=document.createElement('label');label.htmlFor=id;label.textContent=titulo;
  const el=document.createElement(catalogo?'select':tipo==='textarea'?'textarea':'input');el.id=id;
  if(catalogo){for(const [key,nombre] of catalogo){const opt=document.createElement('option');opt.value=key??'';opt.textContent=nombre;el.append(opt);}}
  else if(tipo!=='textarea') el.type=tipo;
  el.value=valor??'';parent.append(label,el);return el;
}
async function abrir(id){
  if(!Number.isInteger(Number(id))||Number(id)<1){mensaje('Elegí una planilla.');return;}
  if(original&&!confirm('¿Descartar el borrador y abrir otra planilla?'))return;
  $('editor').hidden=true;original=null;mensaje('Cargando...');
  try{
    const datos=await api('/'+id);original=datos.documento;opciones=datos.opciones;planillaId=Number(id);
    $('titulo').textContent='Planilla N.º '+id;$('cabecera').replaceChildren();$('solicitudes').replaceChildren();
    campo($('cabecera'),'obra_id','Obra',original.obra_id,opciones.obras);
    campo($('cabecera'),'fecha_compra','Fecha de salida',original.fecha_compra,null,'date');
    campo($('cabecera'),'estado','Estado de la planilla',original.estado);
    campo($('cabecera'),'observaciones','Observaciones',original.observaciones,null,'textarea');
    campo($('cabecera'),'estado_aprobacion','Aprobación',original.estado_aprobacion||'PENDIENTE',[['PENDIENTE','PENDIENTE'],['APROBADA','APROBADA']]);
    for(const s of original.solicitudes){
      const grupo=document.createElement('fieldset'),leyenda=document.createElement('legend');leyenda.textContent='Solicitud '+s.id;grupo.append(leyenda);
      const pref='s'+s.id+'_';
      for(const [key,titulo,cat] of [['persona_id','Solicitante',opciones.personas],['producto_id','Artículo',opciones.productos],['area_id','Área',opciones.areas],['proveedor_id','Proveedor',[[null,'Sin proveedor'],...opciones.proveedores]]])campo(grupo,pref+key,titulo,s[key],cat);
      campo(grupo,pref+'cantidad','Cantidad',s.cantidad).inputMode='decimal';
      campo(grupo,pref+'fecha_solicitud','Fecha y hora de solicitud (AAAA-MM-DD HH:MM:SS y zona horaria)',s.fecha_solicitud);
      campo(grupo,pref+'estado','Estado',s.estado);
      campo(grupo,pref+'observaciones','Observaciones',s.observaciones,null,'textarea');$('solicitudes').append(grupo);
    }
    $('editor').hidden=false;mensaje('');
  }catch(e){mensaje(e.message);}
}
$('buscar').addEventListener('input',mostrarLista);
$('abrir').onclick=()=>abrir($('planillas').value);
$('abrir-numero').onclick=()=>abrir($('numero').value);
$('cancelar').onclick=()=>{if(confirm('¿Descartar los cambios sin guardar?')){original=null;$('editor').hidden=true;mensaje('Cambios descartados.');}};
$('editor').onsubmit=async e=>{
  e.preventDefault();if(!original)return;
  const cambios=structuredClone(original);
  for(const key of ['obra_id','fecha_compra','estado','observaciones','estado_aprobacion'])cambios[key]=$(key).value;
  cambios.obra_id=Number(cambios.obra_id);
  for(const s of cambios.solicitudes){for(const key of ['persona_id','producto_id','area_id','proveedor_id','cantidad','fecha_solicitud','estado','observaciones']){
    const valor=$('s'+s.id+'_'+key).value;s[key]=key.endsWith('_id')?(valor?Number(valor):null):valor;
  }}
  if(!confirm('¿Guardar todas las correcciones de esta planilla?'))return;
  $('guardar').disabled=true;mensaje('Guardando...');
  try{await api('/'+planillaId,'PUT',{anterior:original,cambios});original=null;$('editor').hidden=true;lista=await api('');mostrarLista();mensaje('Planilla guardada. Los cambios quedaron registrados.');}
  catch(e){mensaje(e.message);}
  finally{$('guardar').disabled=false;}
};
if(token)api('').then(datos=>{lista=datos;mostrarLista();}).catch(e=>mensaje(e.message));
