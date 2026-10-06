(function () {
  const estilo = document.createElement("style");
  estilo.textContent = `
    #estado-conexion-100t { position: fixed; z-index: 9999; top: 0; left: 50%; transform: translateX(-50%); width: min(100%, 390px); padding: 6px 10px; background: #e8f5e9; color: #24623b; text-align: center; font: 12px Arial, sans-serif; box-shadow: 0 2px 8px #223c6120; }
    #estado-conexion-100t.sin-conexion { background: #fff1d6; color: #744d00; }
    #estado-conexion-100t.con-pendientes { background: #eaf1fb; color: #223c61; }
    #estado-conexion-100t.error-sincronizacion { background: #fde8e7; color: #8b1e18; }
  `;
  document.head.appendChild(estilo);

  const barra = document.createElement("div");
  barra.id = "estado-conexion-100t";
  barra.setAttribute("role", "status");
  barra.setAttribute("aria-live", "polite");
  barra.hidden = true;
  document.body.prepend(barra);

  async function actualizarEstado() {
    const usuario = JSON.parse(sessionStorage.getItem("usuario") || "{}");
    const conectado = navigator.onLine;
    const operaciones = window.offline100t && usuario.id
      ? await window.offline100t.listarPendientes(usuario.id).catch(() => [])
      : [];
    const pendientes = operaciones.length;
    const operacionConError = operaciones.find((operacion) => operacion.error);

    barra.className = "";
    if (operacionConError) {
      barra.textContent = `Hay un cambio pendiente que necesita revisión: ${operacionConError.error || "sin detalle"}`;
      barra.classList.add("error-sincronizacion");
      barra.hidden = false;
    } else if (!conectado) {
      barra.textContent = pendientes
        ? `Sin conexión · ${pendientes} cambio(s) pendiente(s) de sincronizar`
        : "Sin conexión · los datos guardados localmente todavía no se sincronizan";
      barra.classList.add("sin-conexion");
      barra.hidden = false;
    } else if (pendientes) {
      barra.textContent = `${pendientes} cambio(s) pendiente(s) de sincronizar`;
      barra.classList.add("con-pendientes");
      barra.hidden = false;
    } else {
      barra.textContent = "Con conexión";
      barra.hidden = false;
      window.setTimeout(() => { if (navigator.onLine && !barra.classList.contains("con-pendientes")) barra.hidden = true; }, 2500);
    }
  }

  window.addEventListener("online", () => {
    actualizarEstado();
    window.dispatchEvent(new CustomEvent("100t:sincronizar-pendientes"));
  });
  window.addEventListener("offline", actualizarEstado);
  window.addEventListener("100t:cambios-pendientes", actualizarEstado);
  window.addEventListener("100t:error-sincronizacion", (evento) => {
    barra.textContent = `No se pudo sincronizar: ${evento.detail || "revisá el cambio pendiente"}`;
    barra.className = "error-sincronizacion";
    barra.hidden = false;
  });
  window.addEventListener("100t:sincronizado", () => {
    window.dispatchEvent(new CustomEvent("100t:recargar-datos"));
    actualizarEstado();
  });
  window.addEventListener("DOMContentLoaded", () => {
    actualizarEstado();
    if (navigator.onLine) window.dispatchEvent(new CustomEvent("100t:sincronizar-pendientes"));
  }, { once: true });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/app/service-worker.js", { scope: "/app/" })
      .catch(() => {});
  }

  navigator.serviceWorker?.addEventListener("message", (evento) => {
    if (evento.data?.tipo === "SINCRONIZAR_PENDIENTES") {
      window.dispatchEvent(new CustomEvent("100t:sincronizar-pendientes"));
    }
  });
})();
