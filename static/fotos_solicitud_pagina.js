(async()=>{
 const p=new URLSearchParams(location.search),original=p.get('solicitud') || '',planilla=p.get('planilla') || '';
 const valido=id=>/^([1-9]\d*|offline-[0-9a-f-]+)$/.test(id);
 if(!sessionStorage.getItem('token')){location.replace('/app/');return;}
 if(!valido(original)){document.getElementById('fotos-planilla').hidden=true;document.getElementById('info-fotos-planilla').textContent='Elegí una solicitud válida.';return;}
 const uid=JSON.parse(sessionStorage.getItem('usuario') || '{}').id;
 const id=(await offline100t.resolverRuta('/solicitudes/'+original,uid)).split('/').pop();
 const volver=document.getElementById('volver-fotos');volver.href=p.get('volver')==='compras'?'/app/compras.html':(valido(planilla)?'/app/planillas.html?planilla='+encodeURIComponent(planilla):'/app/planillas.html');volver.textContent='← Volver';
 document.getElementById('titulo-fotos-planilla').textContent='Fotos · Solicitud N.º '+id;
 document.getElementById('info-fotos-planilla').textContent='Imágenes de referencia del material solicitado. Podés sacar fotos o elegirlas de la galería.';
 window.fotosEntrega.abrir(id);
})();