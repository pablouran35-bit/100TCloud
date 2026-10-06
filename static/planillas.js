const token = sessionStorage.getItem("token");
const pantallas = [...document.querySelectorAll(".pantalla")];

let datosIniciales = null;
let planillas = [];
let planillaActual = null;
let solicitudSeleccionada = null;
let pantallaAnteriorDetalle = "pantalla-opciones";

document.getElementById("boton-nueva").disabled = true;
document.getElementById("boton-existente").disabled = true;

if (!token) {
  window.location.replace("/app/");
} else {
  cargarDatosIniciales();
}

async function llamarApi(url, opciones = {}) {
  return window.offline100t.solicitarApi(url, opciones, token);
}

function mostrarPantalla(id) {
  pantallas.forEach((pantalla) => { pantalla.hidden = pantalla.id !== id; });
  document.querySelector("main").scrollTop = 0;
}

function mostrarError(id, texto) {
  const elemento = document.getElementById(id);
  elemento.textContent = texto;
  elemento.style.color = "#b42318";
}

function limpiarMensaje(id) {
  const elemento = document.getElementById(id);
  elemento.textContent = "";
  elemento.style.color = "";
}

function fechaLegible(valor) {
  const fecha = new Date(`${valor}T12:00:00`);
  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  }).format(fecha);
}

async function cargarDatosIniciales() {
  try {
    datosIniciales = await llamarApi("/planillas/inicial");
    document.getElementById("fecha-compra-nueva").textContent = fechaLegible(datosIniciales.fecha_compra_nueva);
    document.getElementById("aviso-contratista").hidden = !datosIniciales.aviso_contratista;
    cargarObras();
    cargarArticulos();
    cargarAreas();
    document.getElementById("boton-existente").disabled = false;
    if (datosIniciales.obras.length === 0) {
      document.getElementById("boton-nueva").disabled = true;
      document.getElementById("mensaje-inicial").textContent = "No tenés obras disponibles para cargar una planilla.";
    } else {
      document.getElementById("boton-nueva").disabled = false;
    }
  } catch (error) {
    mostrarError("mensaje-inicial", error.message);
  }
}

function cargarObras() {
  const selector = document.getElementById("obra-nueva");
  selector.replaceChildren();
  const inicial = document.createElement("option");
  inicial.value = "";
  inicial.textContent = "Elegí una obra";
  selector.appendChild(inicial);
  datosIniciales.obras.forEach((obra) => {
    const opcion = document.createElement("option");
    opcion.value = obra.id;
    opcion.textContent = obra.nombre;
    selector.appendChild(opcion);
  });
}

function cargarArticulos() {
  ["articulo-solicitud", "articulo-edicion"].forEach((id) => {
    const campoBusqueda = id === "articulo-solicitud"
      ? "buscar-articulo"
      : "buscar-articulo-edicion";
    rellenarArticulos(id, campoBusqueda);
    document.getElementById(campoBusqueda).addEventListener("input", () => {
      rellenarArticulos(id, campoBusqueda);
    });
  });
}

function rellenarArticulos(idSelector, idBusqueda, idSeleccionado = null) {
  const selector = document.getElementById(idSelector);
  const filtro = normalizar(document.getElementById(idBusqueda).value.trim());
  const productosFiltrados = datosIniciales.productos.filter((producto) =>
    normalizar(producto.nombre).includes(filtro)
  );
  const seleccionado = selector.value;
  selector.replaceChildren();
  const inicial = document.createElement("option");
  inicial.value = "";
  inicial.textContent = productosFiltrados.length ? "Elegí un artículo" : "No se encontraron artículos";
  selector.appendChild(inicial);
  productosFiltrados.forEach((producto) => {
    const opcion = document.createElement("option");
    opcion.value = producto.id;
    opcion.textContent = `${producto.nombre} · ${producto.unidad}`;
    selector.appendChild(opcion);
  });
  const valorSeleccionado = idSeleccionado ?? seleccionado;
  if (productosFiltrados.some((producto) => String(producto.id) === String(valorSeleccionado))) {
    selector.value = valorSeleccionado;
  }
}

function cargarAreas() {
  const selector = document.getElementById("area-solicitud");
  selector.replaceChildren();
  const inicial = document.createElement("option");
  inicial.value = "";
  inicial.textContent = "Elegí un área";
  selector.appendChild(inicial);
  datosIniciales.areas.forEach((area) => {
    const opcion = document.createElement("option");
    opcion.value = area.id;
    opcion.textContent = `${area.id} — ${area.nombre}`;
    selector.appendChild(opcion);
  });
}

function normalizar(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
}

