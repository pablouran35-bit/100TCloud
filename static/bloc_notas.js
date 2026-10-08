
const fechaActual = document.getElementById("fecha-actual");
const historial = document.getElementById("historial");
const nombreUsuario = document.getElementById("nombre-usuario");
const textoComunicacion = document.getElementById("texto-comunicacion");
const botonAgregar = document.getElementById("boton-agregar");
const mensaje = document.getElementById("mensaje");
const botonVolver = document.getElementById("boton-volver");


/* ==========================================================
   SESIÓN
   ========================================================== */

function obtenerToken() {
  return sessionStorage.getItem("token") || "";
}


function obtenerUsuario() {
  try {
    return JSON.parse(
      sessionStorage.getItem("usuario") || "{}"
    );
  } catch (error) {
    return {};
  }
}


/* ==========================================================
   FORMATO DE FECHA
   ========================================================== */

function formatearFecha(fechaTexto) {
  if (!fechaTexto) {
    return "";
  }

  const partes = fechaTexto.split("-");

  if (partes.length !== 3) {
    return fechaTexto;
  }

  const fecha = new Date(
    Number(partes[0]),
    Number(partes[1]) - 1,
    Number(partes[2])
  );

  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric"
  }).format(fecha);
}


/* ==========================================================
   FORMATO DE HORA
   ========================================================== */

function formatearHora(horaTexto) {
  if (!horaTexto) {
    return "";
  }

  if (horaTexto.length >= 5) {
    return horaTexto.substring(0, 5);
  }

  return horaTexto;
}


/* ==========================================================
   MOSTRAR MENSAJES
   ========================================================== */

function mostrarMensaje(texto, error = false) {
  mensaje.textContent = texto;

  if (error) {
    mensaje.style.color = "#b42318";
  } else {
    mensaje.style.color = "#287a4b";
  }
}


/* ==========================================================
   RESPUESTA DE LA API
   ========================================================== */

async function obtenerRespuestaAPI(url, opciones = {}) {
  const token = obtenerToken();

  const encabezados = {
    ...(opciones.headers || {})
  };

  if (token) {
    encabezados.Authorization = "Bearer " + token;
  }

  const respuesta = await fetch(url, {
    ...opciones,
    headers: encabezados
  });

  let resultado = null;

  try {
    resultado = await respuesta.json();
  } catch (error) {
    resultado = null;
  }

  if (respuesta.status === 401) {
    sessionStorage.clear();

    window.location.href = "/app/";

    throw new Error(
      "La sesión expiró. Volvé a iniciar sesión."
    );
  }

  if (!respuesta.ok) {
    throw new Error(
      resultado?.detail ||
      "No se pudo completar la operación."
    );
  }

  return resultado;
}


/* ==========================================================
   CARGAR COMUNICACIONES
   ========================================================== */

async function cargarComunicaciones() {
  historial.innerHTML = `
    <div class="estado-cargando">
      Cargando comunicaciones...
    </div>
  `;

  mostrarMensaje("");

  try {
    const comunicaciones = await obtenerRespuestaAPI(
      "/bloc-notas"
    );

    historial.innerHTML = "";

    if (
      !Array.isArray(comunicaciones) ||
      comunicaciones.length === 0
    ) {
      historial.innerHTML = `
        <div class="sin-comunicaciones">
          No hay comunicaciones cargadas para hoy.
        </div>
      `;

      return;
    }

    const primera = comunicaciones[0];

    if (primera.fecha) {
      fechaActual.textContent =
        formatearFecha(primera.fecha);
    }

    comunicaciones.forEach((comunicacion) => {
      const tarjeta = document.createElement("article");
      tarjeta.className = "comunicacion";

      const cabecera = document.createElement("div");
      cabecera.className = "cabecera-comunicacion";

      const nombre = document.createElement("div");
      nombre.className = "nombre";
      nombre.textContent =
        comunicacion.nombre_usuario || "Usuario";

      const hora = document.createElement("div");
      hora.className = "hora";
      hora.textContent =
        formatearHora(comunicacion.hora);

      const texto = document.createElement("div");
      texto.className = "texto";
      texto.textContent =
        comunicacion.texto || "";

      cabecera.appendChild(nombre);
      cabecera.appendChild(hora);

      tarjeta.appendChild(cabecera);
      tarjeta.appendChild(texto);

      historial.appendChild(tarjeta);
    });

  } catch (error) {

    historial.innerHTML = `
      <div class="sin-comunicaciones">
        No se pudieron cargar las comunicaciones.
      </div>
    `;

    mostrarMensaje(
      error.message,
      true
    );
  }
}


/* ==========================================================
   AGREGAR COMUNICACIÓN
   ========================================================== */

async function agregarComunicacion() {
  const texto = textoComunicacion.value.trim();

  if (!texto) {
    mostrarMensaje(
      "Escribí una comunicación antes de agregarla.",
      true
    );

    textoComunicacion.focus();

    return;
  }

  if (texto.length > 4000) {
    mostrarMensaje(
      "La comunicación no puede superar los 4000 caracteres.",
      true
    );

    textoComunicacion.focus();

    return;
  }

  botonAgregar.disabled = true;
  botonAgregar.textContent = "GUARDANDO...";
  mostrarMensaje("");

  try {

    await obtenerRespuestaAPI(
      "/bloc-notas",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          texto: texto
        })
      }
    );

    textoComunicacion.value = "";

    mostrarMensaje(
      "Comunicación agregada correctamente."
    );

    await cargarComunicaciones();

    textoComunicacion.focus();

  } catch (error) {

    mostrarMensaje(
      error.message,
      true
    );

  } finally {

    botonAgregar.disabled = false;
    botonAgregar.textContent =
      "AGREGAR COMUNICACIÓN";
  }
}


/* ==========================================================
   USUARIO ACTUAL
   ========================================================== */

function mostrarUsuarioActual() {
  const usuario = obtenerUsuario();

  const nombreCompleto = [
    usuario.nombre,
    usuario.apellido
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  if (nombreCompleto) {
    nombreUsuario.textContent =
      "Escribir como " + nombreCompleto;
  } else if (usuario.nombre_usuario) {
    nombreUsuario.textContent =
      "Escribir como " + usuario.nombre_usuario;
  } else {
    nombreUsuario.textContent =
      "Escribir comunicación";
  }
}


/* ==========================================================
   VOLVER
   ========================================================== */

botonVolver.addEventListener(
  "click",
  () => {
    window.location.href = "/app/";
  }
);


/* ==========================================================
   BOTÓN AGREGAR
   ========================================================== */

botonAgregar.addEventListener(
  "click",
  agregarComunicacion
);


/* ==========================================================
   CTRL + ENTER
   ========================================================== */

textoComunicacion.addEventListener(
  "keydown",
  (evento) => {

    if (
      evento.ctrlKey &&
      evento.key === "Enter"
    ) {
      evento.preventDefault();

      agregarComunicacion();
    }

  }
);


/* ==========================================================
   INICIO
   ========================================================== */

mostrarUsuarioActual();

const hoy = new Date();

fechaActual.textContent =
  new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric"
  }).format(hoy);

cargarComunicaciones();
