const token = sessionStorage.getItem("token");

const pestanaSolicitudes =
  document.getElementById("pestana-solicitudes");

const pestanaTareas =
  document.getElementById("pestana-tareas");

const pestanaDiaCompras =
  document.getElementById("pestana-dia-compras");

const listaPlanillas =
  document.getElementById("lista-planillas-compra");

const listaSolicitudes =
  document.getElementById("lista-solicitudes-compra");

const listaTareas =
  document.getElementById("lista-tareas-compra");

const listaDiaCompras =
  document.getElementById("lista-dia-compras");

const dialogoSolicitud =
  document.getElementById("dialogo-solicitud-compra");

const dialogoTarea =
  document.getElementById("dialogo-tarea-compra");

const formularioSolicitud =
  document.getElementById("formulario-solicitud-compra");

const formularioTarea =
  document.getElementById("formulario-tarea-compra");


let estadosSolicitud = [];
let proveedores = [];
let planillas = [];
let tareas = [];
let diaCompras = null;

let planillaActual = null;
let solicitudActual = null;
let tareaActual = null;


if (!token) {
  window.location.replace("/app/");
} else {
  iniciar();
}


async function llamarApi(url, opciones = {}) {
  return window.offline100t.solicitarApi(
    url,
    opciones,
    token
  );
}


function mensaje(id, texto, error = false) {
  const elemento = document.getElementById(id);

  if (!elemento) {
    return;
  }

  elemento.textContent = texto;
  elemento.style.color = error ? "#b42318" : "";
}


function fechaLegible(valor) {
  if (!valor) return "Sin fecha";

  const fecha = new Date(
    `${String(valor).slice(0, 10)}T12:00:00`
  );

  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric"
  }).format(fecha);
}


