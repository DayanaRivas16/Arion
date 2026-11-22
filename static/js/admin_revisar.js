// Ficha de revisión de proyecto
// (la confirmación de "Aprobar" la maneja admin_modal.js con los data-confirmar del formulario)
document.addEventListener('DOMContentLoaded', function () {

    var formRechazar = document.querySelector('.form-rechazar');
    if (!formRechazar) return;

    var motivo = document.getElementById('motivo');
    var contador = document.getElementById('contador');

    motivo.addEventListener('input', function () {
        contador.textContent = motivo.value.length;
        motivo.classList.remove('is-invalid');
    });

    // Rechazar: primero valida el motivo y luego pide confirmación en el modal
    formRechazar.addEventListener('submit', function (e) {
        e.preventDefault();

        if (motivo.value.trim().length < 10) {
            motivo.classList.add('is-invalid');
            motivo.focus();
            return;
        }

        confirmarAccion({
            titulo: '¿Rechazar este proyecto?',
            mensaje: 'El estudiante verá el motivo que escribiste y podrá corregirlo.',
            tipo: 'danger',
            boton: 'Sí, rechazar'
        }).then(function (ok) {
            if (!ok) return;
            formRechazar.querySelector('button').disabled = true;
            formRechazar.submit();
        });
    });
});