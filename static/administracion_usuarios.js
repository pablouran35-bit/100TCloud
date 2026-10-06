const token = sessionStorage.getItem("token");
const usuarioSesion = JSON.parse(sessionStorage.getItem("usuario") || "{}");
const rolesSesion = (usuarioSesion.roles || []).map((rol) => rol.toUpperCase());

const contenido = document.getElementById("contenido");
const avisoAcceso = document.getElementById("acceso-denegado");
const formulario = document.getElementById("formulario-usuario");
const campoBusqueda = document.getElementById("busqueda-usuario");
const listaUsuarios = document.getElementById("lista-usuarios");
const cantidadResultados = document.getElementById("cantidad-resultados");
const mensaje = document.getElementById("mensaje");
const detalle = document.getElementById("detalle-usuario");
const dialogoContrasena = document.getElementById("dialogo-contrasena");

let usuarios = [];
let rolesDisponibles = [];
let personasDisponibles = [];
let usuarioSeleccionado = null;
let usuarioEnEdicion = null;

if (!token) {
  window.location.replace("/app/");
} else if (!rolesSesion.includes("ADMINISTRADOR")) {
  avisoAcceso.hidden = false;
} else {
  contenido.hidden = false;
  cargarDatos();
}

async function llamarApi(url, opciones = {}) {
  const cabeceras = { Authorization: `Bearer ${token}`, ...(opciones.headers || {}) };
  if (opciones.body) cabeceras["Content-Type"] = "application/json";
  const respuesta = await fetch(url, { ...opciones, headers: cabeceras });
  const texto = await respuesta.text();
  let datos = {};
  if (texto) {
    try { datos = JSON.parse(texto); }
    catch { throw new Error("El servidor respondió con un error. Revisá la terminal de Uvicorn."); }
  }
  if (!respuesta.ok) throw new Error(datos.detail || `Error ${respuesta.status}`);
  return datos;
}

function mostrarMensaje(texto, error = false) {
  mensaje.textContent = texto;
  mensaje.style.color = error ? "#b42318" : "#276341";
}

function normalizar(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
}