document.getElementById("boton-nueva").addEventListener("click", () => {
  limpiarMensaje("mensaje-nueva");
  mostrarPantalla("pantalla-nueva");
});

document.getElementById("boton-existente").addEventListener("click", async () => {
  mostrarPantalla("pantalla-existente");
  await cargarPlanillas();
});

document.querySelectorAll("[data-volver]").forEach((boton) => {
  boton.addEventListener("click", () => mostrarPantalla(boton.dataset.volver));
});

document.getElementById("boton-crear-planilla").addEventListener("click", async () => {
  const obraId = Number(document.getElementById("obra-nueva").value);
  if (!obraId) {
    mostrarError("mensaje-nueva", "Elegí una obra para continuar.");
    return;
  }
  const boton = document.getElementById("boton-crear-planilla");
  boton.disabled = true;
  boton.textContent = "Creando planilla...";
  limpiarMensaje("mensaje-nueva");
  try {
    const resultado = await llamarApi("/planillas", {
      method: "POST",
      body: JSON.stringify({ obra_id: obraId }),
    });
    pantallaAnteriorDetalle = "pantalla-nueva";
    await abrirPlanilla(resultado.id);
    if (resultado.pendiente) {
      document.getElementById("mensaje-solicitud").textContent = resultado.mensaje;
    } else if (!resultado.creada) {
      document.getElementById("mensaje-solicitud").textContent = resultado.mensaje;
    }
  } catch (error) {
    mostrarError("mensaje-nueva", error.message);
  } finally {
    boton.disabled = false;
    boton.textContent = "Crear planilla";
  }
});

async function cargarPlanillas() {
  const lista = document.getElementById("lista-planillas");
  lista.textContent = "Cargando planillas...";
  limpiarMensaje("mensaje-existente");
  try {
    planillas = await llamarApi("/planillas");
    mostrarPlanillas();
  } catch (error) {
    lista.replaceChildren();
    mostrarError("mensaje-existente", error.message);
  }
}

function mostrarPlanillas() {
  const lista = document.getElementById("lista-planillas");
  lista.replaceChildren();
  const busqueda = normalizar(document.getElementById("buscar-planilla").value.trim());
  const encontradas = planillas.filter((planilla) =>
    normalizar(`${planilla.obra} ${planilla.solicitantes}`).includes(busqueda)
  );
  document.getElementById("cantidad-planillas").textContent =
    encontradas.length === 1 ? "1 planilla" : `${encontradas.length} planillas`;
  if (encontradas.length === 0) {
    lista.textContent = planillas.length
      ? "No hay planillas que coincidan con la búsqueda."
      : "No hay planillas con solicitudes pendientes.";
    return;
  }
  encontradas.forEach((planilla) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "item-planilla";
    const titulo = document.createElement("strong");
    titulo.textContent = `Planilla N.º ${planilla.id} · ${planilla.obra}`;
    const datos = document.createElement("small");
    datos.textContent = `${fechaLegible(planilla.fecha_compra)} · ${planilla.pendientes} pendientes${planilla.solicitantes ? ` · ${planilla.solicitantes}` : ""}`;
    boton.append(titulo, datos);
    boton.addEventListener("click", async () => {
      pantallaAnteriorDetalle = "pantalla-existente";
      await abrirPlanilla(planilla.id);
    });
    lista.appendChild(boton);
  });
}

document.getElementById("buscar-planilla").addEventListener("input", mostrarPlanillas);

async function abrirPlanilla(planillaId) {
  limpiarMensaje("mensaje-solicitud");
  try {
    planillaActual = await llamarApi(`/planillas/${planillaId}`);
    mostrarDetallePlanilla();
    mostrarPantalla("pantalla-detalle");
  } catch (error) {
    mostrarError("mensaje-existente", error.message);
    if (pantallaAnteriorDetalle === "pantalla-nueva") mostrarError("mensaje-nueva", error.message);
  }
}

function mostrarDetallePlanilla() {
  document.getElementById("detalle-titulo").textContent = `Planilla N.º ${planillaActual.id} · ${planillaActual.obra}`;
  document.getElementById("detalle-fecha").textContent = `Fecha de compra: ${fechaLegible(planillaActual.fecha_compra)}`;
  const editable = planillaActual.puede_modificar;
  document.getElementById("aviso-solo-consulta").hidden = editable;
  document.getElementById("bloque-agregar-solicitud").hidden = !editable;

  const lista = document.getElementById("lista-solicitudes");
  lista.replaceChildren();
  if (planillaActual.solicitudes.length === 0) {
    lista.textContent = "Todavía no hay solicitudes en esta planilla.";
    return;
  }
  planillaActual.solicitudes.forEach((solicitud) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "item-solicitud";
    item.textContent = `${solicitud.cantidad} — ${solicitud.producto}`;
    item.setAttribute("aria-label", `Ver ${solicitud.cantidad} de ${solicitud.producto}`);
    item.addEventListener("click", () => abrirDetalleSolicitud(solicitud));
    lista.appendChild(item);
  });
}

