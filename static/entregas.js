const token = sessionStorage.getItem("token");
const listaPlanillas = document.getElementById("lista-planillas");
const listaSolicitudes = document.getElementById("lista-solicitudes");
const vistaPlanillas = document.getElementById("vista-planillas");
const vistaSolicitudes = document.getElementById("vista-solicitudes");
const dialogoHistorial = document.getElementById("dialogo-historial");

let planillas = [];
let planillaActual = null;

if (!token) {
  window.location.replace("/app/");
} else {
  cargarPlanillas();
}

async function llamarApi(url, opciones = {}) {
  return window.offline100t.solicitarApi(url, opciones, token);
}

function mostrarMensaje(id, texto, error = false) {
  const elemento = document.getElementById(id);
  elemento.textContent = texto;
  elemento.style.color = error ? "#b42318" : "";
}

function fechaLegible(valor) {
  if (!valor) return "Sin fecha";
  const fecha = new Date(`${String(valor).slice(0, 10)}T12:00:00`);
  return new Intl.DateTimeFormat("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(fecha);
}

async function cargarPlanillas() {
  listaPlanillas.textContent = "Cargando planillas...";
  try {
    planillas = await llamarApi("/entregas");
    mostrarPlanillas();
  } catch (error) {
    listaPlanillas.replaceChildren();
    mostrarMensaje("mensaje-planillas", error.message, true);
  }
}

function mostrarPlanillas() {
  listaPlanillas.replaceChildren();
  mostrarMensaje("mensaje-planillas", "");
  document.getElementById("cantidad-planillas").textContent =
    planillas.length === 1 ? "1 planilla" : `${planillas.length} planillas`;
  if (!planillas.length) {
    listaPlanillas.textContent = "No hay solicitudes compradas disponibles para entregar.";
    return;
  }
  planillas.forEach((planilla) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "item";
    const titulo = document.createElement("strong");
    titulo.textContent = `Planilla N.º ${planilla.id} · ${planilla.obra}`;
    const datos = document.createElement("small");
    datos.textContent = `${fechaLegible(planilla.fecha_compra)} · ${planilla.disponibles} solicitudes para entregar`;
    boton.append(titulo, datos);
    boton.addEventListener("click", () => abrirPlanilla(planilla.id));
    listaPlanillas.appendChild(boton);
  });
}

async function abrirPlanilla(planillaId) {
  try {
    planillaActual = await llamarApi(`/entregas/${planillaId}`);
    document.getElementById("titulo-planilla").textContent =
      `Planilla N.º ${planillaActual.id} · ${planillaActual.obra}`;
    document.getElementById("fecha-planilla").textContent =
      `Fecha de compra: ${fechaLegible(planillaActual.fecha_compra)}`;
    mostrarSolicitudes();
    vistaPlanillas.hidden = true;
    vistaSolicitudes.hidden = false;
  } catch (error) {
    mostrarMensaje("mensaje-planillas", error.message, true);
  }
}

function solicitudesSeleccionadas() {
  return [...document.querySelectorAll("#lista-solicitudes input[type=checkbox]:checked")]
    .map((casilla) => Number(casilla.value));
}

function actualizarSeleccion() {
  const cantidad = solicitudesSeleccionadas().length;
  document.getElementById("cantidad-seleccionada").textContent =
    `${cantidad} ${cantidad === 1 ? "solicitud seleccionada" : "solicitudes seleccionadas"}`;
  document.getElementById("boton-registrar-entrega").disabled = cantidad === 0;
}

