// Dashboard del panel admin
// (la confirmación de "Aprobar" la maneja admin_modal.js con los data-confirmar del formulario)
document.addEventListener('DOMContentLoaded', function () {

    // Los mensajes flash (aprobado, error, etc.) se cierran solos a los 5 segundos
    document.querySelectorAll('.alert').forEach(function (alerta) {
        setTimeout(function () {
            bootstrap.Alert.getOrCreateInstance(alerta).close();
        }, 5000);
    });
});