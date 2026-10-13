
"use strict";

const token = sessionStorage.getItem("token");

const pantallaLista = document.getElementById("pantalla-lista");
const pantallaDetalle = document.getElementById("pantalla-detalle");

let planillasPendientes = [];
let planillaActual = null;
let solicitudesActuales = [];

const ESTADOS_TERMINALES = new Set([
  "COMPRADO Y RETIRADO",
  "ENTREGADO",
  "CANCELADA",
  "RECHAZADA"
]);

// ============================================================
// AUTENTICACIÓN
// ============================================================

function obtenerUsuario() {
  try {
    return JSON.parse(sessionStorage.getItem("usuario") || "{}");
  } catch {
    return {};
  }
}

function esAdministrador() {
  const usuario = obtenerUsuario();

  return (usuario.roles || []).some(
    (rol) => String(rol).toUpperCase() === "ADMINISTRADOR"
  );
}

if (!token) {
  window.location.replace("/app/");
} else if (!esAdministrador()) {
  window.location.replace("/app/");
}

// ============================================================
// CONEXIÓN CON LA API
// ============================================================

async function llamarApi(url, opciones = {}) {
  if (!window.offline100t ||
      typeof window.offline100t.solicitarApi !== "function") {
    throw new Error(
      "No se pudo inicializar la conexión. Recargá la página."
    );
  }

  return window.offline100t.solicitarApi(
    url,
    opciones,
    token
  );
}

// ============================================================
// UTILIDADES
// ============================================================

function normalizar(texto) {
  return String(texto ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

function texto(valor, alternativa = "") {
  if (valor === null || valor === undefined || valor === "") {
    return alternativa;
  }

  return String(valor);
}

function mostrarError(id, mensaje) {
  const elemento = document.getElementById(id);
  elemento.textContent = mensaje;
  elemento.style.color = "#b42318";
}

function mostrarExito(id, mensaje) {
  const elemento = document.getElementById(id);
  elemento.textContent = mensaje;
  elemento.style.color = "#276341";
}

function limpiarMensaje(id) {
  const elemento = document.getElementById(id);
  elemento.textContent = "";
  elemento.style.color = "";
}

function mostrarLista() {
  pantallaLista.hidden = false;
  pantallaDetalle.hidden = true;
  window.scrollTo(0, 0);
}

function mostrarDetalle() {
  pantallaLista.hidden = true;
  pantallaDetalle.hidden = false;
  window.scrollTo(0, 0);
}

function fechaLegible(valor) {
  if (!valor) {
    return "Sin fecha";
  }

  const fechaTexto = String(valor).slice(0, 10);
  const partes = fechaTexto.split("-");

  if (
    partes.length !== 3 ||
    !partes.every((parte) => /^\d+$/.test(parte))
  ) {
    return fechaTexto;
  }

  const fecha = new Date(
    Number(partes[0]),
    Number(partes[1]) - 1,
    Number(partes[2]),
    12
  );

  if (Number.isNaN(fecha.getTime())) {
    return fechaTexto;
  }

  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric"
  }).format(fecha);
}

function obtenerIdPlanilla(planilla) {
  return planilla?.id ??
    planilla?.planilla_id ??
    planilla?.id_planilla ??
    null;
}

function obtenerIdSolicitud(solicitud) {
  return solicitud?.id ??
    solicitud?.solicitud_id ??
    solicitud?.id_solicitud ??
    null;
}

function obtenerEstado(solicitud) {
  return texto(solicitud?.estado, "")
    .trim()
    .toUpperCase();
}

function esProcesable(solicitud) {
  return !ESTADOS_TERMINALES.has(obtenerEstado(solicitud));
}

function extraerLista(resultado) {
  if (Array.isArray(resultado)) {
    return resultado;
  }

  if (Array.isArray(resultado?.planillas)) {
    return resultado.planillas;
  }

  if (Array.isArray(resultado?.pendientes)) {
    return resultado.pendientes;
  }

  if (Array.isArray(resultado?.items)) {
    return resultado.items;
  }

  return [];
}

// ============================================================
// CARGAR PLANILLAS PENDIENTES
// ============================================================

