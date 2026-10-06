const token = sessionStorage.getItem("token");
const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const roles = (usuario.roles || []).map((rol) => rol.toUpperCase());

const contenido = document.getElementById("contenido");
const avisoAcceso = document.getElementById("acceso-denegado");
const formulario = document.getElementById("formulario-articulo");
const listaArticulos = document.getElementById("lista-articulos");
const mensaje = document.getElementById("mensaje");
const campoBusqueda = document.getElementById("busqueda-articulo");
const cantidadResultados = document.getElementById("cantidad-resultados");
const detalle = document.getElementById("detalle-articulo");

let articulos = [];
let articuloSeleccionado = null;
let articuloEnEdicion = null;

if (!token) {
  window.location.replace("/app/");
} else if (!roles.includes("ADMINISTRADOR") && !roles.includes("EMPLEADO")) {
  avisoAcceso.hidden = false;
} else {
  contenido.hidden = false;
  cargarArticulos();
}

async function llamarApi(url, opciones = {}) {
  const cabeceras = {
    Authorization: `Bearer ${token}`,
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
    throw new Error(datos.detail || `Error ${respuesta.status}`);
  }

  return datos;
}

function mostrarMensaje(texto, esError = false) {
  mensaje.textContent = texto;
  mensaje.style.color = esError ? "#b42318" : "#276341";
}

function cerrarDetalle() {
  if (detalle.open) {
    detalle.close();
  }
}

function normalizar(texto) {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

async function cargarArticulos() {
  try {
    const idSeleccionado = articuloSeleccionado?.id;
    articulos = await llamarApi("/administracion/articulos");
    mostrarArticulos();

    if (idSeleccionado) {
      const actualizado = articulos.find(
        (articulo) => articulo.id === idSeleccionado
      );

      if (actualizado) {
        seleccionarArticulo(actualizado);
      }
    }
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}

function mostrarArticulos() {
  listaArticulos.replaceChildren();

  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontrados = articulos.filter((articulo) =>
    normalizar(articulo.nombre).includes(busqueda)
  );

  if (articulos.length === 0) {
    cantidadResultados.textContent = "Todavía no hay artículos cargados.";
    cerrarDetalle();
    return;
  }

  cantidadResultados.textContent =
    encontrados.length === 1
      ? "1 artículo"
      : `${encontrados.length} artículos`;

  if (encontrados.length === 0) {
    listaArticulos.textContent = "No se encontraron artículos.";
    cerrarDetalle();
    return;
  }

  encontrados.forEach((articulo) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "articulo";
    boton.textContent = articulo.nombre;

    if (articuloSeleccionado?.id === articulo.id) {
      boton.classList.add("seleccionado");
    }

    boton.addEventListener("click", () => seleccionarArticulo(articulo));
    listaArticulos.appendChild(boton);
  });
}

function seleccionarArticulo(articulo) {
  articuloSeleccionado = articulo;

  document.getElementById("detalle-nombre").textContent = articulo.nombre;
  document.getElementById("detalle-unidad").textContent =
    `Unidad: ${articulo.unidad}`;
  document.getElementById("detalle-estado").textContent =
    articulo.activo ? "Estado: Activo" : "Estado: Inactivo";
  document.getElementById("detalle-observaciones").textContent =
    articulo.observaciones
      ? `Observaciones: ${articulo.observaciones}`
      : "Sin observaciones";

  document.getElementById("boton-cambiar-estado").textContent =
    articulo.activo ? "Desactivar" : "Activar";

  if (!detalle.open) {
    detalle.showModal();
  }
  mostrarArticulos();
}

campoBusqueda.addEventListener("input", () => {
  articuloSeleccionado = null;
  cerrarDetalle();
  mostrarArticulos();
  listaArticulos.scrollTop = 0;
});

document
  .getElementById("boton-modificar")
  .addEventListener("click", () => {
    if (articuloSeleccionado) {
      editarArticulo(articuloSeleccionado);
    }
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
  .getElementById("boton-cambiar-estado")
  .addEventListener("click", () => {
    if (articuloSeleccionado) {
      cambiarEstado(articuloSeleccionado);
    }
  });

function editarArticulo(articulo) {
  cerrarDetalle();
  articuloEnEdicion = articulo.id;

  formulario.elements.nombre.value = articulo.nombre || "";
  formulario.elements.unidad.value = articulo.unidad || "";
  formulario.elements.observaciones.value =
    articulo.observaciones || "";

  document.getElementById("titulo-formulario").textContent =
    "Modificar artículo";
  document.getElementById("boton-guardar").textContent =
    "Guardar cambios";
  document.getElementById("boton-cancelar").hidden = false;

  formulario.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicion() {
  articuloEnEdicion = null;
  formulario.reset();

  document.getElementById("titulo-formulario").textContent =
    "Agregar un artículo";
  document.getElementById("boton-guardar").textContent =
    "Guardar artículo";
  document.getElementById("boton-cancelar").hidden = true;
}

document
  .getElementById("boton-cancelar")
  .addEventListener("click", cancelarEdicion);

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const botonGuardar = document.getElementById("boton-guardar");
  const estabaEditando = Boolean(articuloEnEdicion);

  const datos = {
    nombre: formulario.elements.nombre.value.trim(),
    unidad: formulario.elements.unidad.value,
    observaciones:
      formulario.elements.observaciones.value.trim() || null
  };

  const url = estabaEditando
    ? `/administracion/articulos/${articuloEnEdicion}`
    : "/administracion/articulos";

  const metodo = estabaEditando ? "PUT" : "POST";

  botonGuardar.disabled = true;
  botonGuardar.textContent = "Guardando...";

  try {
    await llamarApi(url, {
      method: metodo,
      body: JSON.stringify(datos)
    });

    cancelarEdicion();
    articuloSeleccionado = null;
    cerrarDetalle();

    mostrarMensaje(
      estabaEditando
        ? "Artículo modificado correctamente."
        : "Artículo creado correctamente."
    );

    await cargarArticulos();
  } catch (error) {
    mostrarMensaje(error.message, true);
  } finally {
    botonGuardar.disabled = false;
    botonGuardar.textContent = articuloEnEdicion
      ? "Guardar cambios"
      : "Guardar artículo";
  }
});

async function cambiarEstado(articulo) {
  const accion = articulo.activo ? "desactivar" : "activar";

  if (!window.confirm(`¿Querés ${accion} "${articulo.nombre}"?`)) {
    return;
  }

  try {
    await llamarApi(`/administracion/articulos/${articulo.id}/estado`, {
      method: "PATCH",
      body: JSON.stringify({ activo: !articulo.activo })
    });

    mostrarMensaje(
      `Artículo ${accion === "activar" ? "activado" : "desactivado"}.`
    );

    await cargarArticulos();
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}