const dialogoSolicitud = document.getElementById("dialogo-solicitud");
const vistaSolicitud = document.getElementById("vista-solicitud");
const formularioEditarSolicitud = document.getElementById("formulario-editar-solicitud");

function abrirDetalleSolicitud(solicitud) {
  solicitudSeleccionada = solicitud;
  document.getElementById("mensaje-accion-solicitud").textContent = "";
  document.getElementById("formulario-cancelar-solicitud").hidden = true;
  document.getElementById("detalle-solicitud-titulo").textContent =
    `${solicitud.cantidad} — ${solicitud.producto}`;
  document.getElementById("detalle-solicitud-area").textContent =
    `Área: ${solicitud.area_id} — ${solicitud.area}`;
  document.getElementById("detalle-solicitud-solicitante").textContent =
    `Solicitante: ${solicitud.persona}`;
  document.getElementById("detalle-solicitud-estado").textContent =
    `Estado: ${solicitud.estado}`;
  document.getElementById("detalle-solicitud-observaciones").textContent =
    solicitud.observaciones ? `Observaciones: ${solicitud.observaciones}` : "Sin observaciones";

  const puedeEditar = planillaActual.puede_modificar
    && solicitud.estado.toUpperCase() !== "ENTREGADO"
    && !solicitud.tiene_compras;
  document.getElementById("acciones-solicitud").hidden = !puedeEditar;
  vistaSolicitud.hidden = false;
  formularioEditarSolicitud.hidden = true;
  if (!dialogoSolicitud.open) dialogoSolicitud.showModal();
}

function mostrarEdicionSolicitud() {
  if (!solicitudSeleccionada) return;
  vistaSolicitud.hidden = true;
  formularioEditarSolicitud.hidden = false;
  document.getElementById("mensaje-edicion").textContent = "";
  document.getElementById("buscar-articulo-edicion").value = "";
  rellenarArticulos(
    "articulo-edicion",
    "buscar-articulo-edicion",
    solicitudSeleccionada.producto_id
  );
  document.getElementById("cantidad-edicion").value = solicitudSeleccionada.cantidad;
  document.getElementById("area-edicion").value = solicitudSeleccionada.area_id;
  document.getElementById("observaciones-edicion").value = solicitudSeleccionada.observaciones || "";
}

function cancelarEdicionSolicitud() {
  formularioEditarSolicitud.hidden = true;
  vistaSolicitud.hidden = false;
}

document.getElementById("boton-cerrar-solicitud").addEventListener("click", () => dialogoSolicitud.close());
dialogoSolicitud.addEventListener("click", (evento) => {
  if (evento.target === dialogoSolicitud) dialogoSolicitud.close();
});
document.getElementById("boton-modificar-solicitud").addEventListener("click", mostrarEdicionSolicitud);
document.getElementById("boton-cancelar-edicion").addEventListener("click", cancelarEdicionSolicitud);

formularioEditarSolicitud.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!solicitudSeleccionada || !planillaActual) return;
  const datos = {
    producto_id: Number(document.getElementById("articulo-edicion").value),
    area_id: Number(document.getElementById("area-edicion").value),
    cantidad: Number(document.getElementById("cantidad-edicion").value),
    observaciones: document.getElementById("observaciones-edicion").value.trim() || null,
  };
  if (!datos.producto_id || !datos.area_id || !Number.isFinite(datos.cantidad) || datos.cantidad <= 0) {
    document.getElementById("mensaje-edicion").textContent = "Completá artículo, cantidad y área.";
    return;
  }
  const boton = document.getElementById("boton-guardar-edicion");
  boton.disabled = true;
  try {
    const resultado = await llamarApi(`/planillas/${planillaActual.id}/solicitudes/${solicitudSeleccionada.id}`, {
      method: "PUT",
      body: JSON.stringify(datos),
    });
    dialogoSolicitud.close();
    document.getElementById("mensaje-solicitud").textContent = resultado.pendiente
      ? resultado.mensaje : "Solicitud modificada correctamente.";
    document.getElementById("mensaje-solicitud").style.color = "#276341";
    planillaActual = await llamarApi(`/planillas/${planillaActual.id}`);
    mostrarDetallePlanilla();
    if (pantallaAnteriorDetalle === "pantalla-existente") await cargarPlanillas();
  } catch (error) {
    document.getElementById("mensaje-edicion").textContent = error.message;
    document.getElementById("mensaje-edicion").style.color = "#b42318";
  } finally {
    boton.disabled = false;
  }
});