async function cargarPlanillas() {
  const boton = document.getElementById("boton-actualizar");
  const lista = document.getElementById("lista-planillas");

  boton.disabled = true;
  lista.textContent = "Cargando planillas...";
  limpiarMensaje("mensaje-lista");

  try {
    const resultado = await llamarApi(
      "/planillas/aprobacion/pendientes"
    );

    planillasPendientes = extraerLista(resultado);

    mostrarPlanillas();

  } catch (error) {
    planillasPendientes = [];
    lista.replaceChildren();

    mostrarError(
      "mensaje-lista",
      error.message || "No se pudieron cargar las planillas."
    );

  } finally {
    boton.disabled = false;
  }
}

function mostrarPlanillas() {
  const lista = document.getElementById("lista-planillas");

  lista.replaceChildren();

  if (planillasPendientes.length === 0) {
    lista.textContent =
      "No hay planillas pendientes de aprobación.";

    return;
  }

  planillasPendientes.forEach((planilla) => {
    const id = obtenerIdPlanilla(planilla);

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "item-planilla";

    const titulo = document.createElement("strong");

    titulo.textContent =
      `Planilla N.º ${texto(id, "?")} · ` +
      texto(planilla.obra, "Obra sin nombre");

    const detalle = document.createElement("small");

    const fecha = fechaLegible(
      planilla.fecha_compra ??
      planilla.fecha ??
      planilla.fecha_salida
    );

    const solicitantes = texto(
      planilla.solicitantes,
      ""
    );

    const cantidad = planilla.pendientes ??
      planilla.cantidad_solicitudes ??
      planilla.total_solicitudes;

    detalle.textContent =
      `Fecha de compra: ${fecha}` +
      (cantidad !== undefined
        ? ` · Solicitudes: ${cantidad}`
        : "") +
      (solicitantes
        ? ` · Solicitantes: ${solicitantes}`
        : "");

    boton.append(titulo, detalle);

    if (id === null || id === undefined) {
      boton.disabled = true;
    } else {
      boton.addEventListener("click", () => {
        abrirPlanilla(id);
      });
    }

    lista.appendChild(boton);
  });
}

// ============================================================
// ABRIR UNA PLANILLA
// ============================================================

async function abrirPlanilla(planillaId) {
  limpiarMensaje("mensaje-detalle");

  const lista = document.getElementById("lista-solicitudes");

  lista.textContent = "Cargando solicitudes...";

  document.getElementById("boton-aprobar").disabled = true;
  document.getElementById("boton-rechazar").disabled = true;

  mostrarDetalle();

  try {
    const resultado = await llamarApi(
      `/planillas/aprobacion/${encodeURIComponent(planillaId)}`
    );

    if (!resultado || typeof resultado !== "object") {
      throw new Error("La API devolvió una respuesta no válida.");
    }

    // La API puede devolver los datos de la planilla y las
    // solicitudes juntos, o dentro de la propiedad "planilla".
    const datosPlanilla = resultado.planilla &&
      typeof resultado.planilla === "object"
      ? resultado.planilla
      : resultado;

    const solicitudes = Array.isArray(resultado.solicitudes)
      ? resultado.solicitudes
      : Array.isArray(datosPlanilla.solicitudes)
        ? datosPlanilla.solicitudes
        : null;

    if (!solicitudes) {
      throw new Error(
        "La respuesta no contiene la lista de solicitudes esperada."
      );
    }

    planillaActual = {
      ...datosPlanilla,
      id: obtenerIdPlanilla(datosPlanilla) ?? planillaId
    };

    solicitudesActuales = solicitudes;

    document.getElementById("titulo-planilla").textContent =
      `Planilla N.º ${texto(planillaActual.id)} · ` +
      texto(planillaActual.obra, "Obra sin nombre");

    document.getElementById("datos-planilla").textContent =
      `Fecha de compra: ${fechaLegible(
        planillaActual.fecha_compra ??
        planillaActual.fecha ??
        planillaActual.fecha_salida
      )}`;

    document.getElementById("motivo-rechazo").value = "";

    mostrarSolicitudes();

  } catch (error) {
    lista.replaceChildren();

    mostrarError(
      "mensaje-detalle",
      error.message || "No se pudo abrir la planilla."
    );

  } finally {
    document.getElementById("boton-aprobar").disabled = false;
    document.getElementById("boton-rechazar").disabled = false;
  }
}

