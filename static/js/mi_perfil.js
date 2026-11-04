document.addEventListener('DOMContentLoaded', () => {
    const editModal = document.getElementById('editModal');
    const deleteModal = document.getElementById('deleteModal');

    if (editModal) {
        editModal.addEventListener('show.bs.modal', e => {
            const b = e.relatedTarget;
            const form = document.getElementById('edit-form');
            if (typeof EDIT_URL !== 'undefined') {
                form.action = EDIT_URL.replace('/0/', '/' + b.dataset.id + '/');
            }
            document.getElementById('edit-titulo').value = b.dataset.titulo || '';
            document.getElementById('edit-descripcion').value = b.dataset.descripcion || '';
            document.getElementById('edit-categoria').value = b.dataset.categoria || '';
        });
    }

    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', e => {
            const b = e.relatedTarget;
            const form = document.getElementById('delete-form');
            if (typeof DELETE_URL !== 'undefined') {
                form.action = DELETE_URL.replace('/0/', '/' + b.dataset.id + '/');
            }
            document.getElementById('delete-titulo').textContent = b.dataset.titulo || '';
        });
    }
});