async function cargarDatos() {
  try {
    const idSeleccionado = usuarioSeleccionado?.id;
    const datos = await llamarApi("/administracion/usuarios");
    usuarios = datos.usuarios;
    rolesDisponibles = datos.roles;
    personasDisponibles = datos.personas_disponibles;
    mostrarRoles(usuarioEnEdicion?.roles || []);
    mostrarPersonasDisponibles();
    mostrarUsuarios();
    if (idSeleccionado) {
      const actualizado = usuarios.find((usuario) => usuario.id === idSeleccionado);
      if (actualizado) seleccionarUsuario(actualizado);
    }
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
}

function mostrarRoles(seleccionados = []) {
  const lista = document.getElementById("lista-roles");
  lista.replaceChildren();
  rolesDisponibles.forEach((rol) => {
    const etiqueta = document.createElement("label");
    etiqueta.className = "rol";
    const casilla = document.createElement("input");
    casilla.type = "checkbox";
    casilla.name = "rol_ids";
    casilla.value = rol.id;
    casilla.checked = seleccionados.includes(rol.nombre);
    const nombre = document.createElement("span");
    nombre.textContent = rol.nombre;
    etiqueta.append(casilla, nombre);
    lista.appendChild(etiqueta);
  });
  if (rolesDisponibles.length === 0) {
    lista.textContent = "No hay roles cargados en la base de datos.";
  }
}

function mostrarPersonasDisponibles() {
  const selector = document.getElementById("persona-existente");
  selector.replaceChildren();
  personasDisponibles.forEach((persona) => {
    const opcion = document.createElement("option");
    opcion.value = persona.id;
    opcion.textContent = `${persona.apellido}, ${persona.nombre}`;
    selector.appendChild(opcion);
  });
  if (personasDisponibles.length === 0) {
    const opcion = document.createElement("option");
    opcion.value = "";
    opcion.textContent = "No hay personas sin usuario";
    selector.appendChild(opcion);
  }
  actualizarTipoPersona();
}

function actualizarTipoPersona() {
  const existente = document.getElementById("tipo-persona").value === "existente" && usuarioEnEdicion === null;
  document.getElementById("grupo-persona-existente").hidden = !existente;
  document.getElementById("datos-persona").hidden = existente;
  for (const campo of ["nombre", "apellido"]) formulario.elements[campo].required = !existente;
  const tieneDisponibles = personasDisponibles.length > 0;
  const opcionExistente = document.querySelector('#tipo-persona option[value="existente"]');
  opcionExistente.disabled = !tieneDisponibles;
  if (!tieneDisponibles && document.getElementById("tipo-persona").value === "existente") {
    document.getElementById("tipo-persona").value = "nueva";
  }
}

document.getElementById("tipo-persona").addEventListener("change", actualizarTipoPersona);

function mostrarUsuarios() {
  listaUsuarios.replaceChildren();
  const busqueda = normalizar(campoBusqueda.value.trim());
  const encontrados = usuarios.filter((usuario) =>
    normalizar(`${usuario.nombre} ${usuario.apellido} ${usuario.usuario}`).includes(busqueda)
  );
  cantidadResultados.textContent = encontrados.length === 1 ? "1 usuario" : `${encontrados.length} usuarios`;
  if (usuarios.length === 0) {
    listaUsuarios.textContent = "Todavía no hay usuarios cargados.";
    return;
  }
  if (encontrados.length === 0) {
    listaUsuarios.textContent = "No se encontraron usuarios.";
    return;
  }
  encontrados.forEach((usuario) => {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "usuario-item";
    boton.textContent = `${usuario.apellido}, ${usuario.nombre} · ${usuario.usuario}`;
    if (usuarioSeleccionado?.id === usuario.id) boton.classList.add("seleccionado");
    boton.addEventListener("click", () => seleccionarUsuario(usuario));
    listaUsuarios.appendChild(boton);
  });
}

function cerrarDetalle() {
  if (detalle.open) detalle.close();
}

function seleccionarUsuario(usuario) {
  usuarioSeleccionado = usuario;
  document.getElementById("detalle-nombre").textContent = `${usuario.nombre} ${usuario.apellido}`;
  document.getElementById("detalle-usuario-login").textContent = `Nombre de usuario: ${usuario.usuario}`;
  document.getElementById("detalle-roles").textContent = `Roles: ${usuario.roles.length ? usuario.roles.join(", ") : "Sin roles"}`;
  document.getElementById("detalle-estado").textContent = usuario.activo ? "Estado: Activo" : "Estado: Inactivo";
  document.getElementById("boton-cambiar-estado").textContent = usuario.activo ? "Desactivar" : "Activar";
  if (!detalle.open) detalle.showModal();
  mostrarUsuarios();
}

campoBusqueda.addEventListener("input", () => {
  usuarioSeleccionado = null;
  cerrarDetalle();
  mostrarUsuarios();
  listaUsuarios.scrollTop = 0;
});
document.getElementById("boton-cerrar-detalle").addEventListener("click", cerrarDetalle);
detalle.addEventListener("click", (evento) => { if (evento.target === detalle) cerrarDetalle(); });

function editarUsuario(usuario) {
  cerrarDetalle();
  usuarioEnEdicion = usuario;
  document.getElementById("titulo-formulario").textContent = "Modificar usuario";
  document.getElementById("grupo-usuario").hidden = true;
  document.getElementById("usuario-fijo").hidden = false;
  document.getElementById("usuario-fijo").textContent = `Nombre de usuario fijo: ${usuario.usuario}`;
  document.getElementById("grupo-tipo-persona").hidden = true;
  document.getElementById("grupo-persona-existente").hidden = true;
  document.getElementById("datos-persona").hidden = false;
  formulario.elements.nombre.value = usuario.nombre || "";
  formulario.elements.apellido.value = usuario.apellido || "";
  formulario.elements.telefono.value = usuario.telefono || "";
  formulario.elements.email.value = usuario.email || "";
  document.getElementById("grupo-contrasena").hidden = true;
  formulario.elements.nombre.required = true;
  formulario.elements.apellido.required = true;
  mostrarRoles(usuario.roles);
  document.getElementById("boton-guardar").textContent = "Guardar cambios";
  document.getElementById("boton-cancelar").hidden = false;
  formulario.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.getElementById("boton-modificar").addEventListener("click", () => {
  if (usuarioSeleccionado) editarUsuario(usuarioSeleccionado);
});

function cancelarEdicion() {
  usuarioEnEdicion = null;
  formulario.reset();
  document.getElementById("titulo-formulario").textContent = "Crear usuario";
  document.getElementById("grupo-usuario").hidden = false;
  document.getElementById("usuario-fijo").hidden = true;
  document.getElementById("grupo-tipo-persona").hidden = false;
  document.getElementById("datos-persona").hidden = false;
  document.getElementById("grupo-contrasena").hidden = false;
  document.getElementById("contrasena").required = true;
  document.getElementById("ayuda-contrasena").textContent = "La asignás vos; la persona podrá cambiarla cuando quiera.";
  document.getElementById("boton-guardar").textContent = "Crear usuario";
  document.getElementById("boton-cancelar").hidden = true;
  document.getElementById("tipo-persona").value = "nueva";
  mostrarRoles([]);
  actualizarTipoPersona();
}

document.getElementById("boton-cancelar").addEventListener("click", cancelarEdicion);

function rolesMarcados() {
  return [...formulario.querySelectorAll('input[name="rol_ids"]:checked')].map((casilla) => Number(casilla.value));
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const boton = document.getElementById("boton-guardar");
  const roles = rolesMarcados();
  if (roles.length === 0) {
    mostrarMensaje("Elegí al menos un rol para este usuario.", true);
    return;
  }
  const datosPersona = {
    nombre: formulario.elements.nombre.value.trim(),
    apellido: formulario.elements.apellido.value.trim(),
    telefono: formulario.elements.telefono.value.trim() || null,
    email: formulario.elements.email.value.trim() || null,
  };
  const editando = usuarioEnEdicion !== null;
  let url = "/administracion/usuarios";
  let metodo = "POST";
  let datos;
  if (editando) {
    url += `/${usuarioEnEdicion.id}`;
    metodo = "PUT";
    datos = { ...datosPersona, rol_ids: roles };
  } else {
    const existente = document.getElementById("tipo-persona").value === "existente";
    datos = {
      usuario: formulario.elements.usuario.value.trim(),
      contrasena: formulario.elements.contrasena.value,
      rol_ids: roles,
      persona_id: existente ? Number(document.getElementById("persona-existente").value) : null,
      ...(existente ? {} : datosPersona),
    };
  }
  boton.disabled = true;
  boton.textContent = editando ? "Guardando..." : "Creando...";
  try {
    await llamarApi(url, { method: metodo, body: JSON.stringify(datos) });
    cancelarEdicion();
    usuarioSeleccionado = null;
    cerrarDetalle();
    mostrarMensaje(editando ? "Usuario modificado correctamente." : "Usuario creado correctamente.");
    await cargarDatos();
  } catch (error) {
    mostrarMensaje(error.message, true);
  } finally {
    boton.disabled = false;
    boton.textContent = usuarioEnEdicion ? "Guardar cambios" : "Crear usuario";
  }
});

document.getElementById("boton-restablecer").addEventListener("click", () => {
  if (!usuarioSeleccionado) return;
  document.getElementById("destinatario-contrasena").textContent = `Nueva contraseña para ${usuarioSeleccionado.usuario}`;
  document.getElementById("mensaje-contrasena").textContent = "";
  document.getElementById("nueva-contrasena").value = "";
  cerrarDetalle();
  dialogoContrasena.showModal();
});
document.getElementById("boton-cerrar-contrasena").addEventListener("click", () => dialogoContrasena.close());
dialogoContrasena.addEventListener("click", (evento) => { if (evento.target === dialogoContrasena) dialogoContrasena.close(); });
document.getElementById("formulario-contrasena").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!usuarioSeleccionado) return;
  const boton = document.getElementById("boton-guardar-contrasena");
  boton.disabled = true;
  try {
    await llamarApi(`/administracion/usuarios/${usuarioSeleccionado.id}/contrasena`, {
      method: "PUT",
      body: JSON.stringify({ contrasena: document.getElementById("nueva-contrasena").value }),
    });
    dialogoContrasena.close();
    mostrarMensaje("Contraseña restablecida. Compartila directamente con la persona.");
  } catch (error) {
    document.getElementById("mensaje-contrasena").textContent = error.message;
  } finally {
    boton.disabled = false;
  }
});

document.getElementById("boton-cambiar-estado").addEventListener("click", async () => {
  if (!usuarioSeleccionado) return;
  const usuario = usuarioSeleccionado;
  const accion = usuario.activo ? "desactivar" : "activar";
  if (!window.confirm(`¿Querés ${accion} el acceso de ${usuario.nombre} ${usuario.apellido}?`)) return;
  try {
    await llamarApi(`/administracion/usuarios/${usuario.id}/estado`, {
      method: "PATCH",
      body: JSON.stringify({ activo: !usuario.activo }),
    });
    cerrarDetalle();
    usuarioSeleccionado = null;
    mostrarMensaje(`Usuario ${accion === "activar" ? "activado" : "desactivado"} correctamente.`);
    await cargarDatos();
  } catch (error) {
    mostrarMensaje(error.message, true);
  }
});
