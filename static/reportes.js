const token = sessionStorage.getItem("token");
const selector = document.getElementById("tipo-reporte");
const contenedorFiltros = document.getElementById("filtros");
const contenedorResultados = document.getElementById("resultados");
const configuracion = {
  solicitudes: ["obra_id", "persona_id", "producto_id", "proveedor_id", "area_id", "estado", "desde", "hasta"],
  compras: ["planilla_id", "obra_id", "producto_id", "proveedor_id", "estado", "desde", "hasta"],
  entregas: ["obra_id", "producto_id", "desde", "hasta"],
  obras: [],
};
const etiquetas = {
  obra_id: "Obra", persona_id: "Solicitante", producto_id: "Artículo",
  proveedor_id: "Proveedor", area_id: "Área", planilla_id: "Planilla",
  estado: "Estado", desde: "Fecha desde", hasta: "Fecha hasta",
};
let catalogos = {};

if (!token) window.location.replace("/app/");
else iniciar();

async function llamarApi(url) {
  const respuesta = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const texto = await respuesta.text();
  let datos = {};
  if (texto) {
    try { datos = JSON.parse(texto); }
    catch { throw new Error("El servidor respondió con un error. Revisá la terminal de Uvicorn."); }
  }
  if (!respuesta.ok) throw new Error(datos.detail || `Error ${respuesta.status}`);
  return datos;
}

async function iniciar() {
  try {
    catalogos = await llamarApi("/reportes/catalogos");
    selector.addEventListener("change", () => { dibujarFiltros(); cargarReporte(); });
    document.getElementById("aplicar").addEventListener("click", cargarReporte);
    document.getElementById("limpiar").addEventListener("click", () => { dibujarFiltros(); cargarReporte(); });
    dibujarFiltros();
    await cargarReporte();
  } catch (error) { mensaje(error.message, true); }
}

function crearCampo(nombre) {
  const envoltorio = document.createElement("div");
  envoltorio.className = "campo";
  const etiqueta = document.createElement("label");
  etiqueta.textContent = etiquetas[nombre];
  etiqueta.htmlFor = `filtro-${nombre}`;
  const control = nombre === "desde" || nombre === "hasta"
    ? document.createElement("input") : document.createElement("select");
  control.id = etiqueta.htmlFor;
  control.dataset.filtro = nombre;
  if (control.tagName === "INPUT") control.type = "date";
  else {
    const todos = document.createElement("option");
    todos.value = "";
    todos.textContent = nombre === "estado" ? "Todos los estados" : "Todos";
    control.appendChild(todos);
    // Los catálogos tienen nombres particulares y se resuelven explícitamente aquí.
    const clave = { obra_id: "obras", persona_id: "personas", producto_id: "productos", proveedor_id: "proveedores", area_id: "areas", planilla_id: "planillas" }[nombre];
    const opciones = nombre === "estado"
      ? (catalogos.estados || []).map((x) => ({ id: x, nombre: x }))
      : (catalogos[clave] || []);
    opciones.forEach((dato) => {
      const opcion = document.createElement("option");
      opcion.value = dato.id;
      opcion.textContent = dato.nombre;
      control.appendChild(opcion);
    });
  }
  envoltorio.append(etiqueta, control);
  return envoltorio;
}

function dibujarFiltros() {
  contenedorFiltros.replaceChildren();
  (configuracion[selector.value] || []).forEach((nombre) => contenedorFiltros.appendChild(crearCampo(nombre)));
  contenedorResultados.replaceChildren();
}

function parametrosActuales() {
  const parametros = new URLSearchParams();
  contenedorFiltros.querySelectorAll("[data-filtro]").forEach((campo) => {
    if (campo.value) parametros.set(campo.dataset.filtro, campo.value);
  });
  return parametros.toString();
}

async function cargarReporte() {
  contenedorResultados.textContent = "Cargando reporte…";
  mensaje("");
  try {
    const tipo = selector.value;
    const sufijo = parametrosActuales();
    const filas = await llamarApi(`/reportes/${tipo}${sufijo ? `?${sufijo}` : ""}`);
    mostrarResultados(tipo, filas);
  } catch (error) { contenedorResultados.replaceChildren(); mensaje(error.message, true); }
}

function formatoFecha(valor) {
  if (!valor) return "";
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return valor;
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: valor.includes("T") ? "short" : undefined }).format(fecha);
}

const camposResultado = {
  solicitudes: [
    ["Solicitud", "solicitud"], ["Obra", "obra"], ["Solicitante", "solicitante"],
    ["Artículo", "articulo"], ["Cantidad", "cantidad"], ["Proveedor", "proveedor"],
    ["Área", "area"], ["Estado", "estado"], ["Fecha", "fecha", true], ["Observaciones", "observaciones"],
  ],
  compras: [
    ["Planilla", "planilla"], ["Obra", "obra"], ["Solicitud", "solicitud"],
    ["Artículo", "articulo"], ["Cantidad", "cantidad"], ["Proveedor", "proveedor"],
    ["Estado", "estado"], ["Fecha", "fecha", true], ["Observaciones", "observaciones"],
  ],
  entregas: [
    ["Entrega", "entrega"], ["Solicitud", "solicitud"], ["Obra solicitante", "obra"],
    ["Artículo", "articulo"], ["Cantidad solicitada", "cantidad"], ["Entregada por", "entregado_por"],
    ["Fecha y hora", "fecha", true], ["Observaciones", "observaciones"],
  ],
  obras: [["Obra", "obra"], ["Dirección", "direccion"], ["Contratistas", "contratistas"], ["Estado", "activo"]],
};

function mostrarResultados(tipo, filas) {
  contenedorResultados.replaceChildren();
  mensaje(filas.length === 1 ? "1 resultado" : `${filas.length} resultados`);
  if (!filas.length) { contenedorResultados.textContent = "No hay datos que coincidan con esos filtros."; return; }
  filas.forEach((fila) => {
    const tarjeta = document.createElement("article");
    tarjeta.className = "resultado";
    (camposResultado[tipo] || []).forEach(([etiqueta, campo, fecha]) => {
      if (fila[campo] === null || fila[campo] === undefined || fila[campo] === "") return;
      const linea = document.createElement("p");
      if (campo === "solicitud" || campo === "planilla" || campo === "entrega") {
        const fuerte = document.createElement("strong");
        fuerte.textContent = `${etiqueta}: ${fila[campo]}`;
        linea.appendChild(fuerte);
      } else {
        linea.textContent = `${etiqueta}: ${fecha ? formatoFecha(fila[campo]) : campo === "activo" ? (fila[campo] ? "Activa" : "Inactiva") : fila[campo]}`;
      }
      tarjeta.appendChild(linea);
    });
    contenedorResultados.appendChild(tarjeta);
  });
}

function mensaje(texto, error = false) {
  const elemento = document.getElementById("mensaje");
  elemento.textContent = texto;
  elemento.style.color = error ? "#b42318" : "";
}
