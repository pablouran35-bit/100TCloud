(function () {
  const NOMBRE_BD = "100TComprasLocal";
  const VERSION_BD = 1;
  let sincronizacionActiva = false;

  function abrir() {
    return new Promise((resolver, rechazar) => {
      const solicitud = indexedDB.open(NOMBRE_BD, VERSION_BD);

      solicitud.onupgradeneeded = () => {
        const bd = solicitud.result;

        if (!bd.objectStoreNames.contains("pendientes")) {
          const pendientes = bd.createObjectStore(
            "pendientes",
            { keyPath: "id" }
          );

          pendientes.createIndex(
            "por_usuario",
            "usuario_id",
            { unique: false }
          );

          pendientes.createIndex(
            "por_estado",
            "estado",
            { unique: false }
          );
        }

        if (!bd.objectStoreNames.contains("datos_locales")) {
          bd.createObjectStore(
            "datos_locales",
            { keyPath: "clave" }
          );
        }
      };

      solicitud.onsuccess = () => resolver(solicitud.result);

      solicitud.onerror = () =>
        rechazar(
          solicitud.error ||
          new Error(
            "No se pudo abrir el almacenamiento del teléfono."
          )
        );
    });
  }


  async function ejecutar(nombre, modo, accion) {
    const bd = await abrir();

    return new Promise((resolver, rechazar) => {
      const transaccion = bd.transaction(nombre, modo);
      let resultado;

      try {
        resultado = accion(
          transaccion.objectStore(nombre)
        );
      } catch (error) {
        bd.close();
        rechazar(error);
        return;
      }

      transaccion.oncomplete = () => {
        bd.close();
        resolver(resultado?.result);
      };

      transaccion.onerror = transaccion.onabort = () => {
        bd.close();

        rechazar(
          transaccion.error ||
          resultado?.error ||
          new Error(
            "No se pudo guardar el dato en el teléfono."
          )
        );
      };
    });
  }


  function idUnico() {
    if (crypto.randomUUID) {
      return crypto.randomUUID();
    }

    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      (letra) => {
        const numero = Math.floor(Math.random() * 16);

        return (
          letra === "x"
            ? numero
            : (numero & 3) | 8
        ).toString(16);
      }
    );
  }


  function objetoJson(texto) {
    try {
      return texto
        ? JSON.parse(texto)
        : {};
    } catch {
      return {};
    }
  }


  function etiquetaPersona(usuario) {
    return (
      `${usuario.nombre || ""} ${usuario.apellido || ""}`.trim() ||
      usuario.usuario ||
      "Usuario"
    );
  }


  const api = {

    async guardarPendiente(operacion) {
      const existente = await ejecutar(
        "pendientes",
        "readonly",
        (almacen) => almacen.get(operacion.id)
      );

      if (existente) {
        return existente;
      }

      const pendientes = await ejecutar(
        "pendientes",
        "readonly",
        (almacen) => almacen.getAll()
      );

      const orden = Math.max(
        Date.now(),
        ...(pendientes || []).map(
          (fila) => (fila.orden || 0) + 1
        )
      );

      const registro = {
        ...operacion,
        estado: "PENDIENTE",
        orden,
        intentos: 0,
        creado_en: new Date().toISOString(),
      };

      await ejecutar(
        "pendientes",
        "readwrite",
        (almacen) => almacen.put(registro)
      );

      window.dispatchEvent(
        new CustomEvent("100t:cambios-pendientes")
      );

      navigator.serviceWorker?.ready
        .then((trabajador) =>
          trabajador.sync
            ?.register("100t-sincronizar-pendientes")
            .catch(() => {})
        )
        .catch(() => {});

      return registro;
    },


    async listarPendientes(usuarioId) {
      const todos = await ejecutar(
        "pendientes",
        "readonly",
        (almacen) => almacen.getAll()
      );

      return (todos || [])
        .filter(
          (fila) => fila.usuario_id === usuarioId
        )
        .sort(
          (a, b) =>
            (a.orden || 0) - (b.orden || 0)
        );
    },


    async actualizarPendiente(operacion) {
      return ejecutar(
        "pendientes",
        "readwrite",
        (almacen) => almacen.put(operacion)
      );
    },


    async quitarPendiente(id) {
      const resultado = await ejecutar(
        "pendientes",
        "readwrite",
        (almacen) => almacen.delete(id)
      );

      window.dispatchEvent(
        new CustomEvent("100t:cambios-pendientes")
      );

      return resultado;
    },


    async guardarDato(clave, valor, usuarioId) {
      return ejecutar(
        "datos_locales",
        "readwrite",
        (almacen) =>
          almacen.put({
            clave: `${usuarioId}:${clave}`,
            usuario_id: usuarioId,
            actualizado_en: new Date().toISOString(),
            valor,
          })
      );
    },


    async quitarDato(clave, usuarioId) {
      return ejecutar(
        "datos_locales",
        "readwrite",
        (almacen) =>
          almacen.delete(
            `${usuarioId}:${clave}`
          )
      );
    },


    async leerDato(clave, usuarioId) {
      const registro = await ejecutar(
        "datos_locales",
        "readonly",
        (almacen) =>
          almacen.get(
            `${usuarioId}:${clave}`
          )
      );

      return registro?.valor ?? null;
    },


    async listarDatos(prefijo, usuarioId) {
      const todos = await ejecutar(
        "datos_locales",
        "readonly",
        (almacen) => almacen.getAll()
      );

      return (todos || []).filter(
        (fila) =>
          fila.usuario_id === usuarioId &&
          fila.clave.startsWith(
            `${usuarioId}:${prefijo}`
          )
      );
    },


    async contarPendientes(usuarioId) {
      return (
        await this.listarPendientes(usuarioId)
      ).length;
    },


    async solicitarApi(
      url,
      opciones = {},
      token = ""
    ) {
      const metodo = (
        opciones.method || "GET"
      ).toUpperCase();

      const usuario = objetoJson(
        sessionStorage.getItem("usuario")
      );

      let direccion = usuario.id
        ? await resolverUrl(url, usuario.id)
        : url;


      /*
       * ------------------------------------------------------------
       * LECTURAS OFFLINE
       * ------------------------------------------------------------
       */

      if (
        metodo === "GET" &&
        usuario.id
      ) {
        const idLocalSinResolver =
          direccion.match(
            /offline-[0-9a-f-]+/i
          );

        if (idLocalSinResolver) {
          const local =
            await leerRespuestaLocal(
              direccion,
              usuario.id
            );

          if (local.encontrada) {
            return local.valor;
          }
        }

        const hayCambiosPendientes =
          (
            await this.listarPendientes(
              usuario.id
            ).catch(() => [])
          ).length > 0;

        if (
          !navigator.onLine ||
          hayCambiosPendientes
        ) {
          const local =
            await leerRespuestaLocal(
              url,
              usuario.id
            );

          if (local.encontrada) {
            return local.valor;
          }

          const guardado =
            await this.leerDato(
              `respuesta:${url}`,
              usuario.id
            );

          if (guardado !== null) {
            return guardado;
          }
        }
      }


      /*
       * ------------------------------------------------------------
       * OPERACIONES DE ESCRITURA
       * ------------------------------------------------------------
       */

      const claveOperacion =
        metodo === "GET"
          ? null
          : (
              opciones.headers?.[
                "Idempotency-Key"
              ] || idUnico()
            );


      const cabeceras = {
        ...(opciones.headers || {}),
        ...(token
          ? {
              Authorization:
                `Bearer ${token}`
            }
          : {}),
        ...(claveOperacion
          ? {
              "Idempotency-Key":
                claveOperacion
            }
          : {}),
      };


      if (
        opciones.body &&
        !cabeceras["Content-Type"]
      ) {
        cabeceras["Content-Type"] =
          "application/json";
      }


      const operacion =
        metodo === "GET"
          ? null
          : {
              id: claveOperacion,
              operacion_id: claveOperacion,
              usuario_id: usuario.id,
              url,
              method: metodo,
              body: opciones.body || "{}",
              creado_en:
                new Date().toISOString(),
            };


      /*
       * ------------------------------------------------------------
       * MODO OFFLINE REAL
       * ------------------------------------------------------------
       *
       * Si el navegador sabe que no hay Internet,
       * NO intentamos hacer fetch().
       *
       * Esto es importante porque FastAPI puede seguir
       * funcionando localmente en 127.0.0.1:8000 aunque
       * la computadora no tenga Internet.
       *
       * En ese caso fetch() sí llegaría a FastAPI, pero
       * FastAPI intentaría conectarse a Supabase y devolvería
       * HTTP 500.
       *
       * Por eso el cambio offline debe hacerse ANTES del fetch().
       */

      if (
        operacion &&
        usuario.id &&
        !navigator.onLine
      ) {
        if (
          ![
            "POST",
            "PUT",
            "PATCH"
          ].includes(metodo)
        ) {
          throw new Error(
            "Este cambio todavía no se puede guardar sin conexión."
          );
        }

        const resultadoLocal =
          await guardarCambioLocal(
            operacion,
            usuario
          );

        await this.guardarPendiente({
          ...operacion,
          local_output_id:
            resultadoLocal.local_output_id ||
            null,
        });

        window.dispatchEvent(
          new CustomEvent(
            "100t:cambios-pendientes"
          )
        );

        return resultadoLocal.respuesta;
      }


      /*
       * Si ya hay operaciones pendientes,
       * las nuevas escrituras también quedan
       * en cola para mantener el orden.
       */
      if (
        operacion &&
        usuario.id
      ) {
        const yaPendientes =
          await this.listarPendientes(
            usuario.id
          ).catch(() => []);

        if (yaPendientes.length) {
          const resultadoLocal =
            await guardarCambioLocal(
              operacion,
              usuario
            );

          await this.guardarPendiente({
            ...operacion,
            local_output_id:
              resultadoLocal.local_output_id ||
              null,
          });

          window.dispatchEvent(
            new CustomEvent(
              "100t:cambios-pendientes"
            )
          );

          return resultadoLocal.respuesta;
        }
      }


      /*
       * ------------------------------------------------------------
       * INTENTO DE CONEXIÓN
       * ------------------------------------------------------------
       */

      let respuesta;

      try {
        respuesta = await fetch(
          direccion,
          {
            ...opciones,
            headers: cabeceras,
          }
        );

      } catch {
        /*
         * GET sin conexión:
         * buscamos una copia local.
         */
        if (!usuario.id) {
          throw new Error(
            "Iniciá sesión con conexión antes de trabajar sin internet."
          );
        }

        if (metodo === "GET") {
          const local =
            await leerRespuestaLocal(
              url,
              usuario.id
            );

          if (local.encontrada) {
            return local.valor;
          }

          const guardado =
            await this.leerDato(
              `respuesta:${url}`,
              usuario.id
            );

          if (guardado !== null) {
            return guardado;
          }

          throw new Error(
            "No hay una copia local de estos datos. " +
            "Conectate para cargarlos antes de trabajar sin conexión."
          );
        }


        /*
         * Solamente estas operaciones pueden
         * guardarse sin conexión.
         */
        if (
          ![
            "POST",
            "PUT",
            "PATCH"
          ].includes(metodo)
        ) {
          throw new Error(
            "Este cambio todavía no se puede guardar sin conexión."
          );
        }


        const resultadoLocal =
          await guardarCambioLocal(
            operacion,
            usuario
          );

        await this.guardarPendiente({
          ...operacion,
          local_output_id:
            resultadoLocal.local_output_id ||
            null,
        });

        window.dispatchEvent(
          new CustomEvent(
            "100t:cambios-pendientes"
          )
        );

        return resultadoLocal.respuesta;
      }


      /*
       * ------------------------------------------------------------
       * RESPUESTA DE LA API
       * ------------------------------------------------------------
       */

      const texto =
        await respuesta.text();

      let datos = {};

      if (texto) {
        try {
          datos = JSON.parse(texto);
        } catch {
          throw new Error(
            `La API respondió con un error en ${url} ` +
            `(HTTP ${respuesta.status}).`
          );
        }
      }


      if (!respuesta.ok) {
        throw new Error(
          datos.detail ||
          `Error ${respuesta.status}`
        );
      }


      if (
        metodo === "GET" &&
        usuario.id
      ) {
        await this.guardarDato(
          `respuesta:${url}`,
          datos,
          usuario.id
        ).catch(() => {});
      }


      if (
        metodo === "GET" &&
        usuario.id &&
        navigator.onLine
      ) {
        await precalentarDetalles(
          url,
          datos,
          token,
          usuario.id
        ).catch(() => {});
      }


      return datos;
    },


    /*
     * ------------------------------------------------------------
     * SINCRONIZACIÓN
     * ------------------------------------------------------------
     */

    async sincronizarPendientes(token) {
      const usuario = objetoJson(
        sessionStorage.getItem("usuario")
      );

      if (
        !navigator.onLine ||
        !token ||
        !usuario.id ||
        sincronizacionActiva
      ) {
        return;
      }

      sincronizacionActiva = true;

      try {
        const pendientes =
          await this.listarPendientes(
            usuario.id
          );


        for (const operacion of pendientes) {

          /*
           * ERROR o CONFLICTO:
           * no continuamos con operaciones posteriores.
           *
           * Esto mantiene el orden de las operaciones.
           */
          if (
            operacion.estado === "ERROR" ||
            operacion.estado === "CONFLICTO"
          ) {
            break;
          }


          const url =
            await resolverUrl(
              operacion.url,
              usuario.id
            );

          let respuesta;
          let datos = {};


          try {
            respuesta = await fetch(
              url,
              {
                method: operacion.method,
                headers: {
                  Authorization:
                    `Bearer ${token}`,
                  "Content-Type":
                    "application/json",
                  "Idempotency-Key":
                    operacion.operacion_id,
                  "X-Offline-Created-At":
                    operacion.creado_en,
                },
                body: operacion.body,
              }
            );

            const texto =
              await respuesta.text();

            if (texto) {
              try {
                datos = JSON.parse(texto);
              } catch {
                datos = {
                  detail:
                    `La respuesta del servidor no es válida ` +
                    `(HTTP ${respuesta.status}).`
                };
              }
            }

          } catch {
            /*
             * Problema de red:
             * la operación sigue pendiente.
             */
            operacion.intentos =
              (operacion.intentos || 0) + 1;

            await this.actualizarPendiente(
              operacion
            );

            break;
          }


          /*
           * --------------------------------------------------------
           * CONFLICTO REAL
           * --------------------------------------------------------
           *
           * HTTP 409 significa:
           * Cloud encontró un cambio incompatible.
           *
           * NO se elimina la operación.
           * NO se reintenta automáticamente.
           * NO se pisa el dato de Cloud.
           */

          if (respuesta.status === 409) {

            operacion.estado =
              "CONFLICTO";

            operacion.tipo_error =
              datos.detail?.tipo ||
              "CONFLICTO_SINCRONIZACION";

            operacion.error =
              datos.detail ||
              {
                tipo:
                  "CONFLICTO_SINCRONIZACION",
                mensaje:
                  "La operación entra en conflicto " +
                  "con un cambio realizado en Cloud."
              };

            operacion.intentos =
              (operacion.intentos || 0) + 1;

            await this.actualizarPendiente(
              operacion
            );

            window.dispatchEvent(
              new CustomEvent(
                "100t:conflicto-sincronizacion",
                {
                  detail: operacion,
                }
              )
            );

            /*
             * Detenemos la cola.
             * Las operaciones posteriores quedan
             * esperando hasta resolver este conflicto.
             */
            break;
          }


          /*
           * --------------------------------------------------------
           * OTROS ERRORES
           * --------------------------------------------------------
           */

          if (!respuesta.ok) {

            operacion.estado =
              respuesta.status >= 500 ||
              respuesta.status === 401
                ? "PENDIENTE"
                : "ERROR";

            operacion.error =
              datos.detail ||
              `El servidor respondió ${respuesta.status}.`;

            operacion.intentos =
              (operacion.intentos || 0) + 1;

            await this.actualizarPendiente(
              operacion
            );

            window.dispatchEvent(
              new CustomEvent(
                "100t:error-sincronizacion",
                {
                  detail: operacion.error
                }
              )
            );

            /*
             * Conservamos el comportamiento anterior:
             * detenemos la sincronización ante un error.
             */
            break;
          }


          /*
           * --------------------------------------------------------
           * OPERACIÓN CORRECTAMENTE SINCRONIZADA
           * --------------------------------------------------------
           */

          if (
            operacion.local_output_id &&
            datos.id !== undefined
          ) {
            await this.guardarDato(
              `mapa:${operacion.local_output_id}`,
              datos.id,
              usuario.id
            );

            await actualizarIdLocal(
              operacion.local_output_id,
              datos.id,
              usuario.id
            );
          }


          await this.quitarPendiente(
            operacion.id
          );
        }


        /*
         * Si no quedan operaciones pendientes,
         * limpiamos entidades temporales.
         */
        if (
          pendientes.length &&
          !(
            await this.listarPendientes(
              usuario.id
            )
          ).length
        ) {
          await limpiarEntidadesLocales(
            usuario.id
          );

          window.dispatchEvent(
            new CustomEvent(
              "100t:sincronizado"
            )
          );
        }

      } finally {
        sincronizacionActiva = false;

        window.dispatchEvent(
          new CustomEvent(
            "100t:cambios-pendientes"
          )
        );
      }
    },
  };


  function esIdLocal(valor) {
    return (
      typeof valor === "string" &&
      valor.startsWith("offline-")
    );
  }


  async function resolverUrl(
    url,
    usuarioId
  ) {
    let final = url;

    const coincidencias = [
      ...url.matchAll(
        /offline-[0-9a-f-]+/gi
      )
    ].map(
      (m) => m[0]
    );

    for (const localId of coincidencias) {
      const realId =
        await api.leerDato(
          `mapa:${localId}`,
          usuarioId
        );

      if (realId !== null) {
        final = final.replaceAll(
          localId,
          String(realId)
        );
      }
    }

    return final;
  }


  function productoYArea(
    datos,
    articuloId,
    areaId
  ) {
    const articulo =
      (datos?.productos || []).find(
        (fila) =>
          String(fila.id) ===
          String(articuloId)
      );

    const area =
      (datos?.areas || []).find(
        (fila) =>
          String(fila.id) ===
          String(areaId)
      );

    return {
      articulo,
      area
    };
  }


  async function guardarCambioLocal(
    operacion,
    usuario
  ) {
    const cuerpo =
      objetoJson(operacion.body);

    const ahora =
      new Date().toLocaleString("es-AR");

    const nombreUsuario =
      etiquetaPersona(usuario);

    let localOutputId = null;


    /*
     * ============================================================
     * PLANILLAS — CREAR
     * ============================================================
     */

    let coincidencia =
      operacion.url.match(
        /^\/planillas\/?$/
      );

    if (
      operacion.method === "POST" &&
      coincidencia
    ) {
      const inicial =
        await api.leerDato(
          "respuesta:/planillas/inicial",
          usuario.id
        );

      if (!inicial) {
        throw new Error(
          "Para crear una planilla sin conexión, " +
          "primero abrí Planillas con internet para " +
          "guardar obras y artículos en este teléfono."
        );
      }

      const obra =
        inicial.obras.find(
          (fila) =>
            Number(fila.id) ===
            Number(cuerpo.obra_id)
        );

      if (!obra) {
        throw new Error(
          "La obra no está en los datos guardados " +
          "en este teléfono."
        );
      }

      const id =
        `offline-${operacion.id}`;

      operacion.body =
        JSON.stringify({
          ...cuerpo,
          fecha_compra:
            inicial.fecha_compra_nueva
        });

      const entidad = {
        id,
        obra_id: obra.id,
        obra: obra.nombre,
        fecha_compra:
          inicial.fecha_compra_nueva,
        puede_modificar: true,
        solicitudes: [],
        offline: true,
      };

      await api.guardarDato(
        `entidad:planilla:${id}`,
        entidad,
        usuario.id
      );

      localOutputId = id;

      return {
        respuesta: {
          id,
          fecha_compra:
            entidad.fecha_compra,
          creada: true,
          mensaje:
            "Planilla guardada en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
        local_output_id:
          localOutputId,
      };
    }


    /*
     * ============================================================
     * PLANILLAS — AGREGAR SOLICITUD
     * ============================================================
     */

    coincidencia =
      operacion.url.match(
        /^\/planillas\/([^/]+)\/solicitudes\/?$/
      );

    if (
      operacion.method === "POST" &&
      coincidencia
    ) {
      const planillaId =
        coincidencia[1];

      const planilla =
        await obtenerPlanillaLocal(
          planillaId,
          usuario.id
        );

      if (!planilla) {
        throw new Error(
          "No hay una copia local de esta planilla " +
          "para seguir trabajando sin conexión."
        );
      }

      const inicial =
        await api.leerDato(
          "respuesta:/planillas/inicial",
          usuario.id
        );

      const {
        articulo,
        area
      } = productoYArea(
        inicial,
        cuerpo.producto_id,
        cuerpo.area_id
      );

      if (!articulo || !area) {
        throw new Error(
          "El artículo o el área no están en " +
          "el catálogo guardado en este teléfono."
        );
      }

      const id =
        `offline-${operacion.id}`;

      planilla.solicitudes.push({
        id,
        producto_id: articulo.id,
        producto: articulo.nombre,
        cantidad: cuerpo.cantidad,
        area_id: area.id,
        area: area.nombre,
        persona: nombreUsuario,
        estado:
          "PENDIENTE DE COMPRA",
        observaciones:
          cuerpo.observaciones || "",
        tiene_compras: false,
        historial: [
          {
            estado:
              "PENDIENTE DE COMPRA",
            fecha_hora: ahora,
            usuario: nombreUsuario,
            observaciones:
              "Pendiente de sincronización",
          },
        ],
      });

      await api.guardarDato(
        `entidad:planilla:${planillaId}`,
        planilla,
        usuario.id
      );

      localOutputId = id;

      return {
        respuesta: {
          id,
          mensaje:
            "Solicitud guardada en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
        local_output_id: id,
      };
    }


    /*
     * ============================================================
     * PLANILLAS — CAMBIO DE ESTADO OFFLINE
     * ============================================================
     *
     * ESTA es la única modificación de una solicitud
     * que Planillas puede hacer sin conexión.
     *
     * No modifica:
     * - artículo
     * - área
     * - cantidad
     * - observaciones
     *
     * Tampoco cancela.
     */

    coincidencia =
      operacion.url.match(
        /^\/planillas\/([^/]+)\/solicitudes\/([^/]+)\/estado$/
      );

    if (
      operacion.method === "PATCH" &&
      coincidencia
    ) {
      const [
        ,
        planillaId,
        solicitudId
      ] = coincidencia;

      const planilla =
        await obtenerPlanillaLocal(
          planillaId,
          usuario.id
        );

      const solicitud =
        planilla?.solicitudes.find(
          (fila) =>
            String(fila.id) ===
            solicitudId
        );

      if (!solicitud) {
        throw new Error(
          "No hay una copia local de esta solicitud " +
          "para modificar su estado sin conexión."
        );
      }

      const estadoAnterior =
        String(
          cuerpo.estado_anterior ||
          solicitud.estado ||
          "PENDIENTE DE COMPRA"
        ).toUpperCase();

      const estadoNuevo =
        String(
          cuerpo.estado || ""
        ).trim().toUpperCase();

      if (!estadoNuevo) {
        throw new Error(
          "No se recibió un estado para la solicitud."
        );
      }

      /*
       * Guardamos el estado anterior dentro de la operación.
       * Es el dato que Cloud utilizará para detectar conflictos.
       */
      cuerpo.estado_anterior =
        estadoAnterior;

      cuerpo.estado =
        estadoNuevo;

      operacion.body =
        JSON.stringify(cuerpo);

      solicitud.estado =
        estadoNuevo;

      if (!Array.isArray(solicitud.historial)) {
        solicitud.historial = [];
      }

      solicitud.historial.push({
        estado: estadoNuevo,
        fecha_hora: ahora,
        usuario: nombreUsuario,
        observaciones:
          "Pendiente de sincronización",
      });

      /*
       * Los estados finales dejan de aparecer
       * como solicitudes abiertas en Planillas.
       */
      await api.guardarDato(
        `entidad:planilla:${planillaId}`,
        planilla,
        usuario.id
      );

      return {
        respuesta: {
          mensaje:
            "Estado guardado en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
      };
    }


    /*
     * ============================================================
     * PLANILLAS — MODIFICAR / CANCELAR
     * ============================================================
     *
     * IMPORTANTE:
     * Estas operaciones YA NO se permiten offline.
     *
     * Si llegan acá significa que alguna pantalla intentó
     * modificar artículo, área, cantidad, observaciones
     * o cancelar una solicitud sin conexión.
     */

    coincidencia =
      operacion.url.match(
        /^\/planillas\/([^/]+)\/solicitudes\/([^/]+)(?:\/cancelar)?$/
      );

    if (
      ["PUT", "PATCH"].includes(
        operacion.method
      ) &&
      coincidencia
    ) {
      throw new Error(
        "Esta modificación de la solicitud " +
        "requiere conexión. Sin conexión solamente " +
        "se puede cambiar el estado."
      );
    }


    /*
     * ============================================================
     * TAREAS — CREAR
     * ============================================================
     */

    coincidencia =
      operacion.url.match(
        /^\/tareas\/?$/
      );

    if (
      operacion.method === "POST" &&
      coincidencia
    ) {
      const id =
        `offline-${operacion.id}`;

      const tarea = {
        id,
        descripcion:
          cuerpo.descripcion,
        solicitante_id: null,
        solicitante:
          nombreUsuario,
        fecha_solicitud:
          cuerpo.fecha_solicitud,
        estado: "PENDIENTE",
        observaciones:
          cuerpo.observaciones || "",
        historial: [
          {
            estado: "PENDIENTE",
            fecha_hora: ahora,
            usuario: nombreUsuario,
            observaciones:
              cuerpo.observaciones ||
              "Pendiente de sincronización",
          },
        ],
        offline: true,
      };

      await api.guardarDato(
        `entidad:tarea:${id}`,
        tarea,
        usuario.id
      );

      localOutputId = id;

      return {
        respuesta: {
          id,
          mensaje:
            "Tarea guardada en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
        local_output_id:
          localOutputId,
      };
    }


    /*
     * ============================================================
     * TAREAS — MODIFICAR
     * ============================================================
     */

    coincidencia =
      operacion.url.match(
        /^\/tareas\/([^/]+)$/
      );

    if (
      operacion.method === "PUT" &&
      coincidencia
    ) {
      const tareaId =
        coincidencia[1];

      const tarea =
        await obtenerTareaLocal(
          tareaId,
          usuario.id
        );

      if (!tarea) {
        throw new Error(
          "No hay una copia local de esta tarea " +
          "para modificar sin conexión."
        );
      }

      Object.assign(
        tarea,
        cuerpo
      );

      if (!Array.isArray(tarea.historial)) {
        tarea.historial = [];
      }

      tarea.historial.push({
        estado: cuerpo.estado,
        fecha_hora: ahora,
        usuario: nombreUsuario,
        observaciones:
          cuerpo.observaciones ||
          "Pendiente de sincronización",
      });

      await api.guardarDato(
        `entidad:tarea:${tareaId}`,
        tarea,
        usuario.id
      );

      return {
        respuesta: {
          mensaje:
            "Tarea guardada en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
      };
    }


    /*
     * ============================================================
     * COMPRAS — CAMBIO DE ESTADO DE SOLICITUD
     * ============================================================
     *
     * En compras, offline solamente se permitirá cambiar
     * el estado.
     *
     * proveedor y observaciones NO se aceptan offline.
     *
     * El frontend/API de Compras será adaptado al endpoint
     * específico de estado.
     */

    const compraSolicitud =
      operacion.url.match(
        /^\/compras\/planillas\/([^/]+)\/solicitudes\/([^/]+)\/estado$/
      );

    if (
      operacion.method === "PATCH" &&
      compraSolicitud
    ) {
      const [
        ,
        planillaId,
        solicitudId
      ] = compraSolicitud;

      const clave =
        `respuesta:/compras/planillas/${planillaId}`;

      const planilla =
        await api.leerDato(
          clave,
          usuario.id
        );

      const solicitud =
        planilla?.solicitudes.find(
          (fila) =>
            String(fila.id) ===
            solicitudId
        );

      if (!solicitud) {
        throw new Error(
          "No hay una copia local de esta solicitud " +
          "de compra."
        );
      }

      const estadoAnterior =
        String(
          cuerpo.estado_anterior ||
          solicitud.estado ||
          ""
        ).toUpperCase();

      const estadoNuevo =
        String(
          cuerpo.estado || ""
        ).trim().toUpperCase();

      if (!estadoNuevo) {
        throw new Error(
          "No se recibió un estado de compra."
        );
      }

      cuerpo.estado_anterior =
        estadoAnterior;

      cuerpo.estado =
        estadoNuevo;

      operacion.body =
        JSON.stringify(cuerpo);

      solicitud.estado =
        estadoNuevo;

      if (!Array.isArray(solicitud.historial)) {
        solicitud.historial = [];
      }

      solicitud.historial.push({
        estado: estadoNuevo,
        fecha_hora: ahora,
        usuario: nombreUsuario,
        observaciones:
          "Pendiente de sincronización",
      });

      /*
       * En Compras algunos estados hacen que la solicitud
       * deje de aparecer en la lista de compras pendientes.
       */
      if (
        [
          "COMPRADO Y RETIRADO",
          "ENTREGADO",
          "CANCELADA"
        ].includes(estadoNuevo)
      ) {
        planilla.solicitudes =
          planilla.solicitudes.filter(
            (fila) =>
              String(fila.id) !==
              solicitudId
          );
      }

      await api.guardarDato(
        clave,
        planilla,
        usuario.id
      );

      return {
        respuesta: {
          mensaje:
            "Estado de compra guardado en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
      };
    }


    /*
     * ============================================================
     * COMPRAS — MODIFICACIÓN NORMAL
     * ============================================================
     *
     * El PUT anterior permite proveedor + observaciones.
     * Eso NO puede hacerse offline.
     */

    const compraSolicitudOnline =
      operacion.url.match(
        /^\/compras\/planillas\/([^/]+)\/solicitudes\/([^/]+)$/
      );

    if (
      operacion.method === "PUT" &&
      compraSolicitudOnline
    ) {
      throw new Error(
        "Modificar proveedor u observaciones de una compra " +
        "requiere conexión. Sin conexión solamente se puede " +
        "cambiar el estado."
      );
    }


    /*
     * ============================================================
     * COMPRAS — TAREA
     * ============================================================
     */

    const compraTarea =
      operacion.url.match(
        /^\/compras\/tareas\/([^/]+)$/
      );

    if (
      operacion.method === "PUT" &&
      compraTarea
    ) {
      const tareaId =
        compraTarea[1];

      const clave =
        `respuesta:/compras/tareas/${tareaId}`;

      const tarea =
        await api.leerDato(
          clave,
          usuario.id
        );

      if (!tarea) {
        throw new Error(
          "No hay una copia local de esta tarea de compra."
        );
      }

      Object.assign(
        tarea,
        cuerpo
      );

      if (!Array.isArray(tarea.historial)) {
        tarea.historial = [];
      }

      tarea.historial.push({
        estado: cuerpo.estado,
        fecha_hora: ahora,
        usuario: nombreUsuario,
        observaciones:
          cuerpo.observaciones ||
          "Pendiente de sincronización",
      });

      await api.guardarDato(
        clave,
        tarea,
        usuario.id
      );

      return {
        respuesta: {
          mensaje:
            "Cambio de tarea guardado en este teléfono; " +
            "se sincronizará al volver internet.",
          pendiente: true,
        },
      };
    }


    /*
     * ============================================================
     * ENTREGAS
     * ============================================================
     */

    coincidencia =
      operacion.url.match(
        /^\/entregas\/([^/]+)\/solicitudes$/
      );

    if (
      operacion.method === "PATCH" &&
      coincidencia
    ) {
      const planillaId =
        coincidencia[1];

      const clave =
        `respuesta:/entregas/${planillaId}`;

      const planilla =
        await api.leerDato(
          clave,
          usuario.id
        );

      if (!planilla) {
        throw new Error(
          "No hay una copia local de esta planilla " +
          "de entregas."
        );
      }

      for (
        const id
        of cuerpo.solicitud_ids || []
      ) {
        const solicitud =
          planilla.solicitudes.find(
            (fila) =>
              String(fila.id) ===
              String(id)
          );

        if (!solicitud) {
          throw new Error(
            "Una solicitud seleccionada no está " +
            "en la copia local."
          );
        }

        solicitud.estado =
          "ENTREGADO";

        if (!Array.isArray(solicitud.historial)) {
          solicitud.historial = [];
        }

        solicitud.historial.push({
          estado: "ENTREGADO",
          fecha_hora: ahora,
          usuario: nombreUsuario,
          observaciones:
            "Pendiente de sincronización",
        });
      }

      planilla.solicitudes =
        planilla.solicitudes.filter(
          (fila) =>
            !(
              cuerpo.solicitud_ids || []
            ).some(
              (id) =>
                String(id) ===
                String(fila.id)
            )
        );

      await api.guardarDato(
        clave,
        planilla,
        usuario.id
      );

      return {
        respuesta: {
          mensaje:
            "Entrega guardada en este teléfono; " +
            "se sincronizará al volver internet.",
          cantidad:
            (
              cuerpo.solicitud_ids || []
            ).length,
          pendiente: true,
        },
      };
    }


    /*
     * ------------------------------------------------------------
     * Si llegamos acá, esta operación NO está autorizada offline.
     * ------------------------------------------------------------
     */

    throw new Error(
      "Esta operación necesita conexión para guardarse."
    );
  }


  async function obtenerPlanillaLocal(
    id,
    usuarioId
  ) {
    const entidad =
      await api.leerDato(
        `entidad:planilla:${id}`,
        usuarioId
      );

    if (entidad) {
      return entidad;
    }

    return api.leerDato(
      `respuesta:/planillas/${id}`,
      usuarioId
    );
  }


  async function obtenerTareaLocal(
    id,
    usuarioId
  ) {
    const entidad =
      await api.leerDato(
        `entidad:tarea:${id}`,
        usuarioId
      );

    if (entidad) {
      return entidad;
    }

    return api.leerDato(
      `respuesta:/tareas/${id}`,
      usuarioId
    );
  }


  async function leerRespuestaLocal(
    url,
    usuarioId
  ) {
    let coincidencia =
      url.match(
        /^\/planillas\/([^/]+)$/
      );

    if (
      coincidencia &&
      esIdLocal(coincidencia[1])
    ) {
      const valor =
        await obtenerPlanillaLocal(
          coincidencia[1],
          usuarioId
        );

      return {
        encontrada: !!valor,
        valor
      };
    }


    coincidencia =
      url.match(
        /^\/tareas\/([^/]+)$/
      );

    if (
      coincidencia &&
      esIdLocal(coincidencia[1])
    ) {
      const valor =
        await obtenerTareaLocal(
          coincidencia[1],
          usuarioId
        );

      return {
        encontrada: !!valor,
        valor
      };
    }


    if (url === "/planillas") {
      const guardado =
        await api.leerDato(
          `respuesta:${url}`,
          usuarioId
        );

      if (!Array.isArray(guardado)) {
        return {
          encontrada: false,
          valor: null
        };
      }

      const valor =
        structuredClone(guardado);

      for (const planilla of valor) {
        const detalle =
          await api.leerDato(
            `respuesta:/planillas/${planilla.id}`,
            usuarioId
          );

        if (detalle) {
          planilla.pendientes =
            detalle.solicitudes.filter(
              (s) =>
                ![
                  "ENTREGADO",
                  "CANCELADA"
                ].includes(
                  (
                    s.estado || ""
                  ).toUpperCase()
                )
            ).length;
        }
      }

      const locales =
        await api.listarDatos(
          "entidad:planilla:offline-",
          usuarioId
        );

      for (const fila of locales) {
        const p = fila.valor;

        if (
          !valor.some(
            (r) =>
              String(r.id) ===
              String(p.id)
          ) &&
          p.solicitudes.length
        ) {
          valor.unshift({
            id: p.id,
            obra: p.obra,
            fecha_compra:
              p.fecha_compra,
            pendientes:
              p.solicitudes.length,
            solicitantes:
              etiquetaPersona(
                objetoJson(
                  sessionStorage.getItem(
                    "usuario"
                  )
                )
              ),
            offline: true,
          });
        }
      }

      return {
        encontrada:
          Array.isArray(valor),
        valor
      };
    }


    if (url === "/tareas") {
      const guardado =
        await api.leerDato(
          `respuesta:${url}`,
          usuarioId
        );

      if (!Array.isArray(guardado)) {
        return {
          encontrada: false,
          valor: null
        };
      }

      const valor =
        structuredClone(guardado);

      for (const tarea of valor) {
        const detalle =
          await api.leerDato(
            `respuesta:/tareas/${tarea.id}`,
            usuarioId
          );

        if (detalle) {
          Object.assign(
            tarea,
            detalle
          );
        }
      }

      const locales =
        await api.listarDatos(
          "entidad:tarea:offline-",
          usuarioId
        );

      for (const fila of locales) {
        if (
          !valor.some(
            (r) =>
              String(r.id) ===
              String(fila.valor.id)
          )
        ) {
          valor.unshift(
            fila.valor
          );
        }
      }

      return {
        encontrada:
          Array.isArray(valor),
        valor
      };
    }


    const colecciones = [
      {
        ruta: "/compras/planillas",
        detalle: (id) =>
          `/compras/planillas/${id}`,
        campo: "solicitudes",
        cantidad: "solicitudes"
      },
      {
        ruta: "/compras/tareas",
        detalle: (id) =>
          `/compras/tareas/${id}`,
        campo: null
      },
      {
        ruta: "/entregas",
        detalle: (id) =>
          `/entregas/${id}`,
        campo: "solicitudes",
        cantidad: "disponibles"
      },
    ];


    const coleccion =
      colecciones.find(
        (fila) =>
          fila.ruta === url
      );

    if (coleccion) {
      const guardado =
        await api.leerDato(
          `respuesta:${url}`,
          usuarioId
        );

      if (!Array.isArray(guardado)) {
        return {
          encontrada: false,
          valor: null
        };
      }

      const valor =
        structuredClone(guardado);

      for (const fila of valor) {
        const detalle =
          await api.leerDato(
            `respuesta:${coleccion.detalle(fila.id)}`,
            usuarioId
          );

        if (!detalle) {
          continue;
        }

        if (
          coleccion.campo ===
          "solicitudes"
        ) {
          const abiertas =
            detalle.solicitudes.filter(
              (s) => {
                const estado =
                  (
                    s.estado || ""
                  ).toUpperCase();

                return (
                  coleccion.ruta ===
                  "/entregas"
                    ? [
                        "COMPRADO Y RETIRADO",
                        "COMPRADO A ENTREGAR POR PROVEEDOR/FLETE"
                      ].includes(
                        estado
                      )
                    : ![
                        "COMPRADO Y RETIRADO",
                        "ENTREGADO",
                        "CANCELADA"
                      ].includes(
                        estado
                      )
                );
              }
            );

          fila[coleccion.cantidad] =
            abiertas.length;

        } else if (
          coleccion.ruta ===
          "/compras/tareas"
        ) {
          Object.assign(
            fila,
            detalle
          );
        }
      }

      const visibles =
        coleccion.ruta ===
        "/compras/tareas"
          ? valor.filter(
              (fila) =>
                [
                  "PENDIENTE",
                  "EN PROCESO"
                ].includes(
                  (
                    fila.estado || ""
                  ).toUpperCase()
                )
            )
          : valor.filter(
              (fila) =>
                (
                  fila[
                    coleccion.cantidad
                  ] ?? 1
                ) > 0
            );

      return {
        encontrada: true,
        valor: visibles
      };
    }


    return {
      encontrada: false,
      valor: null
    };
  }


  async function precalentarDetalles(
    url,
    filas,
    token,
    usuarioId
  ) {
    const prefijos = {
      "/planillas": (id) =>
        `/planillas/${id}`,

      "/tareas": (id) =>
        `/tareas/${id}`,

      "/compras/planillas": (id) =>
        `/compras/planillas/${id}`,

      "/compras/tareas": (id) =>
        `/compras/tareas/${id}`,

      "/entregas": (id) =>
        `/entregas/${id}`,
    };

    const crearUrl =
      prefijos[url];

    if (
      !crearUrl ||
      !Array.isArray(filas)
    ) {
      return;
    }

    for (
      let inicio = 0;
      inicio < filas.length;
      inicio += 4
    ) {
      await Promise.all(
        filas
          .slice(
            inicio,
            inicio + 4
          )
          .map(
            async (fila) => {
              const direccion =
                crearUrl(fila.id);

              if (
                await api.leerDato(
                  `respuesta:${direccion}`,
                  usuarioId
                )
              ) {
                return;
              }

              try {
                const respuesta =
                  await fetch(
                    direccion,
                    {
                      headers: {
                        Authorization:
                          `Bearer ${token}`
                      }
                    }
                  );

                if (!respuesta.ok) {
                  return;
                }

                const detalle =
                  await respuesta.json();

                await api.guardarDato(
                  `respuesta:${direccion}`,
                  detalle,
                  usuarioId
                );

              } catch {
                /*
                 * La pantalla sigue funcionando
                 * si un detalle no se pudo precargar.
                 */
              }
            }
          )
      );
    }
  }


  async function actualizarIdLocal(
    localId,
    realId,
    usuarioId
  ) {
    const prefijos = [
      "entidad:planilla:",
      "entidad:tarea:"
    ];

    for (const prefijo of prefijos) {
      const fila =
        await api.leerDato(
          `${prefijo}${localId}`,
          usuarioId
        );

      if (!fila) {
        continue;
      }

      fila.id = realId;

      await api.guardarDato(
        `${prefijo}${realId}`,
        fila,
        usuarioId
      );

      break;
    }
  }


  async function limpiarEntidadesLocales(
    usuarioId
  ) {
    const filas =
      await api.listarDatos(
        "entidad:",
        usuarioId
      );

    for (const fila of filas) {
      const clave =
        fila.clave.slice(
          `${usuarioId}:`.length
        );

      if (
        /^entidad:(planilla|tarea):offline-/i.test(
          clave
        )
      ) {
        await api.quitarDato(
          clave,
          usuarioId
        );
      }
    }
  }


  window.offline100t = api;


  window.addEventListener(
    "100t:sincronizar-pendientes",
    () => {
      const token =
        sessionStorage.getItem(
          "token"
        );

      api.sincronizarPendientes(
        token
      ).catch(() => {});
    }
  );


  window.addEventListener(
    "online",
    () => {
      const token =
        sessionStorage.getItem(
          "token"
        );

      api.sincronizarPendientes(
        token
      ).catch(() => {});
    }
  );

})();