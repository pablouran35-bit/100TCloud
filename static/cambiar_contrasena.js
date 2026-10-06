const token = sessionStorage.getItem("token");
const formulario = document.getElementById("formulario-contrasena");
const mensaje = document.getElementById("mensaje");

if (!token) window.location.replace("/app/");

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const actual = document.getElementById("contrasena-actual").value;
  const nueva = document.getElementById("contrasena-nueva").value;
  const confirmar = document.getElementById("confirmar-contrasena").value;
  const boton = document.getElementById("boton-guardar");
  if (nueva !== confirmar) {
    mensaje.textContent = "Las contraseñas nuevas no coinciden.";
    mensaje.style.color = "#b42318";
    return;
  }
  boton.disabled = true;
  mensaje.textContent = "Guardando...";
  try {
    const respuesta = await fetch("/auth/cambiar-contrasena", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ contrasena_actual: actual, contrasena_nueva: nueva }),
    });
    const texto = await respuesta.text();
    let datos = {};
    if (texto) {
      try { datos = JSON.parse(texto); }
      catch { throw new Error("El servidor respondió con un error. Revisá la terminal de Uvicorn."); }
    }
    if (!respuesta.ok) throw new Error(datos.detail || `Error ${respuesta.status}`);
    mensaje.textContent = "Contraseña cambiada. Volvé a ingresar con la nueva contraseña.";
    mensaje.style.color = "#276341";
    sessionStorage.clear();
    setTimeout(() => window.location.replace("/app/"), 1200);
  } catch (error) {
    mensaje.textContent = error.message;
    mensaje.style.color = "#b42318";
  } finally {
    boton.disabled = false;
  }
});