// ============================================================
// MOSTRAR SOLICITUDES
// ============================================================

function mostrarSolicitudes() {
  const lista = document.getElementById("lista-solicitudes");

  lista.replaceChildren();

  const procesables = solicitudesActuales.filter(esProcesable);

  document.getElementById("cantidad-solicitudes").textContent =
    `${solicitudesActuales.length} solicitudes en total · ` +
    `${procesables.length} pendientes de resolución`;

  if (solicitudesActuales.length === 0) {
    lista.textContent = "Esta planilla no tiene solicitudes.";
    document.getElementById("boton-aprobar").disabled = true;
    document.getElementById("boton-rechazar").disabled = true;
    return;
  }

  if (procesables.length === 0) {
    lista.textContent =
      "No hay solicitudes que puedan aprobarse o rechazarse.";

    document.getElementById("boton-aprobar").disabled = true;
    document.getElementById("boton-rechazar").disabled = true;
    return;
  }

  procesables.forEach((solicitud) => {
    const id = obtenerIdSolicitud(solicitud);

    const contenedor = document.createElement("div");
    contenedor.className = "solicitud";

    const etiqueta = document.createElement("label");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "seleccion-solicitud";
    checkbox.value = texto(id);

    if (id === null || id === undefined) {
      checkbox.disabled = true;
    }

    const contenido = document.createElement("div");

    const titulo = document.createElement("strong");

    titulo.textContent =
      `${texto(solicitud.cantidad, "?")} — ` +
      texto(
        solicitud.producto ??
        solicitud.articulo ??
        solicitud.nombre_producto,
        "Artículo sin nombre"
      );

    const detalles = document.createElement("div");
    detalles.className = "detalle-solicitud";

    const area = texto(
      solicitud.area,
      solicitud.area_nombre
        ? solicitud.area_nombre
        : ""
    );

    const areaId = solicitud.area_id;

    const persona = texto(
      solicitud.persona ??
      solicitud.solicitante ??
      solicitud.nombre_solicitante,
      "No informado"
    );

    const estado = texto(solicitud.estado, "Sin estado");

    const observaciones = texto(
      solicitud.observaciones,
      "Sin observaciones"
    );

    detalles.textContent =
      `Solicitante: ${persona}` +
      (area
        ? ` · Área: ${areaId ? areaId + " — " : ""}${area}`
        : areaId
          ? ` · Área ID: ${areaId}`
          : "") +
      ` · Estado: ${estado}` +
      ` · Observaciones: ${observaciones}`;

    contenido.append(titulo, detalles);
    etiqueta.append(checkbox, contenido);
    contenedor.appendChild(etiqueta);

    lista.appendChild(contenedor);
  });

  const seleccionables = lista.querySelectorAll(
    ".seleccion-solicitud:not(:disabled)"
  );

  if (seleccionables.length === 0) {
    mostrarError(
      "mensaje-detalle",
      "No se encontraron IDs válidos para las solicitudes."
    );

    document.getElementById("boton-aprobar").disabled = true;
    document.getElementById("boton-rechazar").disabled = true;
  }
}

// ============================================================
// SELECCIÓN
// ============================================================

function obtenerIdsSeleccionados() {
  return [
    ...document.querySelectorAll(
      ".seleccion-solicitud:checked"
    )
  ]
    .map((checkbox) => Number(checkbox.value))
    .filter((id) => Number.isSafeInteger(id) && id > 0);
}

document
  .getElementById("boton-seleccionar-todas")
  .addEventListener("click", () => {
    document
      .querySelectorAll(".seleccion-solicitud:not(:disabled)")
      .forEach((checkbox) => {
        checkbox.checked = true;
      });
  });

document
  .getElementById("boton-deseleccionar")
  .addEventListener("click", () => {
    document
      .querySelectorAll(".seleccion-solicitud")
      .forEach((checkbox) => {
        checkbox.checked = false;
      });
  });

// ============================================================
// APROBAR PLANILLA COMPLETA
// ============================================================