document.getElementById("boton-cancelar-solicitud").addEventListener("click", () => {
  if (!solicitudSeleccionada || !planillaActual) return;
  document.getElementById("motivo-cancelacion").value = "";
  document.getElementById("mensaje-accion-solicitud").textContent =
    "La solicitud se conservará en el historial y dejará de aparecer en Planillas.";
  document.getElementById("formulario-cancelar-solicitud").hidden = false;
  document.getElementById("motivo-cancelacion").focus();
});

document.getElementById("boton-volver-cancelacion").addEventListener("click", () => {
  document.getElementById("formulario-cancelar-solicitud").hidden = true;
  document.getElementById("mensaje-accion-solicitud").textContent = "";
});

document.getElementById("formulario-cancelar-solicitud").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!solicitudSeleccionada || !planillaActual) return;
  const motivo = document.getElementById("motivo-cancelacion").value.trim();
  if (motivo.length < 3) {
    document.getElementById("mensaje-accion-solicitud").textContent = "Escribí el motivo de la cancelación.";
    return;
  }
  const boton = document.getElementById("boton-confirmar-cancelacion");
  boton.disabled = true;
  try {
    const resultado = await llamarApi(`/planillas/${planillaActual.id}/solicitudes/${solicitudSeleccionada.id}/cancelar`, {
      method: "PATCH",
      body: JSON.stringify({ motivo }),
    });
    dialogoSolicitud.close();
    document.getElementById("mensaje-solicitud").textContent = resultado.pendiente
      ? resultado.mensaje : "Solicitud cancelada; ya no aparece en la planilla.";
    document.getElementById("mensaje-solicitud").style.color = "#276341";
    planillaActual = await llamarApi(`/planillas/${planillaActual.id}`);
    mostrarDetallePlanilla();
    if (pantallaAnteriorDetalle === "pantalla-existente") await cargarPlanillas();
  } catch (error) {
    const mensaje = document.getElementById("mensaje-accion-solicitud");
    mensaje.textContent = error.message;
    mensaje.style.color = "#b42318";
  } finally {
    boton.disabled = false;
  }
});

document.getElementById("boton-volver-detalle").addEventListener("click", async () => {
  if (pantallaAnteriorDetalle === "pantalla-existente") await cargarPlanillas();
  mostrarPantalla(pantallaAnteriorDetalle);
});

document.getElementById("formulario-solicitud").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const productoId = Number(document.getElementById("articulo-solicitud").value);
  const areaId = Number(document.getElementById("area-solicitud").value);
  const cantidad = Number(document.getElementById("cantidad-solicitud").value);
  if (!productoId || !areaId || !Number.isFinite(cantidad) || cantidad <= 0) {
    mostrarError("mensaje-solicitud", "Completá artículo, cantidad y área para guardar.");
    return;
  }
  const boton = document.getElementById("boton-agregar-solicitud");
  boton.disabled = true;
  boton.textContent = "Guardando...";
  try {
    const resultado = await llamarApi(`/planillas/${planillaActual.id}/solicitudes`, {
      method: "POST",
      body: JSON.stringify({
        producto_id: productoId,
        area_id: areaId,
        cantidad,
        observaciones: document.getElementById("observaciones-solicitud").value.trim() || null,
      }),
    });
    evento.target.reset();
    document.getElementById("buscar-articulo").value = "";
    rellenarArticulos("articulo-solicitud", "buscar-articulo");
    document.getElementById("mensaje-solicitud").textContent = resultado.pendiente
      ? resultado.mensaje : "Solicitud agregada a la planilla.";
    document.getElementById("mensaje-solicitud").style.color = "#276341";
    planillaActual = await llamarApi(`/planillas/${planillaActual.id}`);
    mostrarDetallePlanilla();
    if (pantallaAnteriorDetalle === "pantalla-existente") await cargarPlanillas();
  } catch (error) {
    mostrarError("mensaje-solicitud", error.message);
  } finally {
    boton.disabled = false;
    boton.textContent = "Agregar solicitud";
  }
});

window.addEventListener("100t:recargar-datos", async () => {
  if (planillaActual) await abrirPlanilla(planillaActual.id);
  if (document.getElementById("pantalla-existente").hidden === false) await cargarPlanillas();
});
