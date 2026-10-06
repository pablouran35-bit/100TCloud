const token = sessionStorage.getItem("token");
const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const roles = (usuario.roles || []).map((rol) => rol.toUpperCase());

const contenido = document.getElementById("contenido");
const avisoAcceso = document.getElementById("acceso-denegado");
const formulario = document.getElementById("formulario-obra");
const listaObras = document.getElementById("lista-obras");
const mensaje = document.getElementById("mensaje");
const campoBusqueda = document.getElementById("busqueda-obra");
const cantidadResultados = document.getElementById("cantidad-resultados");
const detalle = document.getElementById("detalle-obra");
const dialogoContratistas = document.getElementById("dialogo-contratistas");

let obras = [];
let obraSeleccionada = null;
let obraEnEdicion = null;

if (!token) {
  window.location.replace("/app/");
} else if (!roles.includes("ADMINISTRADOR") && !roles.includes("EMPLEADO")) {
  avisoAcceso.hidden = false;
} else {
  contenido.hidden = false;
  cargarObras();
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

async function cargarObras() {
  try {
    const idSeleccionado = obraSeleccionada ? obraSeleccionada.id : null;
    obras = await llamarApi("/administracion/obras");
    mostrarObras();

    if (idSeleccionado) {
      const actualizada = obras.find((obra) => obra.id === idSeleccionado);

      if (actualizada) {
        seleccionarObra(actualizada);
      }
    }
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}

function mostrarObras() {
  listaObras.replaceChildren();

  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontradas = obras.filter((obra) =>
    normalizar(obra.nombre).includes(busqueda)
  );

  if (obras.length === 0) {
    cantidadResultados.textContent = "Todavía no hay obras cargadas.";
    cerrarDetalle();
    return;
  }

  cantidadResultados.textContent =
    encontradas.length === 1
      ? "1 obra"
      : encontradas.length + " obras";

  if (encontradas.length === 0) {
    listaObras.textContent = "No se encontraron obras.";
    cerrarDetalle();
    return;
  }

  encontradas.forEach((obra) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "obra";
    const nombre = document.createElement("strong");
    nombre.textContent = obra.nombre;
    const contratistas = document.createElement("small");
    contratistas.textContent = obra.contratistas
      ? `Contratistas: ${obra.contratistas}`
      : "Sin contratistas asignados";
    boton.append(nombre, contratistas);

    if (obraSeleccionada && obraSeleccionada.id === obra.id) {
      boton.classList.add("seleccionada");
    }

    boton.addEventListener("click", () => seleccionarObra(obra));
    listaObras.appendChild(boton);
  });
}

function seleccionarObra(obra) {
  obraSeleccionada = obra;

  document.getElementById("detalle-nombre").textContent = obra.nombre;
  document.getElementById("detalle-estado").textContent =
    obra.activo ? "Estado: Activa" : "Estado: Inactiva";
  document.getElementById("detalle-contratistas").textContent = obra.contratistas
    ? `Contratistas asignados: ${obra.contratistas}`
    : "Contratistas asignados: ninguno";
  document.getElementById("detalle-direccion").textContent =
    obra.direccion ? "Dirección: " + obra.direccion : "Sin dirección";
  document.getElementById("detalle-observaciones").textContent =
    obra.observaciones
      ? "Observaciones: " + obra.observaciones
      : "Sin observaciones";

  document.getElementById("boton-cambiar-estado").textContent =
    obra.activo ? "Desactivar" : "Activar";

  if (!detalle.open) {
    detalle.showModal();
  }

  mostrarObras();
}

campoBusqueda.addEventListener("input", () => {
  obraSeleccionada = null;
  cerrarDetalle();
  mostrarObras();
  listaObras.scrollTop = 0;
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
    if (obraSeleccionada) {
      editarObra(obraSeleccionada);
    }
  });

document
  .getElementById("boton-cambiar-estado")
  .addEventListener("click", () => {
    if (obraSeleccionada) {
      cambiarEstado(obraSeleccionada);
    }
  });

document.getElementById("boton-asignar-contratistas").addEventListener("click", async () => {
  if (!obraSeleccionada) return;
  const obra = obraSeleccionada;
  cerrarDetalle();
  document.getElementById("titulo-contratistas").textContent =
    `Contratistas · ${obra.nombre}`;
  const lista = document.getElementById("lista-contratistas");
  lista.textContent = "Cargando contratistas...";
  document.getElementById("mensaje-contratistas").textContent = "";
  dialogoContratistas.showModal();
  try {
    const contratistas = await llamarApi(`/administracion/obras/${obra.id}/contratistas`);
    lista.replaceChildren();
    if (contratistas.length === 0) {
      lista.textContent = "No hay contratistas activos con usuario. Primero asignales el rol Contratista en Administración · Usuarios.";
      return;
    }
    contratistas.forEach((contratista) => {
      const etiqueta = document.createElement("label");
      etiqueta.className = "contratista";
      const casilla = document.createElement("input");
      casilla.type = "checkbox";
      casilla.value = contratista.persona_id;
      casilla.checked = contratista.asignado;
      casilla.disabled = !contratista.activo;
      const texto = document.createElement("span");
      texto.textContent = `${contratista.nombre} · ${contratista.usuario}${contratista.activo ? "" : " (inactivo; asignación existente)"}`;
      etiqueta.append(casilla, texto);
      lista.appendChild(etiqueta);
    });
  } catch (error) {
    lista.replaceChildren();
    document.getElementById("mensaje-contratistas").textContent = error.message;
    document.getElementById("mensaje-contratistas").style.color = "#b42318";
  }
});

document.getElementById("boton-cerrar-contratistas").addEventListener("click", () => {
  dialogoContratistas.close();
  if (obraSeleccionada && !detalle.open) seleccionarObra(obraSeleccionada);
});

dialogoContratistas.addEventListener("click", (evento) => {
  if (evento.target === dialogoContratistas) {
    dialogoContratistas.close();
    if (obraSeleccionada && !detalle.open) seleccionarObra(obraSeleccionada);
  }
});

document.getElementById("boton-guardar-contratistas").addEventListener("click", async (evento) => {
  if (!obraSeleccionada) return;
  const boton = evento.currentTarget;
  const personaIds = [...document.querySelectorAll("#lista-contratistas input:checked")]
    .map((casilla) => Number(casilla.value));
  boton.disabled = true;
  try {
    await llamarApi(`/administracion/obras/${obraSeleccionada.id}/contratistas`, {
      method: "PUT",
      body: JSON.stringify({ persona_ids: personaIds }),
    });
    mostrarMensaje("Contratistas asignados correctamente.");
    dialogoContratistas.close();
    await cargarObras();
  } catch (error) {
    const mensajeContratistas = document.getElementById("mensaje-contratistas");
    mensajeContratistas.textContent = error.message;
    mensajeContratistas.style.color = "#b42318";
  } finally {
    boton.disabled = false;
  }
});

function editarObra(obra) {
  cerrarDetalle();
  obraEnEdicion = obra.id;

  formulario.elements.nombre.value = obra.nombre || "";
  formulario.elements.direccion.value = obra.direccion || "";
  formulario.elements.observaciones.value = obra.observaciones || "";

  document.getElementById("titulo-formulario").textContent =
    "Modificar obra";
  document.getElementById("boton-guardar").textContent =
    "Guardar cambios";
  document.getElementById("boton-cancelar").hidden = false;

  formulario.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicion() {
  obraEnEdicion = null;
  formulario.reset();

  document.getElementById("titulo-formulario").textContent =
    "Agregar una obra";
  document.getElementById("boton-guardar").textContent =
    "Guardar obra";
  document.getElementById("boton-cancelar").hidden = true;
}

document
  .getElementById("boton-cancelar")
  .addEventListener("click", cancelarEdicion);

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const botonGuardar = document.getElementById("boton-guardar");
  const estabaEditando = Boolean(obraEnEdicion);

  const datos = {
    nombre: formulario.elements.nombre.value.trim(),
    direccion: formulario.elements.direccion.value.trim() || null,
    observaciones:
      formulario.elements.observaciones.value.trim() || null
  };

  const url = estabaEditando
    ? "/administracion/obras/" + obraEnEdicion
    : "/administracion/obras";

  const metodo = estabaEditando ? "PUT" : "POST";

  botonGuardar.disabled = true;
  botonGuardar.textContent = "Guardando...";

  try {
    await llamarApi(url, {
      method: metodo,
      body: JSON.stringify(datos)
    });

    cancelarEdicion();
    obraSeleccionada = null;
    cerrarDetalle();

    mostrarMensaje(
      estabaEditando
        ? "Obra modificada correctamente."
        : "Obra creada correctamente."
    );

    await cargarObras();
  } catch (error) {
    mostrarMensaje(error.message, true);
  } finally {
    botonGuardar.disabled = false;
    botonGuardar.textContent = obraEnEdicion
      ? "Guardar cambios"
      : "Guardar obra";
  }
});

async function cambiarEstado(obra) {
  const accion = obra.activo ? "desactivar" : "activar";

  if (!window.confirm("¿Querés " + accion + ' "' + obra.nombre + '"?')) {
    return;
  }

  try {
    await llamarApi("/administracion/obras/" + obra.id + "/estado", {
      method: "PATCH",
      body: JSON.stringify({ activo: !obra.activo })
    });

    mostrarMensaje(
      "Estado de la obra actualizado correctamente."
    );

    await cargarObras();
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}
