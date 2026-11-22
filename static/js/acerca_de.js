document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('imgModal');
    if (!modalEl) return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const modalImg = document.getElementById('imgModalSrc');
    const caption = document.getElementById('imgModalCaption');

    document.querySelectorAll('.zoomable').forEach(img => {
        img.addEventListener('click', () => {
            modalImg.src = img.src;
            modalImg.alt = img.alt;
            caption.textContent = img.alt;
            modal.show();
        });
    });

    // Limpieza por si algo queda pegado al cerrar
    modalEl.addEventListener('hidden.bs.modal', () => {
        document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
        modalImg.src = '';
    });
});