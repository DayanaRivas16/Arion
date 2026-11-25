// Historial de revisiones: modal + línea de tiempo

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('modalRevision');
    if (!modal) return;

    const form = document.getElementById('formRevision');
    const titulo = document.getElementById('revProyectoTitulo');
    const linea = document.getElementById('revLinea');
    const vacio = document.getElementById('revVacio');
    const error = document.getElementById('revError');
    const comentario = document.getElementById('revComentario');
    const ayuda = document.getElementById('revAyuda');

    // 1.ª, 2.ª, 3.ª... para contar las observaciones
    const ordinal = n => `${n}.ª`;

    function formatearFecha(iso) {
        return new Date(iso).toLocaleString('es-CO', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    function crear(tag, clase, texto) {
        const el = document.createElement(tag);
        if (clase) el.className = clase;
        if (texto !== undefined) el.textContent = texto;   // textContent: los comentarios los escribe la gente
        return el;
    }

    function dibujar(revisiones) {
        linea.replaceChildren();
        vacio.hidden = revisiones.length > 0;

        let observaciones = 0;

        revisiones.forEach(r => {
            let etiqueta = r.accion;
            if (r.accion === 'Observado') {
                observaciones += 1;
                etiqueta = `${ordinal(observaciones)} observación`;
            }

            const item = crear('li', `rev-item rev-item--${r.accion.toLowerCase()}`);

            const cabecera = crear('div', 'rev-item__titulo');
            cabecera.append(crear('span', null, etiqueta));
            item.append(cabecera);

            const meta = crear('div', 'rev-item__meta');
            meta.append(`${r.revisor || 'Usuario eliminado'} · `);
            if (r.rol) {
                meta.append(crear('span', `rev-rol rev-rol--${r.rol.toLowerCase()}`, r.rol));
                meta.append(' · ');
            }
            meta.append(formatearFecha(r.fecha));
            item.append(meta);

            if (r.comentario) {
                item.append(crear('p', 'rev-item__texto', r.comentario));
            }

            linea.append(item);
        });
    }

    // Al abrir el modal, tomo los datos del botón que lo disparó
    modal.addEventListener('show.bs.modal', async evento => {
        const boton = evento.relatedTarget;
        if (!boton) return;

        titulo.textContent = boton.dataset.titulo || '';
        form.action = boton.dataset.urlRevisar;
        form.reset();
        ayuda.textContent = 'Al aprobar, el comentario es opcional.';
        comentario.required = false;

        linea.replaceChildren();
        vacio.hidden = true;
        error.hidden = true;

        try {
            const resp = await fetch(boton.dataset.urlHistorial);
            if (!resp.ok) throw new Error(resp.status);
            dibujar(await resp.json());
        } catch (e) {
            error.hidden = false;
        }
    });

    // Observar o rechazar obliga a escribir el motivo
    form.addEventListener('change', e => {
        if (e.target.name !== 'accion') return;
        const exige = e.target.value !== 'Aprobado';
        comentario.required = exige;
        ayuda.textContent = exige
            ? 'Este comentario es obligatorio: el estudiante lo verá.'
            : 'Al aprobar, el comentario es opcional.';
    });
});