function mostrarSolicitudes() {
  listaSolicitudes.replaceChildren();
  mostrarMensaje("mensaje-solicitudes", "");
  if (!planillaActual.solicitudes.length) {
    listaSolicitudes.textContent = "No quedan solicitudes disponibles para entregar en esta planilla.";
    actualizarSeleccion();
    return;
  }
  planillaActual.solicitudes.forEach((solicitud) => {
    const fila = document.createElement("div");
    fila.className = "fila-solicitud";
    const etiqueta = document.createElement("label");
    etiqueta.className = "solicitud-entrega";
    const casilla = document.createElement("input");
    casilla.type = "checkbox";
    casilla.value = solicitud.id;
    casilla.addEventListener("change", actualizarSeleccion);
    const contenido = document.createElement("span");
    const nombre = document.createElement("strong");
    nombre.textContent = `${solicitud.cantidad} — ${solicitud.producto}`;
    const estado = document.createElement("small");
    estado.textContent = `${solicitud.estado}${solicitud.area ? ` · Área ${solicitud.area_id}: ${solicitud.area}` : ""}`;
    const observaciones = document.createElement("small");
    observaciones.textContent = solicitud.observaciones ? `Observaciones: ${solicitud.observaciones}` : "Sin observaciones";
    contenido.append(nombre, estado, observaciones);
    etiqueta.append(casilla, contenido);
    const verHistorial = document.createElement("button");
    verHistorial.type = "button";
    verHistorial.className = "secundario";
    verHistorial.textContent = "Historial";
    verHistorial.addEventListener("click", () => abrirHistorial(solicitud));
    fila.append(etiqueta, verHistorial);
    listaSolicitudes.appendChild(fila);
  });
  actualizarSeleccion();
}

function abrirHistorial(solicitud) {
  document.getElementById("titulo-historial").textContent = `Historial · ${solicitud.producto}`;
  document.getElementById("detalle-solicitud").textContent =
    `${solicitud.cantidad} · ${solicitud.producto} · Solicitud N.º ${solicitud.id}`;
  const lista = document.getElementById("lista-historial");
  lista.replaceChildren();
  if (!solicitud.historial.length) {
    const item = document.createElement("li");
    item.textContent = "No hay movimientos registrados.";
    lista.appendChild(item);
  } else {
    solicitud.historial.forEach((registro) => {
      const item = document.createElement("li");
      item.className = "registro";
      const estado = document.createElement("strong");
      estado.textContent = registro.estado;
      const quien = document.createElement("small");
      quien.textContent = `${registro.fecha_hora} · ${registro.usuario}`;
      const nota = document.createElement("small");
      nota.textContent = registro.observaciones || "Sin observaciones";
      item.append(estado, quien, nota);
      lista.appendChild(item);
    });
  }
  dialogoHistorial.showModal();
}

document.getElementById("boton-seleccionar-todas").addEventListener("click", () => {
  document.querySelectorAll("#lista-solicitudes input[type=checkbox]").forEach((casilla) => {
    casilla.checked = true;
  });
  actualizarSeleccion();
});

document.getElementById("boton-deseleccionar").addEventListener("click", () => {
  document.querySelectorAll("#lista-solicitudes input[type=checkbox]").forEach((casilla) => {
    casilla.checked = false;
  });
  actualizarSeleccion();
});

document.getElementById("boton-registrar-entrega").addEventListener("click", async (evento) => {
  if (!planillaActual) return;
  const ids = solicitudesSeleccionadas();
  if (!ids.length) return;
  if (!window.confirm(`¿Marcar ${ids.length} solicitud(es) como ENTREGADO? Se guardarán en el historial la fecha y tu usuario.`)) return;
  const boton = evento.currentTarget;
  boton.disabled = true;
  try {
    const resultado = await llamarApi(`/entregas/${planillaActual.id}/solicitudes`, {
      method: "PATCH",
      body: JSON.stringify({ solicitud_ids: ids }),
    });
    planillaActual = await llamarApi(`/entregas/${planillaActual.id}`);
    mostrarSolicitudes();
    await cargarPlanillas();
    mostrarMensaje("mensaje-solicitudes", resultado.pendiente
      ? resultado.mensaje : `${resultado.cantidad} solicitud(es) marcada(s) como ENTREGADO.`);
  } catch (error) {
    mostrarMensaje("mensaje-solicitudes", error.message, true);
  } finally {
    boton.disabled = solicitudesSeleccionadas().length === 0;
  }
});

window.addEventListener("100t:recargar-datos", async () => {
  await cargarPlanillas();
  if (planillaActual) await abrirPlanilla(planillaActual.id);
});

document.getElementById("volver-planillas").addEventListener("click", async () => {
  vistaSolicitudes.hidden = true;
  vistaPlanillas.hidden = false;
  await cargarPlanillas();
});

document.querySelectorAll("[data-cerrar]").forEach((boton) => {
  boton.addEventListener("click", () => document.getElementById(boton.dataset.cerrar).close());
});
