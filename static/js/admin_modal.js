
(function () {
    var modalEl = null;
    var modal = null;
    var aceptado = false;

    // El modal se arma una sola vez y se reutiliza
    function crearModal() {
        if (modalEl) return;

        modalEl = document.createElement('div');
        modalEl.className = 'modal fade';
        modalEl.id = 'modalConfirmar';
        modalEl.tabIndex = -1;
        modalEl.setAttribute('aria-hidden', 'true');
        modalEl.innerHTML =
            '<div class="modal-dialog modal-dialog-centered" style="max-width: 420px;">' +
                '<div class="modal-content border-0 shadow-lg rounded-4 confirmar-modal">' +
                    '<div class="modal-body text-center p-4 p-sm-5">' +
                        '<div class="confirmar-icono mx-auto mb-3"><i class="bi"></i></div>' +
                        '<h5 class="fw-bold mb-2" id="confirmarTitulo"></h5>' +
                        '<p class="text-secondary mb-4" id="confirmarMensaje"></p>' +
                        '<div class="d-flex gap-2">' +
                            '<button type="button" class="btn btn-light flex-fill fw-semibold rounded-3 py-2" data-bs-dismiss="modal">Cancelar</button>' +
                            '<button type="button" class="btn flex-fill fw-semibold rounded-3 py-2" id="confirmarAceptar"></button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';
        document.body.appendChild(modalEl);

        modal = new bootstrap.Modal(modalEl);

        document.getElementById('confirmarAceptar').addEventListener('click', function () {
            aceptado = true;
            modal.hide();
        });
    }

    window.confirmarAccion = function (opciones) {
        crearModal();
        opciones = opciones || {};
        var tipo = opciones.tipo === 'danger' ? 'danger' : 'success';

        // textContent (no innerHTML) para que un título de proyecto con símbolos no rompa nada
        document.getElementById('confirmarTitulo').textContent = opciones.titulo || '¿Confirmar acción?';
        document.getElementById('confirmarMensaje').textContent = opciones.mensaje || '';

        var icono = modalEl.querySelector('.confirmar-icono');
        icono.className = 'confirmar-icono mx-auto mb-3 confirmar-' + tipo;
        icono.querySelector('i').className = 'bi ' + (tipo === 'danger' ? 'bi-x-circle' : 'bi-check2-circle');

        var boton = document.getElementById('confirmarAceptar');
        boton.className = 'btn flex-fill fw-semibold rounded-3 py-2 ' + (tipo === 'danger' ? 'btn-danger' : 'btn-primary');
        boton.textContent = opciones.boton || 'Aceptar';

        aceptado = false;

        return new Promise(function (resolve) {
            // Se resuelve al terminar de cerrarse, sea por aceptar, cancelar, Esc o clic afuera
            modalEl.addEventListener('hidden.bs.modal', function alCerrar() {
                modalEl.removeEventListener('hidden.bs.modal', alCerrar);
                resolve(aceptado);
            });
            modal.show();
        });
    };

    // Formularios con data-confirmar
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.hasAttribute || !form.hasAttribute('data-confirmar')) return;
        if (form.dataset.confirmado === '1') return;

        e.preventDefault();

        window.confirmarAccion({
            titulo: form.dataset.confirmarTitulo,
            mensaje: form.dataset.confirmar,
            tipo: form.dataset.confirmarTipo,
            boton: form.dataset.confirmarBoton
        }).then(function (ok) {
            if (!ok) return;

            var boton = form.querySelector('button');
            if (boton) {
                boton.disabled = true;
                if (form.dataset.confirmarCargando) boton.textContent = form.dataset.confirmarCargando;
            }
            form.dataset.confirmado = '1';
            form.submit();
        });
    });
})();