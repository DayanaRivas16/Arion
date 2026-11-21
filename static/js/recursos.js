document.addEventListener('DOMContentLoaded', () => {
    const filterButtons = document.querySelectorAll('.filter-buttons .btn');
    const resourceItems = document.querySelectorAll('.resource-item');
    const searchInput = document.getElementById('resource-search');
    const guiaModal = document.getElementById('guiaPublicarModal');

    let currentCategory = 'todos';

    function filterResources() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

        resourceItems.forEach(item => {
            const category = (item.getAttribute('data-category') || '').toLowerCase();
            const titleEl = item.querySelector('.card-title');
            const descEl = item.querySelector('.card-text');
            const title = titleEl ? titleEl.textContent.toLowerCase() : '';
            const description = descEl ? descEl.textContent.toLowerCase() : '';

            const matchesCategory = (currentCategory === 'todos' || category === currentCategory);
            const matchesSearch = (!query || title.includes(query) || description.includes(query));

            item.style.display = (matchesCategory && matchesSearch) ? '' : 'none';
        });
    }

    if (filterButtons.length > 0) {
        filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                currentCategory = (button.getAttribute('data-filter') || 'todos').toLowerCase();
                filterResources();
            });
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterResources);
    }

    if (guiaModal) {
        guiaModal.addEventListener('shown.bs.modal', () => {
            const irSubirBtn = guiaModal.querySelector('a[href]');
            if (irSubirBtn) {
                irSubirBtn.focus();
            }
        });
    }
});