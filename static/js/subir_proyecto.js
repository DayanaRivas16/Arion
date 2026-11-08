const STEPS = ["Información básica", "Multimedia", "Detalles", "Publicar"];
const uploadData = JSON.parse(document.getElementById("upload-data").textContent);
const CATEGORIES = uploadData.categorias;
const USERS = uploadData.usuarios;
const ESTADOS = [
        { value: "publicado", icon: "bi-globe2", title: "Público", desc: "Visible para la comunidad" },
        { value: "borrador", icon: "bi-lock", title: "Borrador", desc: "Solo tú lo ves" }
    ];

    // Mismos límites que valida el servidor
    const MAX_IMAGE = 5 * 1024 * 1024;
    const MAX_DOCS_TOTAL = 10 * 1024 * 1024;   // suma de todos los documentos
    const MAX_DOCS = 5;
    const IMAGE_EXT = ["png", "jpg", "jpeg", "webp"];
    const DOC_EXT = ["pdf", "docx"];

    let step = 0;
    let categoria = null;       // id de la categoría
    let estado = "publicado";
    let tags = [];
    let cover = null;
    let coverUrl = null;
    let docs = [];
    let members = [];           // ids de usuarios elegidos

    const form = document.getElementById('projectForm');
    const alertBox = document.getElementById('form-alert');

    /* ---------- Utilidades ---------- */
    function esc(s) {
        return String(s).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    }
    function formatSize(b) { return b < 1048576 ? Math.max(1, Math.round(b / 1024)) + ' KB' : (b / 1048576).toFixed(1) + ' MB'; }
    function ext(name) { return name.includes('.') ? name.split('.').pop().toLowerCase() : ''; }
    function initials(name) { return name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?'; }
    function showAlert(msg) { alertBox.textContent = msg; alertBox.classList.remove('d-none'); }
    function hideAlert() { alertBox.classList.add('d-none'); }
    function setError(id, msg) { const el = document.getElementById(id); el.innerHTML = msg; el.classList.toggle('d-none', !msg); }

    /* ---------- Stepper ---------- */
    function renderStepper() {
        document.getElementById('stepper').innerHTML = STEPS.map((label, i) => {
            const done = i < step, active = i === step;
            const circleCls = done ? 'bg-success text-white' : active ? 'bg-primary text-white shadow-primary' : 'bg-secondary-subtle text-muted';
            const labelCls = active ? 'text-primary' : 'text-muted';
            const line = i < STEPS.length - 1 ? `<div class="step-line ${done ? 'bg-success' : ''}"></div>` : '';
            return `
                <div class="d-flex align-items-start">
                    <button type="button" class="btn p-0 border-0 d-flex flex-column align-items-center gap-1 focus-none" onclick="goTo(${i})">
                        <span class="step-circle rounded-circle d-flex align-items-center justify-content-center fw-bold ${circleCls}">
                            ${done ? '<i class="bi bi-check-lg"></i>' : i + 1}
                        </span>
                        <span class="small fw-medium d-none d-sm-block ${labelCls}">${label}</span>
                    </button>
                    ${line}
                </div>`;
        }).join('');
    }

    function showStep() {
        document.querySelectorAll('.step-pane').forEach(p => {
            const on = Number(p.dataset.step) === step;
            p.classList.toggle('d-none', !on);
            if (on) { p.classList.remove('pane-in'); void p.offsetWidth; p.classList.add('pane-in'); }
        });
        document.getElementById('btn-prev').disabled = step === 0;
        document.getElementById('nav-buttons').classList.toggle('d-none', step === 3);
        if (step === 3) fillSummary();
        renderStepper();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function stepError(n) {
        if (n === 0) {
            if (!form.titulo.value.trim()) return "Escribe el título del proyecto.";
            if (!form.descripcion.value.trim()) return "Escribe la descripción del proyecto.";
            if (categoria === null) return "Elige una categoría.";
            if (!tags.length) return "Agrega al menos una etiqueta.";
        }
        if (n === 1) {
            if (!cover) return "Elige una imagen de portada.";
            
            if (!docs.length) return "Debes adjuntar al menos un documento obligatorio.";
        }
        if (n === 2) {
            if (!form.profesor.value.trim()) return "Escribe el nombre del profesor a cargo.";
            if (!form.grado.value.trim()) return "Escribe el grado.";
        }
        return "";
    }

    window.goTo = function (target) {
        if (target > step) {
            for (let n = step; n < target; n++) {
                const err = stepError(n);
                if (err) { showAlert(err); return; }
            }
        }
        hideAlert();
        step = target;
        showStep();
    };
    document.getElementById('btn-next').addEventListener('click', () => goTo(step + 1));
    document.getElementById('btn-prev').addEventListener('click', () => goTo(step - 1));

    /* ---------- Categorías ---------- */
    function renderCategories() {
        const box = document.getElementById('categories');
        if (!CATEGORIES.length) { box.innerHTML = '<span class="text-muted small">No hay categorías disponibles.</span>'; return; }
        box.innerHTML = CATEGORIES.map(c => `
            <button type="button" class="btn btn-sm rounded-pill px-3 py-1 fw-medium ${c.id === categoria ? 'btn-primary' : 'cat-idle'}"
                    onclick="selectCategoria(${c.id})">${esc(c.nombre)}</button>`).join('');
    }
    window.selectCategoria = function (id) {
        categoria = id;
        document.getElementById('categoria').value = id;
        renderCategories();
    };

    /* ---------- Etiquetas ---------- */
    function renderTags() {
        document.getElementById('tags').innerHTML = tags.map((t, i) => `
            <span class="badge bg-secondary-subtle text-dark px-3 py-2 rounded-pill d-inline-flex align-items-center gap-2 fw-medium" style="font-size:.8rem;">
                ${esc(t)}
                <button type="button" class="btn-close" style="font-size:.55rem;" aria-label="Quitar etiqueta ${esc(t)}" onclick="removeTag(${i})"></button>
            </span>`).join('');
        document.getElementById('etiquetas').value = tags.join(',');
    }
    function addTag() {
        const input = document.getElementById('tag-input');
        const v = input.value.trim().replace(/,/g, '');
        if (v && tags.length < 10 && !tags.some(t => t.toLowerCase() === v.toLowerCase())) { tags.push(v); renderTags(); }
        input.value = "";
    }
    window.removeTag = function (i) { tags.splice(i, 1); renderTags(); };
    document.getElementById('btn-add-tag').addEventListener('click', addTag);
    document.getElementById('tag-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); addTag(); }
    });

    /* ---------- Portada ---------- */
    const coverInput = document.getElementById('imagen_portada');
    const dzCover = document.getElementById('dz-cover');

    function setCover(file) {
        setError('cover-error', '');
        if (!file) return;
        let err = "";
        if (!IMAGE_EXT.includes(ext(file.name))) err = "La portada debe ser una imagen PNG, JPG o WEBP.";
        else if (file.size > MAX_IMAGE) err = `La imagen pesa ${formatSize(file.size)} y el máximo es 5 MB.`;
        if (err) { setError('cover-error', esc(err)); coverInput.value = ""; return; }
        cover = file;
        const dt = new DataTransfer(); dt.items.add(file); coverInput.files = dt.files;
        renderCover();
    }
    function renderCover() {
        if (coverUrl) { URL.revokeObjectURL(coverUrl); coverUrl = null; }
        document.getElementById('cover-empty').classList.toggle('d-none', !!cover);
        document.getElementById('cover-preview').classList.toggle('d-none', !cover);
        if (cover) {
            coverUrl = URL.createObjectURL(cover);
            document.getElementById('cover-img').src = coverUrl;
            document.getElementById('cover-name').textContent = cover.name;
            document.getElementById('cover-size').textContent = formatSize(cover.size);
        }
    }
    dzCover.addEventListener('click', () => { if (!cover) coverInput.click(); });
    dzCover.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === dzCover && !cover) { e.preventDefault(); coverInput.click(); } });
    document.getElementById('btn-remove-cover').addEventListener('click', e => { e.stopPropagation(); cover = null; coverInput.value = ""; renderCover(); });
    coverInput.addEventListener('change', () => setCover(coverInput.files[0]));

    /* ---------- Documentos ---------- */
    const docsInput = document.getElementById('documentos');
    const dzDocs = document.getElementById('dz-docs');

    function syncDocs() {
        const dt = new DataTransfer();
        docs.forEach(f => dt.items.add(f));
        docsInput.files = dt.files;
    }
    function totalDocs() { return docs.reduce((sum, f) => sum + f.size, 0); }

    function addDocs(list) {
        const errors = [];
        Array.from(list).forEach(f => {
            if (!DOC_EXT.includes(ext(f.name))) { errors.push(`"${esc(f.name)}" no es PDF ni DOCX.`); return; }
            if (docs.some(x => x.name === f.name && x.size === f.size)) return;
            if (docs.length >= MAX_DOCS) { errors.push(`Solo puedes subir hasta ${MAX_DOCS} documentos.`); return; }
            if (totalDocs() + f.size > MAX_DOCS_TOTAL) {
                errors.push(`"${esc(f.name)}" no cabe: los documentos pueden sumar máximo 10 MB (llevas ${formatSize(totalDocs())}).`);
                return;
            }
            docs.push(f);
        });
        setError('docs-error', [...new Set(errors)].join('<br>'));
        syncDocs();
        renderDocs();
    }
    function renderDocs() {
        document.getElementById('docs-list').innerHTML = docs.map((f, i) => {
            const pdf = ext(f.name) === 'pdf';
            return `
            <div class="d-flex align-items-center gap-3 border rounded-3 p-2 px-3 bg-white">
                <i class="bi ${pdf ? 'bi-file-earmark-pdf text-danger' : 'bi-file-earmark-word text-primary'} fs-3"></i>
                <div class="flex-grow-1 min-w-0">
                    <div class="small fw-medium text-dark text-truncate">${esc(f.name)}</div>
                    <div class="text-muted" style="font-size:.72rem;">${formatSize(f.size)}</div>
                </div>
                <button type="button" class="btn-close" aria-label="Quitar archivo" onclick="removeDoc(${i})"></button>
            </div>`;
        }).join('');
        const totalEl = document.getElementById('docs-total');
        totalEl.classList.toggle('d-none', !docs.length);
        totalEl.textContent = `Total: ${formatSize(totalDocs())} de 10 MB`;
    }
    window.removeDoc = function (i) { docs.splice(i, 1); setError('docs-error', ''); syncDocs(); renderDocs(); };
    dzDocs.addEventListener('click', () => docsInput.click());
    dzDocs.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); docsInput.click(); } });
    docsInput.addEventListener('change', () => addDocs(docsInput.files));
    ['dragenter', 'dragover'].forEach(ev => {
        dzCover.addEventListener(ev, e => { e.preventDefault(); dzCover.classList.add('drag-over'); });
        dzDocs.addEventListener(ev, e => { e.preventDefault(); dzDocs.classList.add('drag-over'); });
    });
    ['dragleave', 'drop'].forEach(ev => {
        dzCover.addEventListener(ev, e => { e.preventDefault(); dzCover.classList.remove('drag-over'); });
        dzDocs.addEventListener(ev, e => { e.preventDefault(); dzDocs.classList.remove('drag-over'); });
    });
    dzCover.addEventListener('drop', e => setCover(e.dataTransfer.files[0]));
    dzDocs.addEventListener('drop', e => addDocs(e.dataTransfer.files));

    /* ---------- Integrantes (usuarios registrados) ---------- */
    const searchInput = document.getElementById('member-search');
    const results = document.getElementById('member-results');

    function avatarHtml(u, cls) {
        return u.foto
            ? `<img src="${esc(u.foto)}" alt="" referrerpolicy="no-referrer" class="${cls} rounded-circle object-cover">`
            : `<span class="${cls} rounded-circle text-white fw-bold d-inline-flex align-items-center justify-content-center avatar-bg">${esc(initials(u.nombre))}</span>`;
    }

    function renderResults() {
        const q = searchInput.value.trim().toLowerCase();
        const list = USERS.filter(u => !members.includes(u.id) && u.nombre.toLowerCase().includes(q)).slice(0, 8);
        if (!USERS.length) {
            results.innerHTML = '<div class="p-3 small text-muted">Aún no hay otros usuarios registrados.</div>';
        } else if (!list.length) {
            results.innerHTML = '<div class="p-3 small text-muted">No encontramos a nadie con ese nombre.</div>';
        } else {
            results.innerHTML = list.map(u => `
                <button type="button" class="member-option d-flex align-items-center gap-2 w-100 border-0 bg-white text-start px-3 py-2" data-id="${u.id}" role="option">
                    ${avatarHtml(u, 'avatar-xs')}
                    <span class="small text-dark">${esc(u.nombre)}</span>
                </button>`).join('');
        }
        results.classList.remove('d-none');
    }
    function closeResults() { results.classList.add('d-none'); }

    function renderMembers() {
        document.getElementById('members').innerHTML = members.map(id => {
            const u = USERS.find(x => x.id === id);
            return `
            <span class="d-inline-flex align-items-center gap-2 bg-light rounded-pill py-1 pe-3 ps-1 border">
                ${avatarHtml(u, 'avatar-xs')}
                <span class="small fw-medium text-dark">${esc(u.nombre)}</span>
                <button type="button" class="btn-close" style="font-size:.55rem;" aria-label="Quitar a ${esc(u.nombre)}" onclick="removeMember(${id})"></button>
            </span>`;
        }).join('');
        document.getElementById('members-hidden').innerHTML = members.map(id => `<input type="hidden" name="integrantes" value="${id}">`).join('');
    }
    window.removeMember = function (id) { members = members.filter(x => x !== id); renderMembers(); };

    searchInput.addEventListener('focus', renderResults);
    searchInput.addEventListener('input', renderResults);
    searchInput.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeResults();
        if (e.key === 'Enter') {
            e.preventDefault();
            const first = results.querySelector('.member-option');
            if (first) first.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        }
    });
    results.addEventListener('mousedown', e => {
        const opt = e.target.closest('.member-option');
        if (!opt) return;
        e.preventDefault();
        members.push(Number(opt.dataset.id));
        searchInput.value = "";
        renderMembers();
        renderResults();
    });
    document.addEventListener('click', e => { if (!e.target.closest('#member-search, #member-results')) closeResults(); });

    /* ---------- Estado de publicación ---------- */
    function renderEstados() {
        document.getElementById('estados').innerHTML = ESTADOS.map(s => `
            <div class="col-6">
                <button type="button" class="estado-card w-100 text-start rounded-4 p-3 ${s.value === estado ? 'selected' : ''}" onclick="selectEstado('${s.value}')">
                    <i class="bi ${s.icon} fs-5 d-block mb-1"></i>
                    <span class="d-block small fw-semibold">${s.title}</span>
                    <span class="d-block text-muted" style="font-size:.72rem;">${s.desc}</span>
                </button>
            </div>`).join('');
        document.getElementById('estado').value = estado;
        document.getElementById('publish-label').textContent = estado === 'publicado' ? 'Publicar proyecto' : 'Guardar borrador';
    }
    window.selectEstado = function (v) { estado = v; renderEstados(); };

    /* ---------- Resumen y envío ---------- */
    function fillSummary() {
        const cat = CATEGORIES.find(c => c.id === categoria);
        const nombres = members.map(id => USERS.find(u => u.id === id).nombre);
        document.getElementById('sum-titulo').textContent = form.titulo.value.trim() || "Sin título";
        document.getElementById('sum-categoria').textContent = cat ? cat.nombre : "Sin categoría";
        document.getElementById('sum-profesor').textContent = form.profesor.value.trim() || "Sin indicar";
        document.getElementById('sum-grado').textContent = form.grado.value.trim() || "Sin indicar";
        document.getElementById('sum-integrantes').textContent = nombres.length ? "Tú, " + nombres.join(", ") : "Solo tú";
        document.getElementById('sum-portada').textContent = cover ? cover.name : "Sin imagen";
        document.getElementById('sum-docs').textContent = docs.length ? docs.length + (docs.length === 1 ? " archivo" : " archivos") : "Ninguno";
        document.getElementById('sum-etiquetas').textContent = tags.length ? tags.join(", ") : "Ninguna";
    }

    form.addEventListener('keydown', e => {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') e.preventDefault();
    });

    form.addEventListener('submit', e => {
        for (let n = 0; n < 3; n++) {
            const err = stepError(n);
            if (err) { e.preventDefault(); step = n; showStep(); showAlert(err); return; }
        }
        const btn = document.getElementById('btn-publish');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Guardando...';
    });

    renderCategories();
    renderTags();
    renderCover();
    renderDocs();
    renderMembers();
    renderEstados();
    showStep();
