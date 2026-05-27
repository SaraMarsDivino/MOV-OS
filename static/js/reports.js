// Minimal reports UI helper: collect filters, POST to API and render simple KPI cards + top products
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('reports-filter-form');
    if (!form) return;
    const btn = document.getElementById('generate-report-btn');
    const results = document.getElementById('reports-results');
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrftoken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    function showSpinner() {
        results.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-light" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }

    function fetchAnalytics(filters) {
        showSpinner();
        fetch(window.location.origin + '/reports/api/compute-analytics/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(filters)
        }).then(r => r.json()).then(resp => {
            if (!resp || !resp.success) {
                results.innerHTML = '<div class="alert alert-danger">Error al generar el informe.</div>';
                return;
            }
            renderResults(resp.data);
        }).catch(err => {
            console.error(err);
            results.innerHTML = '<div class="alert alert-danger">Error de red al generar el informe.</div>';
        });
    }

    function renderKpiCard(title, value, sub) {
        return `
        <div class="col-md-3 mb-3">
            <div class="card p-3 text-center">
                <div class="card-body">
                    <h6 class="card-title">${title}</h6>
                    <p class="display-6 mb-1">${value}</p>
                    <small class="text-muted">${sub || ''}</small>
                </div>
            </div>
        </div>`;
    }

    function renderResults(data) {
        // Simple KPI summary
        const ingreso = data.ingreso_total || 0;
        const ganancia = data.ganancia_neta || 0;
        const trans = data.num_transacciones || 0;
        const ticket = data.ticket_promedio || 0;
        const margen = data.margen || 0;

        let html = '<div class="row">';
        html += renderKpiCard('Ingreso total', ingreso, '');
        html += renderKpiCard('Ganancia neta', ganancia, '');
        html += renderKpiCard('Transacciones', trans, '');
        html += renderKpiCard('Ticket promedio', ticket, '');
        html += '</div>';

        // Top products (rentabilidad)
        const rent = data.rentabilidad_productos || [];
        html += '<div class="row mt-3"><div class="col-12"><h5 class="text-white">Top productos (por ganancia)</h5>';
        if (rent.length === 0) {
            html += '<p class="text-muted">No hay datos para este rango.</p>';
        } else {
            html += '<div class="table-responsive"><table class="table table-dark table-striped"><thead><tr><th>Producto</th><th>Cantidad</th><th>Ganancia neta</th></tr></thead><tbody>';
            rent.slice(0, 10).forEach(r => {
                html += `<tr><td>${r.producto}</td><td>${r.cantidad}</td><td>${r.ganancia_neta_total}</td></tr>`;
            });
            html += '</tbody></table></div>';
        }
        html += '</div></div>';

        results.innerHTML = html;
    }

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        const fecha_inicio = document.getElementById('f_fecha_inicio').value;
        const fecha_fin = document.getElementById('f_fecha_fin').value;
        const cajero = document.getElementById('f_cajero').value || 'todos';
        const sucursal = document.getElementById('f_sucursal').value || 'todos';
        if (!fecha_inicio || !fecha_fin) {
            alert('Selecciona rango de fechas antes de generar el informe.');
            return;
        }
        const filters = { fecha_inicio, fecha_fin, cajero, sucursal };
        fetchAnalytics(filters);
    });
});
