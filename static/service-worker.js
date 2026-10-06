const CACHE_NAME = "100tcompras-shell-v3";
const APP_FILES = [
  "/app/",
  "/app/index.html",
  "/app/manifest.webmanifest",
  "/app/icon.svg",
  "/app/offline.js",
  "/app/offline-db.js",
  "/app/planillas.html",
  "/app/planillas.js",
  "/app/tareas.html",
  "/app/tareas.js",
  "/app/compras.html",
  "/app/compras.js",
  "/app/entregas.html",
  "/app/entregas.js",
  "/app/cambiar_contrasena.html",
  "/app/cambiar_contrasena.js",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres.filter((nombre) => nombre.startsWith("100tcompras-shell-") && nombre !== CACHE_NAME)
          .map((nombre) => caches.delete(nombre))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const solicitud = evento.request;
  const url = new URL(solicitud.url);
  if (solicitud.method !== "GET" || url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith("/app/")) return;

  if (solicitud.mode === "navigate") {
    evento.respondWith(
      fetch(solicitud).catch(async () => {
        const guardada = await caches.match(solicitud);
        return guardada || caches.match("/app/index.html");
      })
    );
    return;
  }

  evento.respondWith(
    caches.match(solicitud).then((guardada) => guardada || fetch(solicitud))
  );
});

self.addEventListener("sync", (evento) => {
  if (evento.tag === "100t-sincronizar-pendientes") {
    evento.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((clientes) => clientes.forEach((cliente) => cliente.postMessage({ tipo: "SINCRONIZAR_PENDIENTES" }))));
  }
});
