const token = sessionStorage.getItem("token");
const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const listaTareas = document.getElementById("lista-tareas");
const campoBusqueda = document.getElementById("buscar-tarea");
const dialogoNueva = document.getElementById("dialogo-nueva-tarea");
const dialogoTarea = document.getElementById("dialogo-tarea");
const formularioNueva = document.getElementById("formulario-nueva-tarea");
const formularioEdicion = document.getElementById("formulario-editar-tarea");

let tareas = [];
let tareaActual = null;

if (!token) {
  window.location.replace("/app/");
} else {
  iniciar();
}

async function llamarApi(url, opciones = {}) {
  return window.offline100t.solicitarApi(url, opciones, token);
}

function mostrarMensaje(id, texto, error = false) {
  const elemento = document.getElementById(id);
  elemento.textContent = texto;
  elemento.style.color = error ? "#b42318" : "";
}

function fechaLocalIso() {
  const hoy = new Date();
  hoy.setMinutes(hoy.getMinutes() - hoy.getTimezoneOffset());
  return hoy.toISOString().slice(0, 10);
}

function fechaLegible(valor) {
  if (!valor) return "Sin fecha";
  const fecha = new Date(`${valor}T12:00:00`);
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  }).format(fecha);
}

function normalizar(valor) {
  return (valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
}

async function iniciar() {
  document.getElementById("solicitante-nueva").value =
    `${usuario.nombre || ""} ${usuario.apellido || ""}`.trim();
  try {
    const inicial = await llamarApi("/tareas/inicial");
    document.getElementById("fecha-nueva").value = inicial.fecha_hoy;
    await cargarTareas();
  } catch (error) {
    mostrarMensaje("mensaje-lista", error.message, true);
  }
}

async function cargarTareas() {
  listaTareas.textContent = "Cargando tareas...";
  mostrarMensaje("mensaje-lista", "");
  try {
    tareas = await llamarApi("/tareas");
    mostrarTareas();
  } catch (error) {
    listaTareas.replaceChildren();
    mostrarMensaje("mensaje-lista", error.message, true);
  }
}

function mostrarTareas() {
  listaTareas.replaceChildren();
  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontradas = tareas.filter((tarea) =>
    normalizar(`${tarea.id} ${tarea.descripcion} ${tarea.solicitante} ${tarea.estado}`).includes(busqueda)
  );
  document.getElementById("cantidad-tareas").textContent =
    encontradas.length === 1 ? "1 tarea" : `${encontradas.length} tareas`;
  if (!encontradas.length) {
    listaTareas.textContent = tareas.length ? "No se encontraron tareas." : "Todavía no hay tareas cargadas.";
    return;
  }
  encontradas.forEach((tarea) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "item-tarea";
    const descripcion = document.createElement("strong");
    descripcion.textContent = tarea.descripcion;
    const datos = document.createElement("small");
    datos.textContent = `Tarea N.º ${tarea.id} · ${tarea.solicitante} · ${fechaLegible(tarea.fecha_solicitud)}`;
    const estado = document.createElement("span");
    estado.className = "estado";
    estado.dataset.estado = tarea.estado;
    estado.textContent = tarea.estado;
    boton.append(descripcion, datos, estado);
    boton.addEventListener("click", () => abrirTarea(tarea.id));
    listaTareas.appendChild(boton);
  });
}

async function abrirTarea(tareaId) {
  try {
    tareaActual = await llamarApi(`/tareas/${tareaId}`);
    mostrarDetalleTarea();
    dialogoTarea.showModal();
  } catch (error) {
    mostrarMensaje("mensaje-lista", error.message, true);
  }
}

