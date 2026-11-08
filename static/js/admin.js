
(() => {
  const toastEl = document.getElementById('toast');  // Busca el elemento HTML donde se mostrará el aviso flotante.
  let toastTimer;  // Guarda el temporizador actual para poder cancelarlo si aparece otro aviso.

  // Muestra un aviso abajo a la derecha.
  // El primer parámetro contiene el texto.
  // El segundo parámetro indica si fue exitoso: true usa el estilo normal y false usa el estilo rojo.
  function toast(msg, ok = true) {
    toastEl.textContent = msg;// Coloca el mensaje recibido dentro del aviso.
    toastEl.className = 'toast show' + (ok ? '' : ' err');// Agrega las clases para hacerlo visible y, en caso de error, aplicar el estilo rojo.

    clearTimeout(toastTimer);// Cancela cualquier temporizador anterior para que solo el aviso más reciente controle el cierre.

    // Después de tres segundos oculta el aviso quitándole la clase que lo mantiene visible.
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), 3000);
  }

  // Realiza una petición HTTP hacia una ruta del servidor.
  // url es la dirección; method es el tipo de petición; body contiene los datos opcionales que se enviarán.
  async function api(url, method = 'POST', body) {
    // fetch inicia la comunicación con Flask sin recargar la página.
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined
    });

    // data guardará la respuesta JSON. Se inicia como objeto vacío por si la respuesta no contiene JSON.
    let data = {};

    // Intenta convertir la respuesta en JSON. Si falla, continúa con el objeto vacío.
    try { data = await res.json(); } catch (_) {}

    // Si la respuesta HTTP fue incorrecta o Flask indicó ok:false, se crea un error con el mensaje recibido.
    if (!res.ok || data.ok === false) throw new Error(data.msg || 'Ocurrió un error en el servidor.');

    // Devuelve los datos para que la parte que llamó a api pueda utilizarlos.
    return data;
  }

  // Espera 700 milisegundos para permitir que el usuario vea el aviso antes de recargar la página.
  const reloadSoon = () => setTimeout(() => location.reload(), 700);

  // Escucha los clics de toda la página para detectar botones que tengan el atributo data-api.
  document.addEventListener('click', async (e) => {
    // Busca el botón más cercano al elemento que recibió el clic y que tenga data-api.
    const btn = e.target.closest('[data-api]');

    // Si el elemento no era un botón de acción, termina esta función sin hacer nada.
    if (!btn) return;

    // Si el botón tiene una confirmación configurada, abre el diálogo antes de continuar.
    if (btn.dataset.confirm) {
        const aceptado = await confirmarAccion(btn.dataset.confirm);

        // Si el usuario cancela, no se envía ninguna petición al servidor.
        if (!aceptado) return;
    }

    // Deshabilita el botón para impedir que el usuario haga doble clic mientras se espera la respuesta.
    btn.disabled = true;

    try {
      // Envía la petición usando la dirección de data-api y el método definido, POST de forma predeterminada.
      const data = await api(btn.dataset.api, btn.dataset.method || 'POST');

      // Muestra el mensaje enviado por Flask o un mensaje de confirmación general.
      toast(data.msg || 'Listo');

      // Recarga la página después de un momento para mostrar los cambios guardados en la base de datos.
      reloadSoon();
    } catch (err) {
      // Si ocurre un problema, muestra el mensaje de error y vuelve a habilitar el botón.
      toast(err.message, false);
      btn.disabled = false;
    }
  });

  // Escucha el envío de formularios configurados con data-form-api.
  document.addEventListener('submit', async (e) => {
    // Encuentra el formulario más cercano que tenga una dirección de API configurada.
    const form = e.target.closest('[data-form-api]');

    // Si el formulario enviado no tiene data-form-api, no realiza ninguna acción.
    if (!form) return;

    // Evita que el navegador recargue o envíe el formulario de forma tradicional.
    e.preventDefault();

    // Crea un objeto vacío que representará todos los datos que se enviarán al servidor.
    const datos = {};

    // Recorre todos los controles del formulario, como inputs, selects y textareas.
    [...form.elements].forEach((el) => {
      // Omite controles sin nombre y controles deshabilitados.
      if (!el.name || el.disabled) return;

      // Guarda los checkbox como true o false.
      // Los demás controles guardan su valor escrito o seleccionado.
      datos[el.name] = el.type === 'checkbox' ? el.checked : el.value;
    });

    // Busca el botón principal de envío, excluyendo botones que sean solo para cancelar o abrir acciones.
    const boton = form.querySelector('button:not([type=button])');

    // Evita que el usuario envíe varias veces mientras espera la respuesta.
    if (boton) boton.disabled = true;

    try {
      // Envía los datos al servidor mediante la URL y el método configurados en el formulario.
      const data = await api(form.dataset.formApi, form.dataset.method || 'POST', datos);

      // Muestra el mensaje de éxito recibido desde Flask.
      toast(data.msg || 'Guardado');

      // Recarga la página si el formulario tiene data-reload="1".
      if (form.dataset.reload) reloadSoon();

      // Si no debe recargar, vuelve a habilitar el botón para permitir otro guardado.
      else if (boton) boton.disabled = false;
    } catch (err) {
      // Muestra el error y reactiva el botón de envío.
      toast(err.message, false);
      if (boton) boton.disabled = false;
    }
  });

  // Controla las ventanas modales abiertas o cerradas mediante atributos HTML.
  document.addEventListener('click', (e) => {
    // Busca si el elemento pulsado tiene el atributo data-open-dialog.
    const abrir = e.target.closest('[data-open-dialog]');

    // Abre el diálogo cuyo id coincide con el valor indicado en data-open-dialog.
    if (abrir) document.getElementById(abrir.dataset.openDialog).showModal();

    // Si se pulsó un elemento con data-close-dialog, obtiene su diálogo padre y lo cierra.
    if (e.target.closest('[data-close-dialog]')) e.target.closest('dialog').close();
  });

  // Detecta los botones usados para editar información de un usuario.
  document.addEventListener('click', (e) => {
    // Busca el botón más cercano que tenga el atributo data-edit-user.
    const btn = e.target.closest('[data-edit-user]');

    // Si el clic no fue sobre ese tipo de botón, termina el manejo del evento.
    if (!btn) return;

    // Obtiene el formulario de edición existente en la página.
    const form = document.getElementById('edit-user-form');

    // Construye la dirección API usando el identificador guardado en el botón.
    form.dataset.formApi = `/admin/api/usuarios/${btn.dataset.id}`;

    // Copia los datos guardados en el botón hacia los campos visibles del formulario.
    form.elements.nombre.value = btn.dataset.nombre;
    form.elements.rol.value = btn.dataset.rol;

    // Deja el campo grado vacío si la tabla muestra "N/A", ya que ese texto solo es informativo.
    form.elements.grado.value = btn.dataset.grado === 'N/A' ? '' : btn.dataset.grado;

    // Abre el diálogo que contiene el formulario de edición.
    document.getElementById('dlg-user').showModal();
  });

  // Detecta cambios en los filtros de rol, grado u otros select configurados con data-autosubmit.
  document.querySelectorAll('form[data-autosubmit] select').forEach((s) =>
    // Envía automáticamente el formulario cuando el usuario cambia una opción del select.
    s.addEventListener('change', () => s.form.submit()));

  // Abre una ventana personalizada para pedir confirmación antes de ejecutar una acción.
  function confirmarAccion(mensaje) {
    // Devuelve una promesa: al terminar, se resolverá con true si aceptó o false si canceló.
    return new Promise((resolve) => {
        // Obtiene los elementos principales del diálogo de confirmación.
        const dialog = document.getElementById('dlg-confirm');
        const texto = document.getElementById('confirm-message');
        const aceptar = document.getElementById('confirm-accept');
        const cancelar = document.getElementById('confirm-cancel');

        // Coloca el texto de la acción que se recibió desde el botón pulsado.
        texto.textContent = mensaje;

        // Determina si la acción es bloquear a un usuario.
        const esBloqueo = mensaje.toLowerCase().includes('bloquear');

        // Cambia el título según si se va a bloquear un usuario o ejecutar otra acción.
        document.getElementById('confirm-title').textContent =
            esBloqueo ? '¿Bloquear usuario?' : '¿Confirmar acción?';

        // Cambia el texto del botón principal según el tipo de acción.
        aceptar.textContent =
            esBloqueo ? 'Sí, bloquear' : 'Sí, continuar';

        // Cierra el diálogo, elimina los eventos temporales y entrega el resultado al botón que llamó a la función.
        function cerrar(resultado) {
            dialog.close();

            // Elimina el clic del botón aceptar para evitar que el evento se conserve en futuras confirmaciones.
            aceptar.removeEventListener('click', confirmar);

            // Elimina el clic del botón cancelar.
            cancelar.removeEventListener('click', rechazar);

            // Elimina la respuesta especial utilizada cuando el usuario presiona Escape.
            dialog.removeEventListener('cancel', cancelarConEsc);

            // Informa si la acción fue aceptada o rechazada.
            resolve(resultado);
        }

        // Si el usuario pulsa el botón de aceptación, resuelve la promesa como verdadera.
        function confirmar() {
            cerrar(true);
        }

        // Si el usuario pulsa cancelar, resuelve la promesa como falsa.
        function rechazar() {
            cerrar(false);
        }

        // Si el usuario presiona Escape, evita que el navegador cierre el diálogo automáticamente y resuelve como cancelado.
        function cancelarConEsc(e) {
            e.preventDefault();
            cerrar(false);
        }

        // Asigna las funciones correspondientes a los botones del diálogo.
        aceptar.addEventListener('click', confirmar);
        cancelar.addEventListener('click', rechazar);

        // Detecta el cierre del diálogo mediante la tecla Escape.
        dialog.addEventListener('cancel', cancelarConEsc);

        // Abre el diálogo de confirmación en modo modal, impidiendo la interacción con el resto de la página.
        dialog.showModal();
    });
  }

})();