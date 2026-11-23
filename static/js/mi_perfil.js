document.addEventListener('DOMContentLoaded', () => {
    const editModal = document.getElementById('editModal');
    const deleteModal = document.getElementById('deleteModal');
    const confirmRevisionModalEl = document.getElementById('confirmRevisionModal');
    const editForm = document.getElementById('edit-form');
    const editEstadoSelect = document.getElementById('edit-estado');
    const optPublicado = document.getElementById('opt-estado-publicado');
    const optBorrador = document.getElementById('opt-estado-borrador');
    const avisoBorrador = document.getElementById('edit-borrador-aviso');
    const confirmRevisionBtn = document.getElementById('confirm-revision-btn');
    const cancelRevisionBtn = document.getElementById('cancel-revision-btn');

    let confirmacionAceptada = false;
    let confirmRevisionModal = null;
    if (confirmRevisionModalEl && window.bootstrap && window.bootstrap.Modal) {
        confirmRevisionModal = new window.bootstrap.Modal(confirmRevisionModalEl);
    }

    if (editModal) {
        editModal.addEventListener('show.bs.modal', e => {
            const b = e.relatedTarget;
            if (!b) return;

            if (typeof EDIT_URL !== 'undefined' && editForm) {
                editForm.action = EDIT_URL.replace('/0/', '/' + b.dataset.id + '/');
            }
            document.getElementById('edit-titulo').value = b.dataset.titulo || '';
            document.getElementById('edit-descripcion').value = b.dataset.descripcion || '';
            document.getElementById('edit-categoria').value = b.dataset.categoria || '';

            const inputImg = document.getElementById('edit-imagen');
            const inputDoc = document.getElementById('edit-documento');
            const inputEnlace = document.getElementById('edit-enlace');
            if (inputImg) inputImg.value = '';
            if (inputDoc) inputDoc.value = '';
            if (inputEnlace) inputEnlace.value = b.dataset.enlace || '';

            confirmacionAceptada = false;
            const estadoActual = (b.dataset.estado || '').toLowerCase();

            if (editForm) {
                editForm.dataset.estadoOriginal = estadoActual;
            }

            if (estadoActual === 'borrador') {
                if (optPublicado) {
                    optPublicado.hidden = true;
                    optPublicado.disabled = true;
                }
                if (optBorrador) {
                    optBorrador.hidden = false;
                    optBorrador.disabled = false;
                }
                if (editEstadoSelect) {
                    editEstadoSelect.value = 'borrador';
                }
            } else {
                // Cuando está publicado (u otro estado), permitir cambiar a borrador
                if (optPublicado) {
                    optPublicado.hidden = false;
                    optPublicado.disabled = false;
                }
                if (optBorrador) {
                    optBorrador.hidden = false;
                    optBorrador.disabled = false;
                }
                if (editEstadoSelect) {
                    editEstadoSelect.value = estadoActual === 'publicado' ? 'publicado' : 'borrador';
                }
            }

            if (avisoBorrador) {
                avisoBorrador.classList.toggle('d-none', estadoActual !== 'borrador');
            }
        });
    }

    if (editForm) {
        editForm.addEventListener('submit', e => {
            const estadoOriginal = (editForm.dataset.estadoOriginal || '').toLowerCase();
            if (estadoOriginal === 'borrador' && !confirmacionAceptada) {
                e.preventDefault();
                if (confirmRevisionModal) {
                    confirmRevisionModal.show();
                }
            }
        });
    }

    if (confirmRevisionBtn) {
        confirmRevisionBtn.addEventListener('click', async () => {
            confirmacionAceptada = true;
            if (confirmRevisionModal) {
                confirmRevisionModal.hide();
            }
            if (!editForm) return;

            const formData = new FormData(editForm);
            const resp = await fetch(editForm.action, {
                method: 'POST',
                body: formData
            });
            window.location.href = resp.url || '/perfil';
        });
    }

    if (cancelRevisionBtn && editModal && window.bootstrap && window.bootstrap.Modal) {
        cancelRevisionBtn.addEventListener('click', () => {
            confirmacionAceptada = false;
            const editModalInstance = window.bootstrap.Modal.getOrCreateInstance(editModal);
            editModalInstance.show();
        });
    }

    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', e => {
            const b = e.relatedTarget;
            if (!b) return;
            const form = document.getElementById('delete-form');
            if (typeof DELETE_URL !== 'undefined' && form) {
                form.action = DELETE_URL.replace('/0/', '/' + b.dataset.id + '/');
            }
            document.getElementById('delete-titulo').textContent = b.dataset.titulo || '';
        });
    }

    if (window.location.hash === '#tab-consultas') {
        const triggerEl = document.querySelector('#consultas-tab');
        if (triggerEl && window.bootstrap && window.bootstrap.Tab) {
            const tab = new window.bootstrap.Tab(triggerEl);
            tab.show();
        }
    }

    if (window.location.hash === '#tab-revision') {
        const revisionTriggerEl = document.querySelector('#revision-tab');
        if (revisionTriggerEl && window.bootstrap && window.bootstrap.Tab) {
            const revisionTab = new window.bootstrap.Tab(revisionTriggerEl);
            revisionTab.show();
        }
    }

    if (window.location.hash === '#tab-borradores') {
        const borradorTriggerEl = document.querySelector('[data-bs-target="#tab-borradores"]');
        if (borradorTriggerEl && window.bootstrap && window.bootstrap.Tab) {
            const borradorTab = new window.bootstrap.Tab(borradorTriggerEl);
            borradorTab.show();
        }
    }
});