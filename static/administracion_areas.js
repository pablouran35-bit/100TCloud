const token = sessionStorage.getItem("token");
const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const roles = (usuario.roles || []).map((rol) => rol.toUpperCase());

const contenido = document.getElementById("contenido");
const avisoAcceso = document.getElementById("acceso-denegado");
const formulario = document.getElementById("formulario-area");
const listaAreas = document.getElementById("lista-areas");
const mensaje = document.getElementById("mensaje");
const campoBusqueda = document.getElementById("busqueda-area");
const cantidadResultados = document.getElementById("cantidad-resultados");
const detalle = document.getElementById("detalle-area");

let areas = [];
let areaSeleccionada = null;
let areaEnEdicion = null;

if (!token) {
  window.location.replace("/app/");
} else if (!roles.includes("ADMINISTRADOR") && !roles.includes("EMPLEADO")) {
  avisoAcceso.hidden = false;
} else {
  contenido.hidden = false;
  cargarAreas();
}

async function llamarApi(url, opciones = {}) {
  const cabeceras = {
    Authorization: "Bearer " + token,
    ...(opciones.headers || {})
  };

  if (opciones.body) {
    cabeceras["Content-Type"] = "application/json";
  }

  const respuesta = await fetch(url, {
    ...opciones,
    headers: cabeceras
  });

  const texto = await respuesta.text();
  let datos = {};

  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      throw new Error(
        "El servidor respondió con un error. Revisá la terminal de Uvicorn."
      );
    }
  }

  if (!respuesta.ok) {
    throw new Error(datos.detail || "Error " + respuesta.status);
  }

  return datos;
}

function mostrarMensaje(texto, esError = false) {
  mensaje.textContent = texto;
  mensaje.style.color = esError ? "#b42318" : "#276341";
}

function normalizar(texto) {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

function cerrarDetalle() {
  if (detalle.open) {
    detalle.close();
  }
}

async function cargarAreas() {
  try {
    const idSeleccionado = areaSeleccionada
      ? areaSeleccionada.id
      : null;
    areas = await llamarApi("/administracion/areas");
    mostrarAreas();

    if (idSeleccionado) {
      const actualizada = areas.find((area) => area.id === idSeleccionado);

      if (actualizada) {
        seleccionarArea(actualizada);
      }
    }
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}

function mostrarAreas() {
  listaAreas.replaceChildren();

  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontradas = areas
    .filter((area) => normalizar(area.nombre).includes(busqueda))
    .sort((a, b) => Number(a.id) - Number(b.id));

  if (areas.length === 0) {
    cantidadResultados.textContent = "Todavía no hay áreas cargadas.";
    cerrarDetalle();
    return;
  }

  cantidadResultados.textContent =
    encontradas.length === 1
      ? "1 área"
      : encontradas.length + " áreas";

  if (encontradas.length === 0) {
    listaAreas.textContent = "No se encontraron áreas.";
    cerrarDetalle();
    return;
  }

  encontradas.forEach((area) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "area";
    boton.textContent = area.id + " — " + area.nombre;

    if (areaSeleccionada && areaSeleccionada.id === area.id) {
      boton.classList.add("seleccionada");
    }

    boton.addEventListener("click", () => seleccionarArea(area));
    listaAreas.appendChild(boton);
  });
}

function seleccionarArea(area) {
  areaSeleccionada = area;

  document.getElementById("detalle-nombre").textContent = area.nombre;
  document.getElementById("detalle-id").textContent = "ID: " + area.id;
  document.getElementById("detalle-estado").textContent =
    area.activo ? "Estado: Activa" : "Estado: Inactiva";
  document.getElementById("boton-cambiar-estado").textContent =
    area.activo ? "Desactivar" : "Activar";

  if (!detalle.open) {
    detalle.showModal();
  }

  mostrarAreas();
}

campoBusqueda.addEventListener("input", () => {
  areaSeleccionada = null;
  cerrarDetalle();
  mostrarAreas();
  listaAreas.scrollTop = 0;
});

document
  .getElementById("boton-cerrar-detalle")
  .addEventListener("click", cerrarDetalle);

detalle.addEventListener("click", (evento) => {
  if (evento.target === detalle) {
    cerrarDetalle();
  }
});

document
  .getElementById("boton-modificar")
  .addEventListener("click", () => {
    if (areaSeleccionada) {
      editarArea(areaSeleccionada);
    }
  });

document
  .getElementById("boton-cambiar-estado")
  .addEventListener("click", () => {
    if (areaSeleccionada) {
      cambiarEstado(areaSeleccionada);
    }
  });

function editarArea(area) {
  cerrarDetalle();
  areaEnEdicion = area.id;
  formulario.elements.nombre.value = area.nombre || "";

  document.getElementById("titulo-formulario").textContent =
    "Modificar área";
  document.getElementById("boton-guardar").textContent =
    "Guardar cambios";
  document.getElementById("boton-cancelar").hidden = false;

  formulario.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicion() {
  areaEnEdicion = null;
  formulario.reset();

  document.getElementById("titulo-formulario").textContent =
    "Agregar un área";
  document.getElementById("boton-guardar").textContent =
    "Guardar área";
  document.getElementById("boton-cancelar").hidden = true;
}

document
  .getElementById("boton-cancelar")
  .addEventListener("click", cancelarEdicion);

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const botonGuardar = document.getElementById("boton-guardar");
  const estabaEditando = Boolean(areaEnEdicion);
  const datos = {
    nombre: formulario.elements.nombre.value.trim()
  };

  const url = estabaEditando
    ? "/administracion/areas/" + areaEnEdicion
    : "/administracion/areas";
  const metodo = estabaEditando ? "PUT" : "POST";

  botonGuardar.disabled = true;
  botonGuardar.textContent = "Guardando...";

  try {
    await llamarApi(url, {
      method: metodo,
      body: JSON.stringify(datos)
    });

    cancelarEdicion();
    areaSeleccionada = null;
    cerrarDetalle();

    mostrarMensaje(
      estabaEditando
        ? "Área modificada correctamente."
        : "Área creada correctamente."
    );

    await cargarAreas();
  } catch (error) {
    mostrarMensaje(error.message, true);
  } finally {
    botonGuardar.disabled = false;
    botonGuardar.textContent = areaEnEdicion
      ? "Guardar cambios"
      : "Guardar área";
  }
});

async function cambiarEstado(area) {
  const accion = area.activo ? "desactivar" : "activar";

  if (!window.confirm("¿Querés " + accion + ' el área "' + area.nombre + '"?')) {
    return;
  }

  try {
    await llamarApi("/administracion/areas/" + area.id + "/estado", {
      method: "PATCH",
      body: JSON.stringify({ activo: !area.activo })
    });

    mostrarMensaje(
      "Área " + (accion === "activar" ? "activada" : "desactivada") +
        " correctamente."
    );

    await cargarAreas();
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}
