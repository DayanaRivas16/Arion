// Gestión de proyectos (panel admin)
// Las confirmaciones (aprobar, destacar, eliminar) las maneja admin_modal.js con los data-confirmar de cada formulario.
document.addEventListener('DOMContentLoaded', function () {

    // Buscador: Esc limpia el texto y recarga sin búsqueda
    var buscador = document.querySelector('.proy-buscar input[name="q"]');
    if (buscador) {
        buscador.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && buscador.value !== '') {
                buscador.value = '';
                buscador.form.submit();
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