function normalizar(valor) {
  return (valor || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}


/* ==========================================================
   INICIO
   ========================================================== */

async function iniciar() {
  try {

    const inicial =
      await llamarApi("/compras/inicial");

    estadosSolicitud =
      inicial.estados_solicitud || [];

    proveedores =
      inicial.proveedores || [];


    const selectorEstado =
      document.getElementById(
        "estado-solicitud-compra"
      );


    if (selectorEstado) {

      estadosSolicitud.forEach((estado) => {

        const opcion =
          document.createElement("option");

        opcion.value = estado;
        opcion.textContent = estado;

        selectorEstado.appendChild(
          opcion
        );
      });

    }


    const selectorProveedor =
      document.getElementById(
        "proveedor-solicitud-compra"
      );


    if (selectorProveedor) {

      const sinProveedor =
        document.createElement("option");

      sinProveedor.value = "";

      sinProveedor.textContent =
        "Sin proveedor asignado";

      selectorProveedor.appendChild(
        sinProveedor
      );


      proveedores.forEach((proveedor) => {

        const opcion =
          document.createElement("option");

        opcion.value = proveedor.id;
        opcion.textContent = proveedor.nombre;

        selectorProveedor.appendChild(
          opcion
        );

      });

    }


    await Promise.all([
      cargarPlanillas(),
      cargarTareas(),
      cargarDiaCompras()
    ]);

  } catch (error) {

    mensaje(
      "mensaje-planillas-compra",
      error.message,
      true
    );

    mensaje(
      "mensaje-tareas-compra",
      error.message,
      true
    );

    mensaje(
      "mensaje-dia-compras",
      error.message,
      true
    );

  }
}


/* ==========================================================
   PESTAÑAS
   ========================================================== */

function mostrarPestana(nombre) {

  const verSolicitudes =
    nombre === "solicitudes";

  const verTareas =
    nombre === "tareas";

  const verDiaCompras =
    nombre === "dia-compras";


  const seccionSolicitudes =
    document.getElementById(
      "seccion-solicitudes"
    );

  const seccionTareas =
    document.getElementById(
      "seccion-tareas"
    );

  const seccionDiaCompras =
    document.getElementById(
      "seccion-dia-compras"
    );


  if (seccionSolicitudes) {

    seccionSolicitudes.hidden =
      !verSolicitudes;

  }


  if (seccionTareas) {

    seccionTareas.hidden =
      !verTareas;

  }


  if (seccionDiaCompras) {

    seccionDiaCompras.hidden =
      !verDiaCompras;

  }


  if (pestanaSolicitudes) {

    pestanaSolicitudes.classList.toggle(
      "activa",
      verSolicitudes
    );

  }


  if (pestanaTareas) {

    pestanaTareas.classList.toggle(
      "activa",
      verTareas
    );

  }


  if (pestanaDiaCompras) {

    pestanaDiaCompras.classList.toggle(
      "activa",
      verDiaCompras
    );

  }


  /*
   * Al entrar al Día de Compras
   * actualizamos nuevamente la información.
   */

  if (verDiaCompras) {

    cargarDiaCompras();

  }

}


/* ----------------------------------------------------------
   BOTÓN SOLICITUDES
   ---------------------------------------------------------- */

if (pestanaSolicitudes) {

  pestanaSolicitudes.addEventListener(
    "click",
    function () {

      mostrarPestana(
        "solicitudes"
      );

    }
  );

}


/* ----------------------------------------------------------
   BOTÓN TAREAS
   ---------------------------------------------------------- */

if (pestanaTareas) {

  pestanaTareas.addEventListener(
    "click",
    function () {

      mostrarPestana(
        "tareas"
      );

    }
  );

}


/* ----------------------------------------------------------
   BOTÓN DÍA DE COMPRAS
   ---------------------------------------------------------- */

if (pestanaDiaCompras) {

  pestanaDiaCompras.addEventListener(
    "click",
    function () {

      console.log(
        "100T: botón Día de Compras presionado"
      );

      mostrarPestana(
        "dia-compras"
      );

    }
  );

} else {

  console.error(
    "100T: NO se encontró el botón #pestana-dia-compras"
  );

}


/* ==========================================================
   SOLICITUDES / PLANILLAS
   ========================================================== */

async function cargarPlanillas() {

  listaPlanillas.textContent =
    "Cargando planillas...";


  try {

    planillas =
      await llamarApi(
        "/compras/planillas"
      );

    mostrarPlanillas();

  } catch (error) {

    listaPlanillas.replaceChildren();

    mensaje(
      "mensaje-planillas-compra",
      error.message,
      true
    );

  }
}


function mostrarPlanillas() {

  listaPlanillas.replaceChildren();

  mensaje(
    "mensaje-planillas-compra",
    ""
  );


  const buscar =
    normalizar(
      document
        .getElementById(
          "buscar-planilla-compra"
        )
        .value
        .trim()
    );


  const encontradas =
    planillas.filter(
      (planilla) =>
        normalizar(
          `${planilla.id} ${planilla.obra}`
        ).includes(buscar)
    );


  document.getElementById(
    "cantidad-planillas-compra"
  ).textContent =
    encontradas.length === 1
      ? "1 planilla"
      : `${encontradas.length} planillas`;


  if (!encontradas.length) {

    listaPlanillas.textContent =
      planillas.length
        ? "No hay coincidencias."
        : "No hay planillas con solicitudes por resolver.";

    return;

  }


  encontradas.forEach((planilla) => {

    const boton =
      document.createElement("button");

    boton.type = "button";
    boton.className = "item";


    const nombre =
      document.createElement("strong");

    nombre.textContent =
      `Planilla N.º ${planilla.id} · ${planilla.obra}`;


    const detalle =
      document.createElement("small");

    detalle.textContent =
      `${fechaLegible(planilla.fecha_compra)} · ${planilla.solicitudes} solicitudes por resolver`;


    boton.append(
      nombre,
      detalle
    );


    boton.addEventListener(
      "click",
      () => abrirPlanilla(planilla.id)
    );


    listaPlanillas.appendChild(
      boton
    );

  });

}


document
  .getElementById(
    "buscar-planilla-compra"
  )
  .addEventListener(
    "input",
    mostrarPlanillas
  );


async function abrirPlanilla(planillaId) {

  try {

    planillaActual =
      await llamarApi(
        `/compras/planillas/${planillaId}`
      );


    document.getElementById(
      "titulo-planilla-compra"
    ).textContent =
      `Planilla N.º ${planillaActual.id} · ${planillaActual.obra}`;


    document.getElementById(
      "fecha-planilla-compra"
    ).textContent =
      `Próxima compra: ${fechaLegible(
        planillaActual.fecha_compra
      )}`;


    mostrarSolicitudes();


    document.getElementById(
      "vista-planillas"
    ).hidden = true;


    document.getElementById(
      "vista-solicitudes"
    ).hidden = false;

  } catch (error) {

    mensaje(
      "mensaje-planillas-compra",
      error.message,
      true
    );

  }

}


function mostrarSolicitudes() {

  listaSolicitudes.replaceChildren();


  if (!planillaActual.solicitudes.length) {

    listaSolicitudes.textContent =
      "Esta planilla ya no tiene solicitudes por resolver.";

    return;

  }


  planillaActual.solicitudes.forEach(
    (solicitud) => {

      const boton =
        document.createElement("button");

      boton.type = "button";
      boton.className = "item";


      const titulo =
        document.createElement("strong");

      titulo.textContent =
        `${solicitud.cantidad} — ${solicitud.producto}`;


      const proveedor =
        document.createElement("small");

      proveedor.textContent =
        solicitud.proveedor
          ? `Proveedor: ${solicitud.proveedor}`
          : "Sin proveedor asignado";


      const estado =
        document.createElement("span");

      estado.className = "estado";

      estado.dataset.estado =
        solicitud.estado;

      estado.textContent =
        solicitud.estado;


      boton.append(
        titulo,
        proveedor,
        estado
      );


      boton.addEventListener(
        "click",
        () => abrirSolicitud(solicitud)
      );


      listaSolicitudes.appendChild(
        boton
      );

    }
  );

}


/* ==========================================================
   DÍA DE COMPRAS
   ========================================================== */

async function cargarDiaCompras() {

  if (!listaDiaCompras) {

    console.error(
      "100T: NO se encontró #lista-dia-compras"
    );

    return;

  }


  listaDiaCompras.textContent =
    "Cargando Día de Compras...";


  try {

    diaCompras =
      await llamarApi(
        "/compras/dia-compras"
      );


    console.log(
      "100T: datos Día de Compras:",
      diaCompras
    );


    mostrarDiaCompras();

  } catch (error) {

    console.error(
      "100T: error cargando Día de Compras:",
      error
    );


    listaDiaCompras.replaceChildren();

    mensaje(
      "mensaje-dia-compras",
      error.message,
      true
    );

  }

}


function mostrarDiaCompras() {

  if (!listaDiaCompras) {
    return;
  }


  listaDiaCompras.replaceChildren();


  mensaje(
    "mensaje-dia-compras",
    ""
  );


  if (!diaCompras) {

    listaDiaCompras.textContent =
      "No hay información del Día de Compras.";

    return;

  }


  const titulo =
    document.getElementById(
      "titulo-dia-compras"
    );


  if (titulo) {

    titulo.textContent =
      `🛒 Día de Compras · ${fechaLegible(
        diaCompras.fecha_compra
      )}`;

  }


  const solicitudes =
    Array.isArray(
      diaCompras.solicitudes
    )
      ? diaCompras.solicitudes
      : [];


  const cantidad =
    document.getElementById(
      "cantidad-dia-compras"
    );


  if (cantidad) {

    cantidad.textContent =
      solicitudes.length === 1
        ? "1 solicitud"
        : `${solicitudes.length} solicitudes`;

  }


  if (!solicitudes.length) {

    listaDiaCompras.textContent =
      "No hay solicitudes correspondientes a este Día de Compras.";

    return;

  }


  /*
   * Agrupamos las solicitudes por obra.
   */

  const grupos =
    new Map();


  solicitudes.forEach(
    (solicitud) => {

      const obra =
        solicitud.obra ||
        "Obra sin nombre";


      if (!grupos.has(obra)) {

        grupos.set(
          obra,
          []
        );

      }


      grupos
        .get(obra)
        .push(solicitud);

    }
  );


  /*
   * Mostramos cada obra y debajo
   * sus solicitudes en formato compacto.
   */

  grupos.forEach(
    (solicitudesObra, obra) => {

      const grupo =
        document.createElement("div");

      grupo.className =
        "grupo-obra";


      const tituloObra =
        document.createElement("h3");

      tituloObra.className =
        "titulo-obra";

      tituloObra.textContent =
        obra;


      grupo.appendChild(
        tituloObra
      );


      solicitudesObra.forEach(
        (solicitud) => {

          const fila =
            document.createElement("div");

          fila.className =
            "fila-dia-compras";


          /*
           * Cantidad
           */

          const cantidad =
            document.createElement("span");

          cantidad.className =
            "cantidad";

          cantidad.textContent =
            solicitud.cantidad;


          /*
           * Producto
           */

          const producto =
            document.createElement("span");

          producto.className =
            "producto";

          producto.textContent =
            solicitud.producto ||
            "Sin producto";


          /*
           * Estado
           */

          const estado =
            document.createElement("span");

          estado.className =
            "estado";

          estado.dataset.estado =
            solicitud.estado;

          estado.textContent =
            solicitud.estado ||
            "SIN ESTADO";


          /*
           * Una sola línea:
           *
           * 10 × Cemento                  PENDIENTE
           */

          fila.append(
            cantidad,
            producto,
            estado
          );


          grupo.appendChild(
            fila
          );

        }
      );


      listaDiaCompras.appendChild(
        grupo
      );

    }
  );

}


/* ==========================================================
   HISTORIAL
   ========================================================== */

function mostrarHistorial(
  idLista,
  registros
) {

  const lista =
    document.getElementById(
      idLista
    );

  lista.replaceChildren();


  if (!registros.length) {

    const item =
      document.createElement("li");

    item.textContent =
      "No hay movimientos registrados.";

    lista.appendChild(
      item
    );

    return;

  }


  registros.forEach(
    (registro) => {

      const item =
        document.createElement("li");

      item.className =
        "registro";


      const estado =
        document.createElement("strong");

      estado.textContent =
        registro.estado;


      const quien =
        document.createElement("small");

      quien.textContent =
        `${registro.fecha_hora} · ${registro.usuario}`;


      const observaciones =
        document.createElement("small");

      observaciones.textContent =
        registro.observaciones ||
        "Sin observaciones";


      item.append(
        estado,
        quien,
        observaciones
      );


      lista.appendChild(
        item
      );

    }
  );

}


/* ==========================================================
   GESTIÓN DE SOLICITUD
   ========================================================== */

function abrirSolicitud(solicitud) {

  solicitudActual =
    solicitud;


  document.getElementById(
    "titulo-solicitud-compra"
  ).textContent =
    `Gestionar solicitud N.º ${solicitud.id}`;


  document.getElementById(
    "datos-solicitud-compra"
  ).textContent =
    `${solicitud.cantidad} · ${solicitud.producto} · Planilla ${planillaActual.id} · ${planillaActual.obra}`;


  const selectorEstado =
    document.getElementById(
      "estado-solicitud-compra"
    );


  if (
    ![...selectorEstado.options]
      .some(
        (opcion) =>
          opcion.value ===
          solicitud.estado
      )
  ) {

    const opcionExistente =
      document.createElement("option");

    opcionExistente.value =
      solicitud.estado;

    opcionExistente.textContent =
      solicitud.estado;

    selectorEstado.appendChild(
      opcionExistente
    );

  }


  selectorEstado.value =
    solicitud.estado;


  document.getElementById(
    "proveedor-solicitud-compra"
  ).value =
    solicitud.proveedor_id || "";


  document.getElementById(
    "observaciones-solicitud-compra"
  ).value =
    solicitud.observaciones;


  mensaje(
    "mensaje-guardar-solicitud",
    ""
  );


  mostrarHistorial(
    "historial-solicitud-compra",
    solicitud.historial
  );


  dialogoSolicitud.showModal();

}


formularioSolicitud.addEventListener(
  "submit",
  async (evento) => {

    evento.preventDefault();


    if (
      !solicitudActual ||
      !planillaActual
    ) {
      return;
    }


    const boton =
      document.getElementById(
        "boton-guardar-solicitud"
      );


    const estadoNuevo =
      document.getElementById(
        "estado-solicitud-compra"
      ).value;


    const proveedorNuevo =
      Number(
        document.getElementById(
          "proveedor-solicitud-compra"
        ).value
      ) || null;


    const observacionesNuevas =
      document
        .getElementById(
          "observaciones-solicitud-compra"
        )
        .value
        .trim() || null;


    const estadoAnterior =
      solicitudActual.estado || "";


    const proveedorAnterior =
      solicitudActual.proveedor_id || null;


    const observacionesAnteriores =
      solicitudActual.observaciones || null;


    boton.disabled = true;


    try {

      const estaOffline =
        !navigator.onLine;


      if (estaOffline) {

        const proveedorCambio =
          proveedorNuevo !==
          proveedorAnterior;


        const observacionesCambio =
          (observacionesNuevas || null) !==
          (observacionesAnteriores || null);


        if (
          proveedorCambio ||
          observacionesCambio
        ) {

          throw new Error(
            "Sin conexión solo se puede modificar el estado de la solicitud. " +
            "El proveedor y las observaciones deben modificarse cuando vuelva la conexión."
          );

        }


        if (
          estadoNuevo ===
          estadoAnterior
        ) {

          throw new Error(
            "No hay ningún cambio de estado para guardar."
          );

        }


        const resultado =
          await llamarApi(
            `/compras/planillas/${planillaActual.id}/solicitudes/${solicitudActual.id}/estado`,
            {
              method: "PATCH",

              body: JSON.stringify({
                estado: estadoNuevo,

                estado_anterior:
                  estadoAnterior,
              }),

            }
          );


        solicitudActual.estado =
          estadoNuevo;


        const nuevoRegistro = {

          fecha_hora:
            "Pendiente de sincronización",

          estado:
            estadoNuevo,

          usuario:
            "Este dispositivo",

          observaciones:
            solicitudActual.observaciones ||
            "",

        };


        if (
          !Array.isArray(
            solicitudActual.historial
          )
        ) {

          solicitudActual.historial =
            [];

        }


        solicitudActual.historial.push(
          nuevoRegistro
        );


        document.getElementById(
          "estado-solicitud-compra"
        ).value =
          estadoNuevo;


        mostrarHistorial(
          "historial-solicitud-compra",
          solicitudActual.historial
        );


        mostrarSolicitudes();


        dialogoSolicitud.close();


        mensaje(
          "mensaje-solicitudes-compra",

          resultado &&
          resultado.pendiente
            ? resultado.mensaje
            : "Estado actualizado localmente. Quedará pendiente de sincronización."
        );


        return;

      }


      const resultado =
        await llamarApi(
          `/compras/planillas/${planillaActual.id}/solicitudes/${solicitudActual.id}`,
          {
            method: "PUT",

            body: JSON.stringify({

              estado:
                estadoNuevo,

              proveedor_id:
                proveedorNuevo,

              observaciones:
                observacionesNuevas,

            }),

          }
        );


      planillaActual =
        await llamarApi(
          `/compras/planillas/${planillaActual.id}`
        );


      await cargarPlanillas();


      mostrarSolicitudes();


      /*
       * Actualizamos también el Día de Compras
       * porque el estado puede haber cambiado.
       */

      await cargarDiaCompras();


      dialogoSolicitud.close();


      mensaje(
        "mensaje-solicitudes-compra",

        resultado.pendiente
          ? resultado.mensaje
          : "Solicitud actualizada; el cambio quedó en su historial."
      );


    } catch (error) {

      mensaje(
        "mensaje-guardar-solicitud",
        error.message,
        true
      );


    } finally {

      boton.disabled =
        false;

    }

  }
);


/* ==========================================================
   VOLVER A PLANILLAS
   ========================================================== */

document
  .getElementById(
    "volver-planillas-compra"
  )
  .addEventListener(
    "click",
    async () => {

      document.getElementById(
        "vista-solicitudes"
      ).hidden = true;


      document.getElementById(
        "vista-planillas"
      ).hidden = false;


      await cargarPlanillas();

    }
  );


/* ==========================================================
   TAREAS
   ========================================================== */

async function cargarTareas() {

  listaTareas.textContent =
    "Cargando tareas...";


  try {

    tareas =
      await llamarApi(
        "/compras/tareas"
      );


    mostrarTareas();

  } catch (error) {

    listaTareas.replaceChildren();

    mensaje(
      "mensaje-tareas-compra",
      error.message,
      true
    );

  }

}


function mostrarTareas() {

  listaTareas.replaceChildren();

  mensaje(
    "mensaje-tareas-compra",
    ""
  );


  const buscar =
    normalizar(
      document
        .getElementById(
          "buscar-tarea-compra"
        )
        .value
        .trim()
    );


  const encontradas =
    tareas.filter(
      (tarea) =>
        normalizar(
          `${tarea.descripcion} ${tarea.solicitante} ${tarea.estado}`
        ).includes(buscar)
    );


  document.getElementById(
    "cantidad-tareas-compra"
  ).textContent =
    encontradas.length === 1
      ? "1 tarea pendiente"
      : `${encontradas.length} tareas pendientes`;


  if (!encontradas.length) {

    listaTareas.textContent =
      tareas.length
        ? "No hay coincidencias."
        : "No hay tareas pendientes o en proceso.";

    return;

  }


  encontradas.forEach((tarea) => {

    const boton =
      document.createElement("button");

    boton.type = "button";
    boton.className = "item";


    const descripcion =
      document.createElement("strong");

    descripcion.textContent =
      tarea.descripcion;


    const detalle =
      document.createElement("small");

    detalle.textContent =
      `Tarea N.º ${tarea.id} · ${tarea.solicitante} · ${fechaLegible(tarea.fecha_solicitud)}`;


    const estado =
      document.createElement("span");

    estado.className =
      "estado";

    estado.dataset.estado =
      tarea.estado;

    estado.textContent =
      tarea.estado;


    boton.append(
      descripcion,
      detalle,
      estado
    );


    boton.addEventListener(
      "click",
      () => abrirTarea(tarea.id)
    );


    listaTareas.appendChild(
      boton
    );

  });

}


document
  .getElementById(
    "buscar-tarea-compra"
  )
  .addEventListener(
    "input",
    mostrarTareas
  );


async function abrirTarea(tareaId) {

  try {

    tareaActual =
      await llamarApi(
        `/compras/tareas/${tareaId}`
      );


    document.getElementById(
      "titulo-tarea-compra"
    ).textContent =
      `Gestionar tarea N.º ${tareaActual.id}`;


    document.getElementById(
      "datos-tarea-compra"
    ).textContent =
      `${tareaActual.descripcion} · ${tareaActual.solicitante} · ${fechaLegible(tareaActual.fecha_solicitud)}`;


    document.getElementById(
      "estado-tarea-compra"
    ).value =
      tareaActual.estado;


    document.getElementById(
      "observaciones-tarea-compra"
    ).value =
      tareaActual.observaciones;


    mensaje(
      "mensaje-guardar-tarea",
      ""
    );


    mostrarHistorial(
      "historial-tarea-compra",
      tareaActual.historial
    );


    dialogoTarea.showModal();

  } catch (error) {

    mensaje(
      "mensaje-tareas-compra",
      error.message,
      true
    );

  }

}


formularioTarea.addEventListener(
  "submit",
  async (evento) => {

    evento.preventDefault();


    if (!tareaActual) {
      return;
    }


    const boton =
      document.getElementById(
        "boton-guardar-tarea-compra"
      );


    boton.disabled = true;


    try {

      const resultado =
        await llamarApi(
          `/compras/tareas/${tareaActual.id}`,
          {
            method: "PUT",

            body: JSON.stringify({

              estado:
                document.getElementById(
                  "estado-tarea-compra"
                ).value,

              observaciones:
                document
                  .getElementById(
                    "observaciones-tarea-compra"
                  )
                  .value
                  .trim() || null,

            }),

          }
        );


      dialogoTarea.close();


      await cargarTareas();


      mensaje(
        "mensaje-tareas-compra",

        resultado.pendiente
          ? resultado.mensaje
          : "Tarea actualizada; el cambio quedó en su historial."
      );


    } catch (error) {

      mensaje(
        "mensaje-guardar-tarea",
        error.message,
        true
      );


    } finally {

      boton.disabled = false;

    }

  }
);


/* ==========================================================
   RECARGA GENERAL
   ========================================================== */

window.addEventListener(
  "100t:recargar-datos",
  async () => {

    await Promise.all([
      cargarPlanillas(),
      cargarTareas(),
      cargarDiaCompras()
    ]);


    if (planillaActual) {

      await abrirPlanilla(
        planillaActual.id
      );

    }


    if (tareaActual) {

      await abrirTarea(
        tareaActual.id
      );

    }

  }
);


/* ==========================================================
   CERRAR DIÁLOGOS
   ========================================================== */

document
  .querySelectorAll("[data-cerrar]")
  .forEach(
    (boton) => {

      boton.addEventListener(
        "click",
        () => {

          const dialogo =
            document.getElementById(
              boton.dataset.cerrar
            );

          if (dialogo) {

            dialogo.close();

          }

        }
      );

    }
  );