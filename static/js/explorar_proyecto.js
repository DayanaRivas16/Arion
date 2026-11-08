const projectsElement = document.getElementById('projects-data');
const projectsWrapper = document.getElementById('projects-wrapper');

if (projectsElement && projectsWrapper) {
    const projects = JSON.parse(projectsElement.textContent || '[]');
    const authenticated = projectsWrapper.dataset.authenticated === 'true';
    const pageSize = 9;

    let activeCategory = 'Todos';
    let viewMode = 'grid';
    let searchQuery = '';
    let selectedAuthor = '';
    let sortBy = 'recientes';
    let visibleCount = pageSize;

    const resultsCount = document.getElementById('results-count');
    const emptyState = document.getElementById('empty-state');
    const moreWrapper = document.getElementById('more-wrapper');

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[character]);
    }

    const sorters = {
        recientes: (a, b) => b.date - a.date,
        vistas: (a, b) => b.views - a.views,
        valorados: (a, b) => (b.rating ?? -1) - (a.rating ?? -1),
        gustados: (a, b) => b.likes - a.likes
    };

    function getFilteredProjects() {
        const query = searchQuery.trim().toLowerCase();
        return projects
            .filter(project =>
                (activeCategory === 'Todos' || project.category === activeCategory) &&
                (project.title.toLowerCase().includes(query) || project.author.toLowerCase().includes(query)) &&
                (selectedAuthor === '' || project.author === selectedAuthor)
            )
            .sort(sorters[sortBy]);
    }

    function imageHtml(project) {
        if (!project.image) {
            return '<div class="w-100 h-100 bg-light d-flex align-items-center justify-content-center text-muted"><i class="bi bi-image fs-1"></i></div>';
        }
        return `<img src="${escapeHtml(project.image)}" class="w-100 h-100 object-cover card-img-anim" alt="Portada de ${escapeHtml(project.title)}">`;
    }

    function metaHtml(project) {
        if (!authenticated) return '';
        const rating = project.rating === null
            ? '<span class="badge bg-primary-subtle text-primary rounded-pill">Nuevo</span>'
            : `<span><i class="bi bi-star-fill text-warning me-1"></i>${project.rating.toFixed(1)}</span>`;
        return `<div class="d-flex align-items-center gap-2 text-muted small project-meta">${rating}<span><i class="bi bi-eye me-1"></i>${project.views}</span><span><i class="bi bi-heart me-1"></i>${project.likes}</span></div>`;
    }

    function authorHtml(project, size) {
        return `<div class="d-flex align-items-center gap-2 min-w-0"><div class="rounded-circle bg-primary text-white fw-bold d-flex align-items-center justify-content-center flex-shrink-0 project-author-avatar" data-size="${size}">${escapeHtml(project.avatar)}</div><span class="text-muted small text-truncate">${escapeHtml(project.author)}</span></div>`;
    }

    function descriptionHtml(project) {
        const description = project.description || 'Sin descripción disponible.';
        return `<p class="project-description text-muted small mt-3 mb-0">${escapeHtml(description)}</p>${authenticated ? '' : '<p class="small text-primary mt-2 mb-0">Inicia sesión para ver más información.</p>'}`;
    }

    function cardGrid(project) {
        return `<div class="col"><div class="card h-100 border-0 rounded-4 shadow-sm overflow-hidden custom-project-card"><div class="project-grid-image position-relative overflow-hidden">${imageHtml(project)}${project.featured ? '<span class="position-absolute top-0 start-0 m-3 badge bg-warning text-dark rounded-pill fw-bold">⭐ Destacado</span>' : ''}</div><div class="card-body p-4 flex-grow-1 d-flex flex-column justify-content-between"><div><h5 class="card-title fw-bold text-dark mb-1 card-title-hover"><a href="/proyecto/${project.id}" class="stretched-link text-decoration-none text-reset">${escapeHtml(project.title)}</a></h5><span class="badge bg-secondary-subtle text-secondary rounded-2 px-2 py-1 text-xs">${escapeHtml(project.category)}</span>${descriptionHtml(project)}</div><div class="d-flex align-items-center justify-content-between gap-2 mt-4 pt-3 border-t">${authorHtml(project, 26)}${metaHtml(project)}</div></div></div></div>`;
    }

    function cardList(project) {
        return `<div class="card border-0 rounded-4 shadow-sm overflow-hidden custom-project-card w-100"><div class="d-flex flex-column flex-sm-row"><div class="position-relative overflow-hidden flex-shrink-0 list-thumb">${imageHtml(project)}${project.featured ? '<span class="position-absolute top-0 start-0 m-2 badge bg-warning text-dark rounded-pill fw-bold featured-small">⭐</span>' : ''}</div><div class="p-4 flex-grow-1 d-flex flex-column justify-content-between min-w-0"><div><h5 class="card-title fw-bold text-dark mb-1 card-title-hover"><a href="/proyecto/${project.id}" class="stretched-link text-decoration-none text-reset">${escapeHtml(project.title)}</a></h5><span class="badge bg-secondary-subtle text-secondary rounded-2 px-2 py-1 text-xs">${escapeHtml(project.category)}</span>${descriptionHtml(project)}</div><div class="d-flex align-items-center justify-content-between gap-2 mt-3 pt-2 border-t">${authorHtml(project, 24)}${metaHtml(project)}</div></div></div></div>`;
    }

    function renderProjects() {
        const filtered = getFilteredProjects();
        const shown = filtered.slice(0, visibleCount);

        resultsCount.textContent = `${filtered.length} ${filtered.length === 1 ? 'proyecto encontrado' : 'proyectos encontrados'}`;
        projectsWrapper.className = viewMode === 'grid'
            ? 'row g-4 row-cols-1 row-cols-sm-2 row-cols-lg-3'
            : 'd-flex flex-column gap-3';
        projectsWrapper.innerHTML = shown.map(viewMode === 'grid' ? cardGrid : cardList).join('');

        document.querySelectorAll('.project-author-avatar').forEach(avatar => {
            const size = avatar.dataset.size;
            avatar.style.width = `${size}px`;
            avatar.style.height = `${size}px`;
            avatar.style.fontSize = '10px';
        });

        const empty = filtered.length === 0;
        emptyState.classList.toggle('d-none', !empty);
        if (empty) {
            const noProjects = projects.length === 0;
            document.getElementById('empty-title').textContent = noProjects ? 'Aún no hay proyectos publicados' : 'No encontramos proyectos';
            document.getElementById('empty-text').textContent = noProjects
                ? 'Sé la primera persona en compartir uno.'
                : 'Prueba con otra búsqueda o cambia la categoría.';
            document.getElementById('empty-cta').classList.toggle('d-none', !noProjects);
        }
        moreWrapper.classList.toggle('d-none', filtered.length <= visibleCount);
    }

    function resetAndRender() {
        visibleCount = pageSize;
        renderProjects();
    }

    document.getElementById('search-input').addEventListener('input', event => {
        searchQuery = event.target.value;
        resetAndRender();
    });
    document.getElementById('author-select').addEventListener('change', event => {
        selectedAuthor = event.target.value;
        resetAndRender();
    });
    document.getElementById('sort-select').addEventListener('change', event => {
        sortBy = event.target.value;
        resetAndRender();
    });
    document.querySelectorAll('.btn-cat').forEach(button => {
        button.addEventListener('click', event => {
            document.querySelectorAll('.btn-cat').forEach(item => {
                item.className = 'btn btn-light text-muted border-0 rounded-pill px-4 btn-cat';
            });
            event.currentTarget.className = 'btn btn-primary rounded-pill px-4 btn-cat active';
            activeCategory = event.currentTarget.dataset.category;
            resetAndRender();
        });
    });
    document.getElementById('btn-grid').addEventListener('click', () => {
        viewMode = 'grid';
        document.getElementById('btn-grid').className = 'btn btn-sm rounded-3 active-view px-3';
        document.getElementById('btn-list').className = 'btn btn-sm text-muted rounded-3 px-3';
        renderProjects();
    });
    document.getElementById('btn-list').addEventListener('click', () => {
        viewMode = 'list';
        document.getElementById('btn-list').className = 'btn btn-sm rounded-3 active-view px-3';
        document.getElementById('btn-grid').className = 'btn btn-sm text-muted rounded-3 px-3';
        renderProjects();
    });
    document.getElementById('btn-more').addEventListener('click', () => {
        visibleCount += pageSize;
        renderProjects();
    });

    renderProjects();
}