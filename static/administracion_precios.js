"use strict";
const $ = id => document.getElementById(id);
const token = sessionStorage.getItem("token");
const roles = (JSON.parse(sessionStorage.getItem("usuario") || "{}").roles || []).map(r => r.toUpperCase());
const dinero = v => v == null ? "Sin precio" : new Intl.NumberFormat("es-AR", {style:"currency",currency:"ARS"}).format(v);
let articulos = [], seleccionado = null, filtros = {planillas: []};
let revision = 0;
function mensaje(texto) { $("mensaje").textContent = texto; }
async function api(ruta, opciones = {}) {
  const r = await fetch("/administracion/precios" + ruta, {...opciones, headers: {
    Authorization: `Bearer ${token}`, "Content-Type": "application/json"
  }, cache: "no-store"});
  if (!r.ok) {
    let datos; try { datos = await r.json(); } catch { /* respuesta sin JSON */ }
    throw Error(typeof datos?.detail === "string" ? datos.detail : `No se pudo completar la operación (${r.status}).`);
  }
  return r.json();
}
function celda(fila, texto) { const c = document.createElement("td"); c.textContent = texto; fila.append(c); return c; }
function mostrarCatalogo() {
  $("catalogo").replaceChildren();
  const busqueda = $("busqueda").value.trim().toLocaleLowerCase("es");
  for (const a of articulos.filter(a => a.nombre.toLocaleLowerCase("es").includes(busqueda))) {
    const fila = document.createElement("tr");
    celda(fila, a.nombre + (a.activo ? "" : " (inactivo)")); celda(fila, a.unidad); celda(fila, dinero(a.precio_unitario));
    const boton = document.createElement("button"); boton.type = "button"; boton.textContent = "Editar precio";
    boton.onclick = () => {
      seleccionado = a.id; $("editor").hidden = false;
      $("articulo-elegido").textContent = `${a.nombre} · ${a.unidad}`;
      $("precio").value = a.precio_unitario ?? ""; $("precio").focus();
    };
    celda(fila, "").append(boton); $("catalogo").append(fila);
  }
}
function opcionesPlanillas() {
  $("planilla").replaceChildren(new Option("Todas", ""));
  for (const p of filtros.planillas) {
    if ($("obra").value && String(p.obra_id) !== $("obra").value) continue;
    if ($("fecha").value && String(p.fecha_compra).slice(0,10) !== $("fecha").value) continue;
    $("planilla").add(new Option(`#${p.id} · ${p.obra} · ${String(p.fecha_compra).slice(0,10)}`, p.id));
  }
}
function editarPrecio(id) {
  const a = articulos.find(a => a.id === id);
  if(!a) return;
  seleccionado = id; $("editor").hidden = false;
  $("articulo-elegido").textContent = `${a.nombre} · ${a.unidad}`;
  $("precio").value = a.precio_unitario ?? "";
  $("editor").scrollIntoView({behavior:"smooth",block:"center"});
  $("precio").focus({preventScroll:true});
}
function invalidar() {
  $("sin-precio").replaceChildren();
  revision++; $("total").textContent = ""; $("resumen").replaceChildren();
  $("aviso").textContent = "Los filtros cambiaron. Presioná Calcular para actualizar.";
}
async function calcular() {
  const version = ++revision;
  $("sin-precio").replaceChildren();
  $("total").textContent = "Calculando…"; $("resumen").replaceChildren(); $("aviso").textContent = "";
  const query = new URLSearchParams();
  for (const [id, clave] of [["fecha","fecha"],["obra","obra_id"],["planilla","planilla_id"]]) if ($(id).value) query.set(clave,$(id).value);
  query.set("solo_aprobadas", $("aprobadas").checked);
  try {
    const r = await api("/estimacion?" + query);
    if (version !== revision) return;
    $("total").textContent = `${r.completo ? "Efectivo estimado" : "Estimación parcial"}: ${dinero(r.total_estimado)}`;
    $("alcance").textContent = `${r.solicitudes} solicitudes · ${r.articulos.length} artículos`;
    $("aviso").textContent = r.articulos_sin_precio ? `Faltan precios para ${r.articulos_sin_precio} artículos (${r.solicitudes_sin_precio} solicitudes). No están incluidos en el importe.` : (r.solicitudes ? "Todos los artículos incluidos tienen precio." : "No hay solicitudes pendientes con estos filtros.");
    const faltantes = r.articulos.filter(a => a.precio_unitario == null);
    if(!faltantes.length) $("sin-precio").textContent = "No hay artículos sin precio en esta selección.";
    for(const a of faltantes) {
      const li = document.createElement("li");
      li.textContent = `${a.nombre} · ${a.cantidad} ${a.unidad} · ${a.solicitudes} solicitudes `;
      const boton = document.createElement("button"); boton.type = "button";
      boton.textContent = "Cargar precio"; boton.onclick = () => editarPrecio(a.id);
      li.append(boton); $("sin-precio").append(li);
    }
    for (const a of r.articulos) {
      const fila = document.createElement("tr");
      [a.nombre, a.unidad, new Intl.NumberFormat("es-AR", {maximumFractionDigits:6}).format(a.cantidad), dinero(a.precio_unitario), dinero(a.subtotal)].forEach(v => celda(fila,v));
      $("resumen").append(fila);
    }
  } catch (e) { if (version === revision) { $("total").textContent = ""; $("aviso").textContent = e.message; } }
}
$("busqueda").oninput = mostrarCatalogo;
$("cancelar").onclick = () => { seleccionado = null; $("editor").hidden = true; };
$("editor").onsubmit = async e => {
  e.preventDefault(); if (seleccionado == null) return;
  $("guardar").disabled = true;
  try {
    const id = seleccionado;
    const respuesta = await api(`/${id}`, {method:"PATCH", body:JSON.stringify({precio_unitario:$("precio").value.trim() || null})});
    articulos.find(a => a.id === id).precio_unitario = respuesta.precio_unitario;
    $("editor").hidden = true; seleccionado = null;
    mostrarCatalogo(); mensaje("Precio de referencia guardado."); await calcular();
  } catch (e) { mensaje(e.message); }
  finally { $("guardar").disabled = false; }
};
$("filtros").onsubmit = e => { e.preventDefault(); calcular(); };
for (const id of ["fecha","obra","planilla","aprobadas"]) $(id).onchange = () => {
  if (id === "fecha" || id === "obra") opcionesPlanillas(); invalidar();
};
async function iniciar() {
  if (!token) { location.replace("/app/"); return; }
  if (!roles.some(r => ["ADMINISTRADOR","EMPLEADO"].includes(r))) { mensaje("Esta sección es solo para empleados y administradores."); return; }
  $("contenido").hidden = false;
  try {
    [articulos, filtros] = await Promise.all([api(""), api("/filtros")]);
    for (const o of filtros.obras) $("obra").add(new Option(o.nombre,o.id));
    const hoy = new Intl.DateTimeFormat("en-CA", {timeZone:"America/Argentina/Buenos_Aires",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
    const d = new Date(hoy + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + (2 - d.getUTCDay() + 7) % 7);
    $("fecha").value = d.toISOString().slice(0,10);
    mostrarCatalogo(); opcionesPlanillas(); await calcular();
  } catch (e) { mensaje(e.message); }
}
iniciar();
