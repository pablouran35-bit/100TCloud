(() => {
  let controlador = null;
  let tokenActivo = '';
  let reintento = null;
  const vistos = new Set();
  let inicializado = false;
  let usuarioActivo = null;
  function guardarVistos() {
    if (usuarioActivo === null) return;
    sessionStorage.setItem('100t-avisos-' + usuarioActivo, JSON.stringify([...vistos]));
  }

  function avisar(evento) {
    const usuario = JSON.parse(sessionStorage.getItem('usuario') || '{}');
    if (!sessionStorage.getItem('token') || vistos.has(evento.id)) return;
    vistos.add(evento.id);
    if (vistos.size > 500) vistos.delete(vistos.values().next().value);
    guardarVistos();
    window.dispatchEvent(new CustomEvent('100t:comunicacion', {detail: evento}));
    if (String(evento.usuario_id) === String(usuario.id)) return;
    let aviso = document.getElementById('aviso-comunicacion-100t');
    if (!aviso) {
      aviso = document.createElement('a');
      aviso.id = 'aviso-comunicacion-100t';
      aviso.href = '/app/bloc_notas.html';
      aviso.setAttribute('role', 'status');
      aviso.style.cssText = 'position:fixed;top:35px;left:5%;width:90%;box-sizing:border-box;padding:16px;background:#223c61;color:white;border-radius:10px;z-index:10000;text-align:center;text-decoration:none;box-shadow:0 3px 15px #0004';
      document.body.appendChild(aviso);
    }
    aviso.textContent = 'Hay una nueva comunicación. Tocá para verla.';
    aviso.hidden = false;
    setTimeout(() => { aviso.hidden = true; }, 12000);
  }

  async function recuperarPendientes(token) {
    try {
      const respuesta = await fetch('/bloc-notas', {
        headers: {Authorization: 'Bearer ' + token}, cache: 'no-store'
      });
      if (!respuesta.ok || token !== sessionStorage.getItem('token')) return;
      const filas = await respuesta.json();
      if (!inicializado) {
        filas.forEach(fila => vistos.add(fila.id));
        inicializado = true;
        guardarVistos();
      } else {
        filas.forEach(avisar);
      }
    } catch (_) {
      // La reconexión del canal volverá a recuperar los mensajes.
    }
    window.dispatchEvent(new Event('100t:reconectado'));
  }

  async function conectar(token) {
    controlador = new AbortController();
    const actual = controlador;
    tokenActivo = token;
    try {
      const respuesta = await fetch('/bloc-notas/eventos', {
        headers: {Authorization: 'Bearer ' + token},
        cache: 'no-store', signal: actual.signal
      });
      if (respuesta.status === 401 || respuesta.status === 403) {
        actual.abort();
        tokenActivo = token;
        return;
      }
      if (!respuesta.ok) throw new Error('Canal no disponible');
      const lector = respuesta.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const {value, done} = await lector.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let corte;
        while ((corte = buffer.indexOf('\n\n')) !== -1) {
          const bloque = buffer.slice(0, corte);
          buffer = buffer.slice(corte + 2);
          for (const linea of bloque.split('\n')) {
            if (!linea.startsWith('data: ')) continue;
            const evento = JSON.parse(linea.slice(6));
            if (evento.tipo === 'comunicacion') avisar(evento);
            else recuperarPendientes(token);
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') console.warn('Se reconectará el bloc de comunicaciones.');
    } finally {
      if (controlador === actual) controlador = null;
      if (!actual.signal.aborted) {
        reintento = setTimeout(() => { tokenActivo = ''; revisarSesion(); }, 3000);
      }
    }
  }

  function revisarSesion() {
    const token = sessionStorage.getItem('token') || '';
    const usuario = JSON.parse(sessionStorage.getItem('usuario') || '{}');
    const roles = usuario.roles || [];
    const permitido = roles.includes('ADMINISTRADOR') || roles.includes('EMPLEADO');
    if (!token || !permitido) {
      controlador?.abort();
      controlador = null;
      tokenActivo = '';
      inicializado = false;
      usuarioActivo = null;
      vistos.clear();
      clearTimeout(reintento);
      document.getElementById('aviso-comunicacion-100t')?.remove();
      return;
    }
    if (String(usuario.id) !== usuarioActivo) {
      usuarioActivo = String(usuario.id);
      vistos.clear();
      const guardados = sessionStorage.getItem('100t-avisos-' + usuarioActivo);
      try {
        JSON.parse(guardados || '[]').forEach(id => vistos.add(id));
        inicializado = guardados !== null && guardados !== undefined;
      } catch (_) { inicializado = false; }
    }
    if (token !== tokenActivo) {
      controlador?.abort();
      clearTimeout(reintento);
      conectar(token);
    }
  }
  // Solo revisa la sesión local; no hace solicitudes periódicas a la base.
  setInterval(revisarSesion, 1000);
  window.addEventListener('online', () => { tokenActivo = ''; revisarSesion(); });
  window.addEventListener('pageshow', revisarSesion);
  window.addEventListener('pagehide', () => { controlador?.abort(); clearTimeout(reintento); tokenActivo = ''; });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { tokenActivo = ''; revisarSesion(); }
  });
  revisarSesion();
})();