function mostrarDetalleTarea() {
  mostrarMensaje("mensaje-detalle-tarea", "");
  document.getElementById("detalle-descripcion").textContent =
    `Tarea N.º ${tareaActual.id} · ${tareaActual.descripcion}`;
  document.getElementById("detalle-solicitante").textContent =
    `Solicitante: ${tareaActual.solicitante}`;
  document.getElementById("detalle-fecha").textContent =
    `Fecha de solicitud: ${fechaLegible(tareaActual.fecha_solicitud)}`;
  document.getElementById("detalle-observaciones").textContent =
    tareaActual.observaciones ? `Observaciones: ${tareaActual.observaciones}` : "Sin observaciones";
  const estado = document.getElementById("detalle-estado");
  estado.textContent = tareaActual.estado;
  estado.dataset.estado = tareaActual.estado;

  const historial = document.getElementById("lista-historial");
  historial.replaceChildren();
  if (!tareaActual.historial.length) {
    const item = document.createElement("li");
    item.textContent = "No hay movimientos registrados.";
    historial.appendChild(item);
  } else {
    tareaActual.historial.forEach((registro) => {
      const item = document.createElement("li");
      item.className = "registro-historial";
      const estadoRegistro = document.createElement("strong");
      estadoRegistro.textContent = registro.estado;
      const detalles = document.createElement("small");
      detalles.textContent = `${registro.fecha_hora} · ${registro.usuario}`;
      const observaciones = document.createElement("small");
      observaciones.textContent = registro.observaciones || "Sin observaciones";
      item.append(estadoRegistro, detalles, observaciones);
      historial.appendChild(item);
    });
  }

  document.getElementById("vista-tarea").hidden = false;
  formularioEdicion.hidden = true;
}

document.getElementById("boton-nueva-tarea").addEventListener("click", () => {
  formularioNueva.reset();
  document.getElementById("solicitante-nueva").value =
    `${usuario.nombre || ""} ${usuario.apellido || ""}`.trim();
  document.getElementById("fecha-nueva").value = fechaLocalIso();
  mostrarMensaje("mensaje-nueva", "");
  dialogoNueva.showModal();
});

document.getElementById("boton-recargar").addEventListener("click", cargarTareas);
campoBusqueda.addEventListener("input", mostrarTareas);
document.querySelectorAll("[data-cerrar]").forEach((boton) => {
  boton.addEventListener("click", () => document.getElementById(boton.dataset.cerrar).close());
});
document.getElementById("boton-editar-tarea").addEventListener("click", () => {
  if (!tareaActual) return;
  document.getElementById("vista-tarea").hidden = true;
  formularioEdicion.hidden = false;
  document.getElementById("descripcion-edicion").value = tareaActual.descripcion;
  document.getElementById("solicitante-edicion").value = tareaActual.solicitante;
  document.getElementById("fecha-edicion").value = tareaActual.fecha_solicitud;
  document.getElementById("estado-edicion").value = tareaActual.estado;
  document.getElementById("observaciones-edicion").value = tareaActual.observaciones;
  mostrarMensaje("mensaje-edicion", "");
});
document.getElementById("boton-cancelar-edicion").addEventListener("click", () => {
  formularioEdicion.hidden = true;
  document.getElementById("vista-tarea").hidden = false;
});

formularioNueva.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const boton = document.getElementById("boton-guardar-nueva");
  boton.disabled = true;
  try {
    const resultado = await llamarApi("/tareas", {
      method: "POST",
      body: JSON.stringify({
        descripcion: document.getElementById("descripcion-nueva").value.trim(),
        fecha_solicitud: document.getElementById("fecha-nueva").value,
        observaciones: document.getElementById("observaciones-nueva").value.trim() || null,
      }),
    });
    dialogoNueva.close();
    await cargarTareas();
    mostrarMensaje("mensaje-lista", resultado.pendiente ? resultado.mensaje : "Tarea creada correctamente.");
  } catch (error) {
    mostrarMensaje("mensaje-nueva", error.message, true);
  } finally {
    boton.disabled = false;
  }
});

formularioEdicion.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!tareaActual) return;
  const boton = document.getElementById("boton-guardar-edicion");
  boton.disabled = true;
  try {
    const resultado = await llamarApi(`/tareas/${tareaActual.id}`, {
      method: "PUT",
      body: JSON.stringify({
        descripcion: document.getElementById("descripcion-edicion").value.trim(),
        fecha_solicitud: document.getElementById("fecha-edicion").value,
        estado: document.getElementById("estado-edicion").value,
        observaciones: document.getElementById("observaciones-edicion").value.trim() || null,
      }),
    });
    await cargarTareas();
    tareaActual = await llamarApi(`/tareas/${tareaActual.id}`);
    mostrarDetalleTarea();
    mostrarMensaje("mensaje-detalle-tarea", resultado.pendiente
      ? resultado.mensaje : "Tarea actualizada y agregada al historial.");
  } catch (error) {
    mostrarMensaje("mensaje-edicion", error.message, true);
  } finally {
    boton.disabled = false;
  }
});

window.addEventListener("100t:recargar-datos", async () => {
  await cargarTareas();
  if (tareaActual) {
    tareaActual = await llamarApi(`/tareas/${tareaActual.id}`);
    mostrarDetalleTarea();
  }
});