document
  .getElementById("boton-aprobar")
  .addEventListener("click", async () => {
    if (!planillaActual) {
      mostrarError(
        "mensaje-detalle",
        "Primero seleccioná una planilla."
      );
      return;
    }

    const ids = solicitudesActuales
      .filter(esProcesable)
      .map(obtenerIdSolicitud)
      .filter((id) => id !== null && id !== undefined)
      .map(Number)
      .filter((id) => Number.isSafeInteger(id) && id > 0);

    if (ids.length === 0) {
      mostrarError(
        "mensaje-detalle",
        "No hay solicitudes válidas para enviar a aprobación."
      );
      return;
    }

    const confirmado = window.confirm(
      `¿Confirmás la aprobación de la planilla N.º ` +
      `${planillaActual.id}?\n\n` +
      `Se aprobará la planilla completa y las solicitudes ` +
      `procesables continuarán al módulo Compras.`
    );

    if (!confirmado) {
      return;
    }

    await resolverPlanilla({
      decision: "APROBAR",
      solicitudes_ids: ids,
      motivo: null
    });
  });

// ============================================================
// RECHAZAR SOLICITUDES SELECCIONADAS
// ============================================================

document
  .getElementById("boton-rechazar")
  .addEventListener("click", async () => {
    if (!planillaActual) {
      mostrarError(
        "mensaje-detalle",
        "Primero seleccioná una planilla."
      );
      return;
    }

    const ids = obtenerIdsSeleccionados();

    if (ids.length === 0) {
      mostrarError(
        "mensaje-detalle",
        "Seleccioná al menos una solicitud para rechazar."
      );
      return;
    }

    const motivo = document
      .getElementById("motivo-rechazo")
      .value
      .trim();

    if (motivo.length < 3) {
      mostrarError(
        "mensaje-detalle",
        "Escribí un motivo de rechazo de al menos 3 caracteres."
      );
      document.getElementById("motivo-rechazo").focus();
      return;
    }

    const confirmado = window.confirm(
      `¿Confirmás el rechazo de ${ids.length} solicitud(es)?\n\n` +
      `Las demás solicitudes no seleccionadas no se rechazarán.`
    );

    if (!confirmado) {
      return;
    }

    await resolverPlanilla({
      decision: "RECHAZAR",
      solicitudes_ids: ids,
      motivo
    });
  });

// ============================================================
// ENVIAR DECISIÓN A LA API
// ============================================================

async function resolverPlanilla(datos) {
  const botonAprobar = document.getElementById("boton-aprobar");
  const botonRechazar = document.getElementById("boton-rechazar");

  botonAprobar.disabled = true;
  botonRechazar.disabled = true;

  limpiarMensaje("mensaje-detalle");

  try {
    const resultado = await llamarApi(
      `/planillas/aprobacion/${encodeURIComponent(planillaActual.id)}/resolver`,
      {
        method: "POST",
        body: JSON.stringify(datos)
      }
    );

    mostrarExito(
      "mensaje-detalle",
      resultado?.mensaje ||
      (
        datos.decision === "APROBAR"
          ? "Planilla aprobada correctamente."
          : "Solicitudes rechazadas correctamente."
      )
    );

    // Actualizamos la lista para reflejar la resolución.
    await cargarPlanillas();

    // Si quedan solicitudes pendientes de aprobación, permitimos
    // volver a seleccionarla. Si ya no aparece, volvemos al listado.
    const siguePendiente = planillasPendientes.some(
      (planilla) =>
        String(obtenerIdPlanilla(planilla)) ===
        String(planillaActual.id)
    );

    if (!siguePendiente || datos.decision === "APROBAR") {
      mostrarLista();
    } else {
      await abrirPlanilla(planillaActual.id);
      mostrarExito(
        "mensaje-detalle",
        resultado?.mensaje ||
        "La resolución se registró correctamente."
      );
    }

  } catch (error) {
    mostrarError(
      "mensaje-detalle",
      error.message || "No se pudo resolver la aprobación."
    );

  } finally {
    botonAprobar.disabled = false;
    botonRechazar.disabled = false;
  }
}

// ============================================================
// VOLVER Y ACTUALIZAR
// ============================================================

document
  .getElementById("boton-actualizar")
  .addEventListener("click", cargarPlanillas);

document
  .getElementById("boton-volver-lista")
  .addEventListener("click", async () => {
    mostrarLista();
    await cargarPlanillas();
  });

// ============================================================
// INICIO
// ============================================================

if (token && esAdministrador()) {
  cargarPlanillas();
}
