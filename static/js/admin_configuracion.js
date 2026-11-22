// Configuración del sistema (panel admin)
// Las confirmaciones (eliminar categoría, guardar permisos) las maneja admin_modal.js con los data-confirmar del formulario.
document.addEventListener('DOMContentLoaded', function () {

    // Los puntos y muestras de color toman su color del atributo data-color
    document.querySelectorAll('[data-color]').forEach(function (el) {
        el.style.backgroundColor = el.dataset.color;
    });

    // Ventana "Nueva categoría"
    var dialogo = document.getElementById('dlgCategoria');
    var btnAbrir = document.getElementById('btnNuevaCategoria');
    var btnCerrar = document.getElementById('btnCerrarCategoria');

    if (dialogo && btnAbrir) {
        btnAbrir.addEventListener('click', function () {
            if (typeof dialogo.showModal === 'function') {
                dialogo.showModal();
            } else {
                dialogo.setAttribute('open', '');
            }
            document.getElementById('catNombre').focus();
        });

        function cerrar() {
            if (typeof dialogo.close === 'function') {
                dialogo.close();
            } else {
                dialogo.removeAttribute('open');
            }
        }
        btnCerrar.addEventListener('click', cerrar);

        // Clic en el fondo oscuro (fuera de la tarjeta) cierra la ventana
        dialogo.addEventListener('click', function (e) {
            if (e.target === dialogo) cerrar();
        });
    }

    // Formatos: no deja guardar si se desmarcan los dos
    var formFormatos = document.getElementById('formFormatos');
    if (formFormatos) {
        var error = document.getElementById('errorFormatos');
        var casillas = formFormatos.querySelectorAll('.cfg-formato');

        casillas.forEach(function (c) {
            c.addEventListener('change', function () {
                error.classList.add('d-none');
            });
        });

        formFormatos.addEventListener('submit', function (e) {
            var alguno = Array.prototype.some.call(casillas, function (c) { return c.checked; });
            if (!alguno) {
                e.preventDefault();
                error.classList.remove('d-none');
            }
        });
    }

    // Los mensajes flash se cierran solos a los 5 segundos
    document.querySelectorAll('.alert').forEach(function (alerta) {
        setTimeout(function () {
            if (window.bootstrap) {
                bootstrap.Alert.getOrCreateInstance(alerta).close();
            } else {
                alerta.style.display = 'none';
            }
        }, 5000);
    });
});