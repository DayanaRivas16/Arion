document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('imgModal');
    if (modalEl) {
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
    }

    const integranteModalEl = document.getElementById('integranteModal');
    if (integranteModalEl) {
        const integranteModal = bootstrap.Modal.getOrCreateInstance(integranteModalEl);
        const modalImg = document.getElementById('integranteModalImg');
        const modalName = document.getElementById('integranteModalName');
        const modalRole = document.getElementById('integranteModalRole');
        const modalProgram = document.getElementById('integranteModalProgram');

        const openIntegranteModal = (item) => {
            modalImg.src = item.dataset.img || '';
            modalImg.alt = item.dataset.name || '';
            modalName.textContent = item.dataset.name || '';
            modalRole.textContent = item.dataset.role || '';
            modalProgram.textContent = item.dataset.program || '';
            integranteModal.show();
        };

        document.querySelectorAll('.photo-item').forEach(item => {
            item.addEventListener('click', () => openIntegranteModal(item));
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openIntegranteModal(item);
                }
            });
        });

        integranteModalEl.addEventListener('hidden.bs.modal', () => {
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');
            modalImg.src = '';
        });
    }
});