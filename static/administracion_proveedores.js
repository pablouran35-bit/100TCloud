const token = sessionStorage.getItem("token");
const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const roles = (usuario.roles || []).map((rol) => rol.toUpperCase());

const contenido = document.getElementById("contenido");
const avisoAcceso = document.getElementById("acceso-denegado");
const formulario = document.getElementById("formulario-proveedor");
const listaProveedores = document.getElementById("lista-proveedores");
const mensaje = document.getElementById("mensaje");
const campoBusqueda = document.getElementById("busqueda-proveedor");
const cantidadResultados = document.getElementById("cantidad-resultados");
const detalle = document.getElementById("detalle-proveedor");

let proveedores = [];
let proveedorSeleccionado = null;
let proveedorEnEdicion = null;

if (!token) {
  window.location.replace("/app/");
} else if (!roles.includes("ADMINISTRADOR") && !roles.includes("EMPLEADO")) {
  avisoAcceso.hidden = false;
} else {
  contenido.hidden = false;
  cargarProveedores();
}

async function llamarApi(url, opciones = {}) {
  const cabeceras = {
    Authorization: `Bearer ${token}`,
    ...(opciones.headers || {})
  };
  if (opciones.body) cabeceras["Content-Type"] = "application/json";

  const respuesta = await fetch(url, { ...opciones, headers: cabeceras });
  const texto = await respuesta.text();
  let datos = {};
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      throw new Error("El servidor respondió con un error. Revisá la terminal de Uvicorn.");
    }
  }
  if (!respuesta.ok) throw new Error(datos.detail || `Error ${respuesta.status}`);
  return datos;
}

function mostrarMensaje(texto, esError = false) {
  mensaje.textContent = texto;
  mensaje.style.color = esError ? "#b42318" : "#276341";
}

function normalizar(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
}

function cerrarDetalle() {
  if (detalle.open) detalle.close();
}

async function cargarProveedores() {
  try {
    const idSeleccionado = proveedorSeleccionado?.id;
    proveedores = await llamarApi("/administracion/proveedores");
    mostrarProveedores();
    if (idSeleccionado) {
      const actualizado = proveedores.find((proveedor) => proveedor.id === idSeleccionado);
      if (actualizado) seleccionarProveedor(actualizado);
    }
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}

function mostrarProveedores() {
  listaProveedores.replaceChildren();
  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontrados = proveedores
    .filter((proveedor) => normalizar(proveedor.nombre).includes(busqueda))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es", { sensitivity: "base" }) || Number(a.id) - Number(b.id));

  if (proveedores.length === 0) {
    cantidadResultados.textContent = "Todavía no hay proveedores cargados.";
    cerrarDetalle();
    return;
  }
  cantidadResultados.textContent = encontrados.length === 1 ? "1 proveedor" : `${encontrados.length} proveedores`;
  if (encontrados.length === 0) {
    listaProveedores.textContent = "No se encontraron proveedores.";
    cerrarDetalle();
    return;
  }

  encontrados.forEach((proveedor) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "proveedor";
    boton.textContent = proveedor.nombre;
    if (proveedorSeleccionado?.id === proveedor.id) boton.classList.add("seleccionado");
    boton.addEventListener("click", () => seleccionarProveedor(proveedor));
    listaProveedores.appendChild(boton);
  });
}

function ponerDato(id, etiqueta, valor) {
  document.getElementById(id).textContent = `${etiqueta}: ${valor || "Sin datos"}`;
}

function seleccionarProveedor(proveedor) {
  proveedorSeleccionado = proveedor;
  document.getElementById("detalle-nombre").textContent = proveedor.nombre;
  ponerDato("detalle-id", "ID", proveedor.id);
  ponerDato("detalle-contacto", "Contacto", proveedor.contacto);
  ponerDato("detalle-telefono", "Teléfono", proveedor.telefono);
  ponerDato("detalle-whatsapp", "WhatsApp", proveedor.whatsapp);
  ponerDato("detalle-email", "Correo", proveedor.email);
  ponerDato("detalle-observaciones", "Observaciones", proveedor.observaciones);
  ponerDato("detalle-estado", "Estado", proveedor.activo ? "Activo" : "Inactivo");
  document.getElementById("boton-cambiar-estado").textContent = proveedor.activo ? "Desactivar" : "Activar";
  if (!detalle.open) detalle.showModal();
  mostrarProveedores();
}

campoBusqueda.addEventListener("input", () => {
  proveedorSeleccionado = null;
  cerrarDetalle();
  mostrarProveedores();
  listaProveedores.scrollTop = 0;
});

document.getElementById("boton-cerrar-detalle").addEventListener("click", cerrarDetalle);
detalle.addEventListener("click", (evento) => {
  if (evento.target === detalle) cerrarDetalle();
});
document.getElementById("boton-modificar").addEventListener("click", () => {
  if (proveedorSeleccionado) editarProveedor(proveedorSeleccionado);
});
document.getElementById("boton-cambiar-estado").addEventListener("click", () => {
  if (proveedorSeleccionado) cambiarEstado(proveedorSeleccionado);
});

function editarProveedor(proveedor) {
  cerrarDetalle();
  proveedorEnEdicion = proveedor.id;
  for (const campo of ["nombre", "contacto", "telefono", "whatsapp", "email", "observaciones"]) {
    formulario.elements[campo].value = proveedor[campo] || "";
  }
  document.getElementById("titulo-formulario").textContent = "Modificar proveedor";
  document.getElementById("boton-guardar").textContent = "Guardar cambios";
  document.getElementById("boton-cancelar").hidden = false;
  formulario.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicion() {
  proveedorEnEdicion = null;
  formulario.reset();
  document.getElementById("titulo-formulario").textContent = "Agregar un proveedor";
  document.getElementById("boton-guardar").textContent = "Guardar proveedor";
  document.getElementById("boton-cancelar").hidden = true;
}

document.getElementById("boton-cancelar").addEventListener("click", cancelarEdicion);
formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const botonGuardar = document.getElementById("boton-guardar");
  const estabaEditando = proveedorEnEdicion !== null;
  const datos = Object.fromEntries(["nombre", "contacto", "telefono", "whatsapp", "email", "observaciones"].map((campo) => [campo, formulario.elements[campo].value.trim() || null]));
  const url = estabaEditando ? `/administracion/proveedores/${proveedorEnEdicion}` : "/administracion/proveedores";
  botonGuardar.disabled = true;
  botonGuardar.textContent = "Guardando...";
  try {
    await llamarApi(url, { method: estabaEditando ? "PUT" : "POST", body: JSON.stringify(datos) });
    cancelarEdicion();
    proveedorSeleccionado = null;
    cerrarDetalle();
    mostrarMensaje(estabaEditando ? "Proveedor modificado correctamente." : "Proveedor creado correctamente.");
    await cargarProveedores();
  } catch (error) {
    mostrarMensaje(error.message, true);
  } finally {
    botonGuardar.disabled = false;
    botonGuardar.textContent = proveedorEnEdicion !== null ? "Guardar cambios" : "Guardar proveedor";
  }
});

async function cambiarEstado(proveedor) {
  const accion = proveedor.activo ? "desactivar" : "activar";
  if (!window.confirm(`¿Querés ${accion} al proveedor "${proveedor.nombre}"?`)) return;
  try {
    await llamarApi(`/administracion/proveedores/${proveedor.id}/estado`, {
      method: "PATCH",
      body: JSON.stringify({ activo: !proveedor.activo })
    });
    mostrarMensaje(`Proveedor ${accion === "activar" ? "activado" : "desactivado"} correctamente.`);
    await cargarProveedores();
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}
