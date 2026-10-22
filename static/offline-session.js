/* Solo se recuerda la sesión si el usuario prepara explícitamente su teléfono. */
(() => {
  try {
    const s=JSON.parse(localStorage.getItem('100t-sesion-dispositivo') || 'null');
    if(!sessionStorage.getItem('token') && s?.token && s?.usuario?.id) {
      sessionStorage.setItem('token',s.token);
      sessionStorage.setItem('usuario',JSON.stringify(s.usuario));
    }
  }catch { localStorage.removeItem('100t-sesion-dispositivo'); }
})();
