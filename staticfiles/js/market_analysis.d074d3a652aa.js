(function(){
  function escapeHtml(s){
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[c]));
  }

  function truncateText(s, maxLen){
    const str = String(s ?? '');
    const n = Number(maxLen || 0);
    if (!n || n < 4) return str;
    if (str.length <= n) return str;
    return str.slice(0, n - 1) + '…';
  }

  function formatCLP(num){
    try {
      const n = Number(num);
      if (Number.isNaN(n)) return String(num ?? '');
      return n.toLocaleString('es-CL', { maximumFractionDigits: 0 });
    } catch { return String(num ?? ''); }
  }

  function formatPct(num, digits=1){
    const n = Number(num);
    if (!Number.isFinite(n)) return 'N/D';
    return `${n.toFixed(digits)}%`;
  }

  function qs(form){
    const fd = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      if (v !== null && String(v).trim() !== '') params.set(k, String(v));
    }
    return params;
  }

  function setStatus(msg, type='muted'){
    const el = document.getElementById('marketStatus');
    if (!el) return;
    el.className = `small ${type}`;
    el.textContent = msg;
  }

  async function fetchJson(url){
    const res = await fetch(url, { credentials: 'same-origin' });
    const ct = res.headers.get('content-type') || '';
    const txt = await res.text();
    let data = null;
    if (ct.includes('application/json')) {
      try { data = JSON.parse(txt); } catch { data = { error: 'JSON inválido' }; }
    } else {
      data = { error: `HTTP ${res.status} - ${txt.substring(0, 200)}...` };
    }
    if (!res.ok) throw new Error((data && data.error) ? data.error : `HTTP ${res.status}`);
    return data;
  }

  function destroyChart(ch){
    try { if (ch) ch.destroy(); } catch(e) {}
  }

  const charts = {
    payment: null,
    topProducts: null,
    byHour: null,
    weekend: null,
    monthly: null,
    branches: null,
    paycycle: null,
    terminals: null,
    topMargin: null,
    pareto: null,
    priceDist: null,
    offers: null,
  };

  let activeParams = null;
  let cachedHeatmap = null;
  let heatmapMode = 'tickets';
  let topProductsMode = 'qty';
  let topProductsPayload = null;
  const loadedTabs = new Set();

  const TOP_PRODUCTS_MODE_STORAGE_KEY = 'marketAnalysis.topProductsMode';
  const TOP_PRODUCTS_LIST_OPEN_STORAGE_KEY = 'marketAnalysis.topProductsListOpen';

  function loadTopProductsModeFromStorage(){
    try {
      const v = localStorage.getItem(TOP_PRODUCTS_MODE_STORAGE_KEY);
      return (v === 'amount' || v === 'qty') ? v : null;
    } catch { return null; }
  }

  function saveTopProductsModeToStorage(mode){
    try {
      localStorage.setItem(TOP_PRODUCTS_MODE_STORAGE_KEY, mode);
    } catch { /* ignore */ }
  }

  function loadTopProductsListOpenFromStorage(){
    try {
      const v = localStorage.getItem(TOP_PRODUCTS_LIST_OPEN_STORAGE_KEY);
      if (v === '1' || v === 'true') return true;
      if (v === '0' || v === 'false') return false;
      return null;
    } catch { return null; }
  }

  function saveTopProductsListOpenToStorage(open){
    try {
      localStorage.setItem(TOP_PRODUCTS_LIST_OPEN_STORAGE_KEY, open ? '1' : '0');
    } catch { /* ignore */ }
  }

  function setCollapseOpenById(collapseId, open){
    const el = document.getElementById(collapseId);
    if (!el) return;
    const btn = document.querySelector(`[data-bs-target="#${collapseId}"]`);
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');

    // Prefer Bootstrap API when available; otherwise fallback to class toggle.
    try {
      const bs = (window.bootstrap && window.bootstrap.Collapse) ? window.bootstrap : null;
      if (bs && bs.Collapse) {
        let inst = null;
        try { inst = bs.Collapse.getInstance(el); } catch { inst = null; }
        if (!inst) inst = new bs.Collapse(el, { toggle: false });
        if (open) inst.show(); else inst.hide();
        return;
      }
    } catch { /* ignore */ }

    if (open) el.classList.add('show');
    else el.classList.remove('show');
  }

  function ensureFiltersApplied(){
    return !!(activeParams && activeParams.get('start_date') && activeParams.get('end_date'));
  }

  function clearVisuals(){
    for (const k of Object.keys(charts)) destroyChart(charts[k]);
    for (const k of Object.keys(charts)) charts[k] = null;

    const hints = ['topProductsHint','salesByHourHint','paymentHint'];
    for (const id of hints) {
      const el = document.getElementById(id);
      if (el) el.textContent = 'Aplica filtros para cargar.';
    }
    const heatmap = document.getElementById('heatmapContainer');
    if (heatmap) heatmap.innerHTML = '<div class="muted">Aplica filtros para cargar.</div>';

    cachedHeatmap = null;
    heatmapMode = 'tickets';

    const notes = document.getElementById('overviewNotes');
    if (notes) notes.textContent = 'Aplica filtros para cargar indicadores.';

    const peak = document.getElementById('peakHourLabel');
    if (peak) peak.textContent = '';

    const paycycleHint = document.getElementById('paycycleHint');
    if (paycycleHint) paycycleHint.textContent = 'Aplica filtros para cargar.';

    const terminalHint = document.getElementById('terminalHint');
    if (terminalHint) terminalHint.textContent = 'Aplica filtros para cargar.';

    const peakDensityValue = document.getElementById('peakDensityValue');
    const peakDensityDetail = document.getElementById('peakDensityDetail');
    if (peakDensityValue) peakDensityValue.textContent = 'N/D';
    if (peakDensityDetail) peakDensityDetail.textContent = 'Aplica filtros para calcular.';

    const projectionValue = document.getElementById('projectionValue');
    const projectionDetail = document.getElementById('projectionDetail');
    if (projectionValue) projectionValue.textContent = '$0';
    if (projectionDetail) projectionDetail.textContent = 'Aplica filtros para calcular.';

    const yoyValue = document.getElementById('yoyValue');
    const yoyDetail = document.getElementById('yoyDetail');
    if (yoyValue) yoyValue.textContent = 'N/D';
    if (yoyDetail) yoyDetail.textContent = 'Aplica filtros para calcular.';

    const runwayResult = document.getElementById('runwayResult');
    if (runwayResult) runwayResult.innerHTML = '';

    const elasticityResult = document.getElementById('elasticityResult');
    if (elasticityResult) elasticityResult.innerHTML = '';
    const elasticityStatus = document.getElementById('elasticityStatus');
    if (elasticityStatus) elasticityStatus.textContent = 'Usa meses dentro del rango filtrado.';

    const newSummary = document.getElementById('newProductsSummary');
    const newDetail = document.getElementById('newProductsDetail');
    if (newSummary) newSummary.textContent = 'N/D';
    if (newDetail) newDetail.textContent = 'Aplica filtros para calcular.';
    const winBody = document.getElementById('newWinnersBody');
    const loseBody = document.getElementById('newLosersBody');
    if (winBody) winBody.innerHTML = '<tr><td colspan="2" class="muted">Aplica filtros para cargar.</td></tr>';
    if (loseBody) loseBody.innerHTML = '<tr><td colspan="2" class="muted">Aplica filtros para cargar.</td></tr>';

    const antisocialBody = document.getElementById('antisocialTableBody');
    if (antisocialBody) antisocialBody.innerHTML = '<tr><td colspan="4" class="muted">Aplica filtros para cargar.</td></tr>';

    const attachBody = document.getElementById('attachTableBody');
    if (attachBody) attachBody.innerHTML = '<tr><td colspan="4" class="muted">Aplica filtros y luego ingresa un producto A.</td></tr>';
    const attachStatus = document.getElementById('attachStatus');
    if (attachStatus) attachStatus.textContent = 'Se calcula con las ventas filtradas.';

    const topListBody = document.getElementById('topProductsListBody');
    if (topListBody) topListBody.innerHTML = '<tr><td colspan="3" class="muted">Aplica filtros para cargar.</td></tr>';
    const topHeader = document.getElementById('topProductsValueHeader');
    if (topHeader) topHeader.textContent = (topProductsMode === 'amount') ? 'Monto' : 'Unidades';

    topProductsPayload = null;

    const vHigh = document.getElementById('volatilityHighBody');
    const vLow = document.getElementById('volatilityLowBody');
    if (vHigh) vHigh.innerHTML = '<tr><td colspan="3" class="muted">Aplica filtros para cargar.</td></tr>';
    if (vLow) vLow.innerHTML = '<tr><td colspan="3" class="muted">Aplica filtros para cargar.</td></tr>';

    const zombiesBody = document.getElementById('zombiesTableBody');
    if (zombiesBody) zombiesBody.innerHTML = '<tr><td colspan="2" class="muted">Aplica filtros para cargar.</td></tr>';

    const impulseBody = document.getElementById('impulseTableBody');
    if (impulseBody) impulseBody.innerHTML = '<tr><td colspan="3" class="muted">Aplica filtros para cargar.</td></tr>';

    const periodKpis = document.getElementById('periodKpis');
    if (periodKpis) periodKpis.style.display = 'none';
  }

  function renderKpiGrid(overview){
    const grid = document.getElementById('kpiGrid');
    const empty = document.getElementById('kpiEmptyMsg');
    const periodKpis = document.getElementById('periodKpis');
    if (!grid) return;

    const k = overview.kpis || {};
    const periods = overview.periods || {};
    const tp = overview.top_product || null;
    const tpUnits = overview.top_product_by_units || null;

    const topMoneyName = (tp && tp.nombre) ? String(tp.nombre) : 'N/D';
    const topUnitsName = (tpUnits && tpUnits.nombre) ? String(tpUnits.nombre) : 'N/D';

    grid.innerHTML = `
      <div class="col-12 col-lg-4">
        <div class="kpi-card kpi-card-primary" style="background:#0B84C1; border:none;">
          <h3 style="font-size:1.8rem;">$${formatCLP(k.venta_total_neta ?? 0)}</h3>
          <p style="color:rgba(255,255,255,0.9);">Venta Total Neta (rango)</p>
        </div>
      </div>
      <div class="col-6 col-lg-2"><div class="kpi-card"><h3>$${formatCLP(k.utilidad_bruta_real ?? 0)}</h3><p>Utilidad bruta real</p></div></div>
      <div class="col-6 col-lg-2"><div class="kpi-card"><h3>${formatPct(k.margen_ganancia_promedio_pct ?? 0, 1)}</h3><p>Margen promedio</p></div></div>
      <div class="col-6 col-lg-2"><div class="kpi-card"><h3>$${formatCLP(k.ticket_promedio ?? 0)}</h3><p>Ticket promedio</p></div></div>
      <div class="col-6 col-lg-2"><div class="kpi-card"><h3>${Number(k.articulos_por_ticket ?? 0).toFixed(2)}</h3><p>Artículos por ticket</p></div></div>

      <div class="col-6 col-lg-3"><div class="kpi-card"><h3>${Number(k.sku_breadth_avg ?? 0).toFixed(2)}</h3><p>Diversidad (SKUs/ticket)</p></div></div>
      <div class="col-6 col-lg-3"><div class="kpi-card"><h3>${formatCLP(k.ventas_count ?? 0)}</h3><p>Tickets (cantidad)</p></div></div>
      <div class="col-6 col-lg-3"><div class="kpi-card"><h3>$${formatCLP((tp && tp.total_monto) ? tp.total_monto : 0)}</h3><p>Top producto ($)</p><div class="kpi-sub" title="${escapeHtml(topMoneyName)}">${escapeHtml(truncateText(topMoneyName, 70))}</div></div></div>
      <div class="col-6 col-lg-3"><div class="kpi-card"><h3>${formatCLP((tpUnits && tpUnits.unidades) ? tpUnits.unidades : 0)}</h3><p>Top producto (unid)</p><div class="kpi-sub" title="${escapeHtml(topUnitsName)}">${escapeHtml(truncateText(topUnitsName, 70))}</div></div></div>

      <div class="col-6 col-lg-4"><div class="kpi-card"><h3>$${formatCLP(k.total_descuentos_estimado ?? 0)}</h3><p>Descuentos (estimado)</p></div></div>
      <div class="col-6 col-lg-4"><div class="kpi-card"><h3>$${formatCLP(k.costo_total_estimado ?? 0)}</h3><p>Costo (estimado)</p></div></div>
      <div class="col-6 col-lg-4"><div class="kpi-card"><h3>N/D</h3><p>Devoluciones/anulaciones</p></div></div>
    `;

    if (empty) empty.style.display = 'none';

    if (periodKpis) {
      const d = periods.day?.total_monto ?? 0;
      const w = periods.week?.total_monto ?? 0;
      const m = periods.month?.total_monto ?? 0;
      const kpiDay = document.getElementById('kpiDay');
      const kpiWeek = document.getElementById('kpiWeek');
      const kpiMonth = document.getElementById('kpiMonth');
      if (kpiDay) kpiDay.textContent = `$${formatCLP(d)}`;
      if (kpiWeek) kpiWeek.textContent = `$${formatCLP(w)}`;
      if (kpiMonth) kpiMonth.textContent = `$${formatCLP(m)}`;
      periodKpis.style.display = '';
    }
  }

  function renderTopProductsList(bodyId, items, labelKey, valueKey, isMoney){
    const body = document.getElementById(bodyId);
    if (!body) return;
    const rows = items || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="3" class="muted">Sin datos para el rango.</td></tr>';
      return;
    }

    body.innerHTML = rows.map((r, idx) => {
      const name = String((r && r[labelKey]) ? r[labelKey] : '');
      const val = Number((r && r[valueKey]) ? r[valueKey] : 0);
      const valTxt = isMoney ? `$${formatCLP(val)}` : `${formatCLP(val)}`;
      return `
        <tr>
          <td>${idx + 1}</td>
          <td style="white-space:normal; word-break:break-word;">${escapeHtml(name)}</td>
          <td class="text-end">${escapeHtml(valTxt)}</td>
        </tr>
      `;
    }).join('');
  }

  function renderPaymentMethods(payment){
    const canvas = document.getElementById('paymentMethodChart');
    if (!canvas) return;

    const labelsMap = {
      efectivo: 'Efectivo',
      debito: 'Débito',
      credito: 'Crédito',
      transferencia: 'Transferencia',
    };

    const labels = (payment || []).map(r => labelsMap[r.forma_pago] || (r.forma_pago || 'Otro'));
    const values = (payment || []).map(r => Number(r.total_monto || 0));

    charts.payment = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: [
            'rgba(11,132,193,0.85)',
            'rgba(15,157,88,0.85)',
            'rgba(244,160,0,0.85)',
            'rgba(99,102,241,0.85)',
            'rgba(156,163,175,0.85)',
          ],
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom' },
          tooltip: { callbacks: { label: (ctx) => `${ctx.label}: $${formatCLP(ctx.parsed)}` } },
        }
      }
    });

    const hint = document.getElementById('paymentHint');
    if (hint) hint.textContent = '';
  }

  function renderHeatmap(payload, mode){
    const container = document.getElementById('heatmapContainer');
    if (!container) return;

    const isAmount = (mode === 'amount');
    const matrix = isAmount ? (payload.matrix_amount || []) : (payload.matrix_count || []);
    const labels = payload.weekday_labels || [];

    const peakHour = isAmount ? payload.peak_hour_amount : payload.peak_hour;
    const peakTickets = isAmount ? payload.peak_tickets_amount : payload.peak_tickets;
    const peakAmount = isAmount ? payload.peak_amount_amount : payload.peak_amount;

    const flat = (matrix || []).flat();
    const max = Math.max(...flat.map(v => Number(v) || 0), 0);
    const hours = Array.from({length: 24}, (_, i) => String(i).padStart(2,'0'));

    function cellStyle(v){
      const n = Number(v) || 0;
      if (max <= 0) return 'background:#f8fafc;';
      const t = Math.min(1, n / max);
      const alpha = 0.08 + t * 0.65;
      return `background: rgba(11, 132, 193, ${alpha.toFixed(3)});`;
    }

    const header = `
      <thead>
        <tr>
          <th style="min-width:64px">Día</th>
          ${hours.map(h => `<th class="text-center" style="min-width:36px">${h}</th>`).join('')}
        </tr>
      </thead>
    `;

    const body = `
      <tbody>
        ${(matrix || []).map((row, i) => {
          return `
            <tr>
              <td><strong>${labels[i] || ''}</strong></td>
              ${row.map(v => {
                const n = Number(v) || 0;
                const txt = isAmount ? (n > 0 ? `$${formatCLP(n)}` : '') : (n > 0 ? String(Math.round(n)) : '');
                return `<td class="text-center" style="${cellStyle(n)}">${txt}</td>`;
              }).join('')}
            </tr>
          `;
        }).join('')}
      </tbody>
    `;

    container.innerHTML = `
      <table class="table table-sm align-middle mb-0" style="font-size:0.78rem;">
        ${header}
        ${body}
      </table>
    `;

    const peak = document.getElementById('peakHourLabel');
    if (peak) {
      if (peakHour === null || peakHour === undefined) {
        peak.textContent = '';
      } else {
        const hh = String(peakHour).padStart(2,'0');
        const t = Number(peakTickets || 0);
        const amt = Number(peakAmount || 0);
        if (isAmount) {
          peak.textContent = `Hora de oro ($): ${hh}:00 ($${formatCLP(amt || 0)} | ${t} tickets)`;
        } else {
          peak.textContent = `Hora de oro (tickets): ${hh}:00 (${t} tickets${amt > 0 ? ` | $${formatCLP(amt)}` : ''})`;
        }
      }
    }
  }

  function renderWeekendChart(payload){
    const canvas = document.getElementById('weekendChart');
    if (!canvas) return;

    const weekend = payload.weekend?.total_monto ?? 0;
    const weekday = payload.weekday?.total_monto ?? 0;

    charts.weekend = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Días hábiles', 'Fin de semana'],
        datasets: [{
          data: [weekday, weekend],
          backgroundColor: ['rgba(99,102,241,0.35)', 'rgba(11,132,193,0.35)'],
          borderColor: ['rgba(99,102,241,0.85)', 'rgba(11,132,193,0.85)'],
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderPaycycleChart(payload){
    const canvas = document.getElementById('paycycleChart');
    if (!canvas) return;

    const pay = payload.paydays?.total_monto ?? 0;
    const rest = payload.rest?.total_monto ?? 0;

    charts.paycycle = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Días 1–5 y 15–20', 'Resto'],
        datasets: [{
          data: [pay, rest],
          backgroundColor: ['rgba(11,132,193,0.35)', 'rgba(156,163,175,0.35)'],
          borderColor: ['rgba(11,132,193,0.85)', 'rgba(156,163,175,0.85)'],
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });

    const hint = document.getElementById('paycycleHint');
    if (hint) hint.textContent = '';
  }

  function renderPeakDensity(payload){
    const v = document.getElementById('peakDensityValue');
    const d = document.getElementById('peakDensityDetail');
    if (!v || !d) return;
    if (payload.max_tickets_per_minute === null || payload.max_tickets_per_minute === undefined) {
      v.textContent = 'N/D';
      d.textContent = 'Sin ventas en el rango.';
      return;
    }
    v.textContent = `${payload.max_tickets_per_minute} tickets/min`;
    const hh = (payload.peak_hour === null || payload.peak_hour === undefined) ? 'N/D' : String(payload.peak_hour).padStart(2,'0') + ':00';
    d.textContent = `Hora peak: ${hh}`;
  }

  function renderTerminalChart(payload){
    const canvas = document.getElementById('terminalSalesChart');
    if (!canvas) return;

    const rows = payload.terminals || [];
    const labels = rows.map(r => (r.caja_label || '').slice(0, 18));
    const totals = rows.map(r => Number(r.total_monto || 0));

    charts.terminals = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: totals,
          backgroundColor: 'rgba(99,102,241,0.25)',
          borderColor: 'rgba(99,102,241,0.85)',
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const i = ctx.dataIndex;
                const row = rows[i] || {};
                const extra = ` | Tickets: ${formatCLP(row.tickets || 0)} | Vendedor: ${row.vendedor || 'N/D'}`;
                return `$${formatCLP(ctx.parsed.y)}${extra}`;
              }
            }
          }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });

    const hint = document.getElementById('terminalHint');
    if (hint) hint.textContent = '';
  }

  function renderMonthlyTrend(payload){
    const canvas = document.getElementById('monthlyTrendChart');
    if (!canvas) return;

    const rows = payload.monthly || [];
    const labels = rows.map(r => (r.month || '').slice(0,7));
    const values = rows.map(r => Number(r.total_monto || 0));

    charts.monthly = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: 'rgba(15,157,88,0.95)',
          backgroundColor: 'rgba(15,157,88,0.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 2,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderBranches(payload){
    const canvas = document.getElementById('branchesChart');
    if (!canvas) return;

    const rows = payload.branches || [];
    const labels = rows.map(r => (r.sucursal_nombre || '').slice(0, 24));
    const totals = rows.map(r => Number(r.total_monto || 0));

    charts.branches = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Ventas',
          data: totals,
          backgroundColor: 'rgba(11,132,193,0.25)',
          borderColor: 'rgba(11,132,193,0.75)',
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const i = ctx.dataIndex;
                const row = rows[i] || {};
                const extra = ` | Ticket: $${formatCLP(row.ticket_promedio || 0)} | Items/ticket: ${(row.articulos_por_ticket ?? 0).toFixed(2)}`;
                return `$${formatCLP(ctx.parsed.y)}${extra}`;
              }
            }
          }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderTopProducts(canvasId, items, labelKey, valueKey, title, isMoney=false){
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const labels = (items || []).map(x => String(x[labelKey] || ''));
    const values = (items || []).map(x => Number(x[valueKey] || 0));

    // Make room for long labels (horizontal bars)
    try {
      canvas.height = Math.max(260, Math.min(520, (labels.length || 10) * 34));
    } catch (e) {}

    return new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: title,
          data: values,
          backgroundColor: 'rgba(11,132,193,0.25)',
          borderColor: 'rgba(11,132,193,0.75)',
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const i = items && items[0] ? items[0].dataIndex : -1;
                return (i >= 0 && labels[i]) ? labels[i] : '';
              },
              label: (ctx) => {
                const v = ctx.parsed.x;
                return isMoney ? `$${formatCLP(v)}` : `${formatCLP(v)}`;
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              callback: (v) => isMoney ? `$${formatCLP(v)}` : formatCLP(v)
            },
            grid: { color: 'rgba(15,23,42,0.10)' }
          },
          y: {
            ticks: {
              callback: (v) => truncateText(String(v), 48)
            },
            grid: { display: false }
          }
        }
      }
    });
  }

  function syncTopProductsToggleUI(){
    const qtyBtn = document.getElementById('topProductsModeQtyBtn');
    const amtBtn = document.getElementById('topProductsModeAmountBtn');
    if (qtyBtn) qtyBtn.classList.toggle('active', topProductsMode === 'qty');
    if (amtBtn) amtBtn.classList.toggle('active', topProductsMode === 'amount');
  }

  function renderTopProductsUnified(){
    if (!topProductsPayload) return;

    const isMoney = (topProductsMode === 'amount');
    const items = isMoney ? (topProductsPayload.top_by_amount || []) : (topProductsPayload.top_by_qty || []);
    const valueKey = isMoney ? 'monto_total' : 'cantidad';
    const title = isMoney ? 'Monto' : 'Cantidad';

    destroyChart(charts.topProducts);
    charts.topProducts = renderTopProducts('topProductsChart', items, 'producto_nombre', valueKey, title, isMoney);

    renderTopProductsList('topProductsListBody', items, 'producto_nombre', valueKey, isMoney);

    const hint = document.getElementById('topProductsHint');
    if (hint) hint.textContent = '';

    const header = document.getElementById('topProductsValueHeader');
    if (header) header.textContent = isMoney ? 'Monto' : 'Unidades';

    syncTopProductsToggleUI();
  }

  function renderSalesByHour(items){
    const canvas = document.getElementById('salesByHourChart');
    if (!canvas) return null;

    const labels = Array.from({length: 24}, (_, i) => String(i).padStart(2,'0') + ':00');
    const totals = Array.from({length: 24}, () => 0);

    for (const row of (items || [])) {
      const h = Number(row.hour);
      if (Number.isInteger(h) && h >= 0 && h <= 23) totals[h] = Number(row.total_monto || 0);
    }

    return new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: totals,
          borderColor: 'rgba(15,157,88,0.95)',
          backgroundColor: 'rgba(15,157,88,0.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 2,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } }
        },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderTopMargin(payload){
    const canvas = document.getElementById('topMarginChart');
    if (!canvas) return;

    const rows = payload.top_by_margin_pct || [];
    const labels = rows.map(r => (r.producto_nombre || '').slice(0, 32));
    const values = rows.map(r => Number(r.margen_pct || 0));

    charts.topMargin = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: 'rgba(244,160,0,0.25)',
          borderColor: 'rgba(244,160,0,0.85)',
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => formatPct(ctx.parsed.y, 1) } } },
        scales: { y: { ticks: { callback: (v) => `${Number(v).toFixed(0)}%` } } }
      }
    });
  }

  function renderPareto(payload){
    const canvas = document.getElementById('paretoChart');
    if (!canvas) return;

    const rows = payload.series || [];
    const labels = rows.map(r => String(r.rank));
    const values = rows.map(r => Number(r.cum_share_pct || 0));

    charts.pareto = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: 'rgba(99,102,241,0.95)',
          backgroundColor: 'rgba(99,102,241,0.10)',
          fill: true,
          tension: 0.25,
          pointRadius: 2,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => formatPct(ctx.parsed.y, 1) } } },
        scales: { y: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } } }
      }
    });
  }

  function renderZombies(payload){
    const body = document.getElementById('zombiesTableBody');
    if (!body) return;
    const rows = payload.zombies || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="2" class="muted">No hay productos sin ventas en ese rango.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
        <td class="text-end">${formatCLP(r.stock || 0)}</td>
      </tr>
    `).join('');
  }

  function renderAntisocial(payload){
    const body = document.getElementById('antisocialTableBody');
    if (!body) return;
    const rows = payload.antisocial || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4" class="muted">Sin resultados en el rango.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(r => {
      const rate = (typeof r.solo_rate === 'number') ? `${(r.solo_rate * 100).toFixed(1)}%` : 'N/D';
      return `
        <tr>
          <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
          <td class="text-end">${formatCLP(r.solo_tickets || 0)}</td>
          <td class="text-end">${formatCLP(r.tickets_with_product || 0)}</td>
          <td class="text-end">${rate}</td>
        </tr>
      `;
    }).join('');
  }

  function renderAttach(payload){
    const body = document.getElementById('attachTableBody');
    if (!body) return;
    const rows = payload.attached || [];
    const ticketsA = payload.tickets_with_primary || 0;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4" class="muted">Sin adjuntos (o sin ventas del producto A en el rango).</td></tr>';
      return;
    }
    body.innerHTML = rows.map(r => {
      const rate = (typeof r.attach_rate === 'number') ? `${(r.attach_rate * 100).toFixed(1)}%` : 'N/D';
      return `
        <tr>
          <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
          <td class="text-end">${formatCLP(ticketsA)}</td>
          <td class="text-end">${formatCLP(r.tickets_with_both || 0)}</td>
          <td class="text-end">${rate}</td>
        </tr>
      `;
    }).join('');
  }

  function renderVolatility(payload){
    const highBody = document.getElementById('volatilityHighBody');
    const lowBody = document.getElementById('volatilityLowBody');
    if (!highBody || !lowBody) return;

    const high = payload.high || [];
    const low = payload.low || [];

    if (!high.length) highBody.innerHTML = '<tr><td colspan="3" class="muted">Sin datos suficientes.</td></tr>';
    else highBody.innerHTML = high.map(r => `
      <tr>
        <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
        <td class="text-end">${Number(r.cv || 0).toFixed(2)}</td>
        <td class="text-end">${formatCLP(r.units || 0)}</td>
      </tr>
    `).join('');

    if (!low.length) lowBody.innerHTML = '<tr><td colspan="3" class="muted">Sin datos suficientes.</td></tr>';
    else lowBody.innerHTML = low.map(r => `
      <tr>
        <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
        <td class="text-end">${Number(r.cv || 0).toFixed(2)}</td>
        <td class="text-end">${formatCLP(r.units || 0)}</td>
      </tr>
    `).join('');
  }

  function renderElasticity(payload){
    const result = document.getElementById('elasticityResult');
    if (!result) return;
    if (!payload.available) {
      result.innerHTML = `<div class="muted">${payload.message || 'No disponible.'}</div>`;
      return;
    }

    const e = payload.elasticity;
    const pctUnits = (payload.pct_units ?? 0) * 100;
    const pctPrice = (payload.pct_price ?? 0) * 100;
    const eTxt = (e === null || e === undefined) ? 'N/D' : e.toFixed(2);
    result.innerHTML = `
      <div class="kpi-card">
        <h3>Elasticidad: ${eTxt}</h3>
        <p class="muted mb-0">${payload.month_prev} → ${payload.month_curr} | ΔVolumen: ${pctUnits.toFixed(1)}% | ΔPrecio: ${pctPrice.toFixed(1)}%</p>
      </div>
    `;
  }

  function renderNewProducts(payload){
    const summary = document.getElementById('newProductsSummary');
    const detail = document.getElementById('newProductsDetail');
    const winnersBody = document.getElementById('newWinnersBody');
    const losersBody = document.getElementById('newLosersBody');
    if (!summary || !detail || !winnersBody || !losersBody) return;

    summary.textContent = `${payload.success || 0} éxito / ${payload.fail || 0} fracaso`;
    detail.textContent = `Nuevos: ${payload.new_products_total || 0} | Baseline: ${Number(payload.baseline_units_per_product || 0).toFixed(2)} u/producto (periodo)`;

    const winners = payload.winners || [];
    const losers = payload.losers || [];

    winnersBody.innerHTML = winners.length ? winners.map(r => `
      <tr><td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td><td class="text-end">${formatCLP(r.units || 0)}</td></tr>
    `).join('') : '<tr><td colspan="2" class="muted">Sin datos.</td></tr>';

    losersBody.innerHTML = losers.length ? losers.map(r => `
      <tr><td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td><td class="text-end">${formatCLP(r.units || 0)}</td></tr>
    `).join('') : '<tr><td colspan="2" class="muted">Sin datos.</td></tr>';
  }

  function renderPriceDist(payload){
    const canvas = document.getElementById('priceDistChart');
    if (!canvas) return;

    const rows = payload.buckets || [];
    const labels = rows.map(r => r.label || '');
    const values = rows.map(r => Number(r.revenue || 0));

    charts.priceDist = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: 'rgba(11,132,193,0.25)',
          borderColor: 'rgba(11,132,193,0.75)',
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } } },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderOffers(payload){
    const canvas = document.getElementById('offersChart');
    if (!canvas) return;

    const offer = payload.offer?.revenue ?? 0;
    const full = payload.full?.revenue ?? 0;

    charts.offers = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Precio full', 'Oferta (estimado)'],
        datasets: [{
          data: [full, offer],
          backgroundColor: ['rgba(156,163,175,0.35)', 'rgba(244,160,0,0.35)'],
          borderColor: ['rgba(156,163,175,0.85)', 'rgba(244,160,0,0.85)'],
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `$${formatCLP(ctx.parsed.y)}` } } },
        scales: { y: { ticks: { callback: (v) => `$${formatCLP(v)}` } } }
      }
    });
  }

  function renderImpulse(payload){
    const body = document.getElementById('impulseTableBody');
    if (!body) return;
    const rows = payload.top_impulse || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="3" class="muted">Sin resultados con la heurística actual.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(r => `
      <tr>
        <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
        <td class="text-end">${formatCLP(r.items || 0)}</td>
        <td class="text-end">$${formatCLP(r.revenue || 0)}</td>
      </tr>
    `).join('');
  }

  function renderProjection(payload){
    const v = document.getElementById('projectionValue');
    const d = document.getElementById('projectionDetail');
    if (v) v.textContent = `$${formatCLP(payload.projection_close_month || 0)}`;
    if (d) d.textContent = `MTD: $${formatCLP(payload.mtd_total || 0)} (día ${payload.day_of_month}/${payload.days_in_month})`;
  }

  function renderYoY(payload){
    const v = document.getElementById('yoyValue');
    const d = document.getElementById('yoyDetail');
    if (v) {
      if (payload.yoy_pct === null || payload.yoy_pct === undefined) v.textContent = 'N/D';
      else v.textContent = formatPct(payload.yoy_pct, 1);
    }
    if (d) d.textContent = `Actual: $${formatCLP(payload.current?.total_monto || 0)} | Año anterior: $${formatCLP(payload.prev_year?.total_monto || 0)}`;
  }

  function renderBasketTable(rows){
    const body = document.getElementById('basketTableBody');
    if (!body) return;

    if (!rows || rows.length === 0) {
      body.innerHTML = '<tr><td colspan="4" class="muted">Sin resultados para ese producto con los filtros actuales.</td></tr>';
      return;
    }

    body.innerHTML = rows.map(r => {
      const conf = (typeof r.confidence === 'number') ? (r.confidence * 100).toFixed(1) + '%' : '';
      const lift = (typeof r.lift === 'number') ? r.lift.toFixed(2) : '';
      return `
        <tr>
          <td>${r.producto_nombre || ('Producto #' + r.producto_id)}</td>
          <td class="text-end">${formatCLP(r.cooc_sales || 0)}</td>
          <td class="text-end">${conf}</td>
          <td class="text-end">${lift}</td>
        </tr>
      `;
    }).join('');
  }

  async function loadResumen(){
    if (!ensureFiltersApplied()) return;

    setStatus('Cargando KPIs principales…', 'text-muted');
    const overview = await fetchJson(`/reports/market/api/overview/?${activeParams.toString()}`);

    renderKpiGrid(overview);

    destroyChart(charts.payment);
    renderPaymentMethods(overview.payment_methods || []);

    const notes = document.getElementById('overviewNotes');
    if (notes) {
      const r = overview.returns || {};
      const msg = r.available ? '' : (r.message || '');
      notes.innerHTML = `
        <div><strong>Clave:</strong> Venta Total Neta = suma del total final de cada ticket en el rango.</div>
        <div><strong>Descuentos:</strong> estimado comparando precio unitario vs precio de lista del producto.</div>
        <div><strong>Devoluciones/anulaciones:</strong> ${msg || 'N/D'}</div>
      `;
    }

    setStatus('Resumen listo. Abre pestañas para más detalle.', 'text-success');
  }

  async function loadOperacion(){
    if (!ensureFiltersApplied()) return;
    if (loadedTabs.has('operacion')) return;
    loadedTabs.add('operacion');

    setStatus('Cargando operación (heatmap, sucursales, tendencia)…', 'text-muted');

    const [heat, weekend, monthly, branches, paycycle, peakDensity, terminals] = await Promise.all([
      fetchJson(`/reports/market/api/heatmap/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/weekend-vs-weekday/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/monthly-trend/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/branches/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/paycycle/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/peak-density/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/terminals/?${activeParams.toString()}`),
    ]);

    cachedHeatmap = heat;
    renderHeatmap(cachedHeatmap, heatmapMode);

    destroyChart(charts.weekend);
    destroyChart(charts.monthly);
    destroyChart(charts.branches);
    destroyChart(charts.paycycle);
    destroyChart(charts.terminals);

    renderWeekendChart(weekend);
    renderMonthlyTrend(monthly);
    renderBranches(branches);

    renderPaycycleChart(paycycle);
    renderPeakDensity(peakDensity);
    renderTerminalChart(terminals);

    setStatus('Operación lista.', 'text-success');
  }

  async function loadProductos(){
    if (!ensureFiltersApplied()) return;
    if (loadedTabs.has('productos')) return;
    loadedTabs.add('productos');

    setStatus('Cargando productos (top, margen, pareto, huesos)…', 'text-muted');

    const [top, hour, margin, pareto, zombies, antisocial] = await Promise.all([
      fetchJson(`/reports/market/api/top-products/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/sales-by-hour/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/top-margin-products/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/pareto/?${activeParams.toString()}&limit=40`),
      fetchJson(`/reports/market/api/zombies/?${activeParams.toString()}&days=30`),
      fetchJson(`/reports/market/api/antisocial-products/?${activeParams.toString()}&limit=20`),
    ]);

    destroyChart(charts.topProducts);
    destroyChart(charts.byHour);
    destroyChart(charts.topMargin);
    destroyChart(charts.pareto);

    topProductsPayload = top;
    if (topProductsMode !== 'qty' && topProductsMode !== 'amount') topProductsMode = 'qty';
    renderTopProductsUnified();

    charts.byHour = renderSalesByHour(hour.by_hour);

    const h3 = document.getElementById('salesByHourHint'); if (h3) h3.textContent = '';

    renderTopMargin(margin);
    renderPareto(pareto);
    renderZombies(zombies);
    renderAntisocial(antisocial);

    setStatus('Productos listos.', 'text-success');
  }

  async function loadComportamiento(){
    if (!ensureFiltersApplied()) return;
    if (loadedTabs.has('comportamiento')) return;
    loadedTabs.add('comportamiento');

    setStatus('Cargando comportamiento (precios, ofertas, impulso)…', 'text-muted');

    const [price, offers, impulse, volatility] = await Promise.all([
      fetchJson(`/reports/market/api/price-distribution/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/offers/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/impulse/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/volatility/?${activeParams.toString()}`),
    ]);

    destroyChart(charts.priceDist);
    destroyChart(charts.offers);

    renderPriceDist(price);
    renderOffers(offers);
    renderImpulse(impulse);
    renderVolatility(volatility);

    setStatus('Comportamiento listo. Market Basket es bajo demanda.', 'text-success');
  }

  async function loadAlertas(){
    if (!ensureFiltersApplied()) return;
    if (loadedTabs.has('alertas')) return;
    loadedTabs.add('alertas');

    setStatus('Cargando alertas (proyección, YoY)…', 'text-muted');

    const [proj, yoy, newProducts] = await Promise.all([
      fetchJson(`/reports/market/api/projection/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/yoy/?${activeParams.toString()}`),
      fetchJson(`/reports/market/api/new-products/?${activeParams.toString()}`),
    ]);

    renderProjection(proj);
    renderYoY(yoy);
    renderNewProducts(newProducts);

    setStatus('Alertas listas.', 'text-success');
  }

  function setupTabLazyLoading(){
    const mapping = {
      '#tab-operacion': loadOperacion,
      '#tab-productos': loadProductos,
      '#tab-comportamiento': loadComportamiento,
      '#tab-alertas': loadAlertas,
    };

    const tabButtons = document.querySelectorAll('#marketTabs button[data-bs-toggle="tab"]');
    for (const btn of tabButtons) {
      const target = btn.getAttribute('data-bs-target');
      const loader = mapping[target];
      if (!loader) continue;

      btn.addEventListener('shown.bs.tab', () => {
        loader().catch(err => {
          console.error(err);
          setStatus(err?.message || 'Error cargando pestaña', 'text-danger');
        });
      });

      btn.addEventListener('click', () => {
        setTimeout(() => {
          loader().catch(err => {
            console.error(err);
            setStatus(err?.message || 'Error cargando pestaña', 'text-danger');
          });
        }, 0);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('marketFilters');
    const heatmapTicketsBtn = document.getElementById('heatmapModeTicketsBtn');
    const heatmapAmountBtn = document.getElementById('heatmapModeAmountBtn');
    const basketBtn = document.getElementById('loadBasketBtn');
    const runwayBtn = document.getElementById('loadRunwayBtn');
    const attachBtn = document.getElementById('loadAttachBtn');
    const elasticityBtn = document.getElementById('loadElasticityBtn');
    const topQtyModeBtn = document.getElementById('topProductsModeQtyBtn');
    const topAmountModeBtn = document.getElementById('topProductsModeAmountBtn');

    const empty = document.getElementById('kpiEmptyMsg');
    if (empty) empty.style.display = '';

    setupTabLazyLoading();

    // Top products toggle (Cantidad / Monto)
    function setTopProductsMode(mode){
      if (mode !== 'qty' && mode !== 'amount') return;
      topProductsMode = mode;
      saveTopProductsModeToStorage(mode);
      // Only re-render if we already loaded the Productos tab
      if (topProductsPayload) renderTopProductsUnified();
      else syncTopProductsToggleUI();
    }

    if (topQtyModeBtn) topQtyModeBtn.addEventListener('click', () => setTopProductsMode('qty'));
    if (topAmountModeBtn) topAmountModeBtn.addEventListener('click', () => setTopProductsMode('amount'));

    // Restore last selection
    const storedMode = loadTopProductsModeFromStorage();
    if (storedMode) topProductsMode = storedMode;
    syncTopProductsToggleUI();

    // Restore/capture "Ver lista completa" state
    const topListEl = document.getElementById('topProductsList');
    const storedTopListOpen = loadTopProductsListOpenFromStorage();
    if (storedTopListOpen !== null) setCollapseOpenById('topProductsList', storedTopListOpen);

    if (topListEl) {
      topListEl.addEventListener('shown.bs.collapse', () => saveTopProductsListOpenToStorage(true));
      topListEl.addEventListener('hidden.bs.collapse', () => saveTopProductsListOpenToStorage(false));
    }

    function syncHeatmapToggleUI(){
      if (heatmapTicketsBtn) heatmapTicketsBtn.classList.toggle('active', heatmapMode === 'tickets');
      if (heatmapAmountBtn) heatmapAmountBtn.classList.toggle('active', heatmapMode === 'amount');
    }

    function setHeatmapMode(mode){
      heatmapMode = (mode === 'amount') ? 'amount' : 'tickets';
      syncHeatmapToggleUI();
      if (cachedHeatmap) renderHeatmap(cachedHeatmap, heatmapMode);
    }

    syncHeatmapToggleUI();
    if (heatmapTicketsBtn) heatmapTicketsBtn.addEventListener('click', () => setHeatmapMode('tickets'));
    if (heatmapAmountBtn) heatmapAmountBtn.addEventListener('click', () => setHeatmapMode('amount'));

    async function applyFilters(){
      if (!form) return;
      const params = qs(form);
      if (!params.get('start_date') || !params.get('end_date')) {
        setStatus('Selecciona fecha inicio y fin.', 'text-danger');
        return;
      }

      activeParams = params;
      loadedTabs.clear();
      clearVisuals();

      async function maybeLoadActiveTab(){
        const activeBtn = document.querySelector('#marketTabs .nav-link.active');
        const target = activeBtn?.getAttribute('data-bs-target') || '#tab-resumen';
        if (target === '#tab-resumen') return;
        const mapping = {
          '#tab-operacion': loadOperacion,
          '#tab-productos': loadProductos,
          '#tab-comportamiento': loadComportamiento,
          '#tab-alertas': loadAlertas,
        };
        const loader = mapping[target];
        if (loader) await loader();
      }

      try {
        await loadResumen();
        await maybeLoadActiveTab();
      } catch (err) {
        console.error(err);
        setStatus(err?.message || 'Error cargando resumen', 'text-danger');
      }
    }

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await applyFilters();
      });
    }

    const z30 = document.getElementById('zombies30');
    const z60 = document.getElementById('zombies60');
    async function reloadZombies(days){
      if (!ensureFiltersApplied()) {
        setStatus('Primero aplica filtros.', 'text-danger');
        return;
      }
      if (!loadedTabs.has('productos')) {
        setStatus('Abre la pestaña Productos para ver “huesos”.', 'text-muted');
        return;
      }
      try {
        const data = await fetchJson(`/reports/market/api/zombies/?${activeParams.toString()}&days=${days}`);
        renderZombies(data);
      } catch (err) {
        console.error(err);
        setStatus(err?.message || 'Error cargando huesos', 'text-danger');
      }
    }
    if (z30) z30.addEventListener('click', () => reloadZombies(30));
    if (z60) z60.addEventListener('click', () => reloadZombies(60));

    if (basketBtn) {
      basketBtn.addEventListener('click', async () => {
        try {
          if (!ensureFiltersApplied()) {
            const basketStatus = document.getElementById('basketStatus');
            if (basketStatus) basketStatus.textContent = 'Primero aplica filtros.';
            return;
          }

          const pid = (document.getElementById('basketProductId')?.value || '').trim();
          const basketStatus = document.getElementById('basketStatus');
          if (!pid) {
            if (basketStatus) basketStatus.textContent = 'Ingresa un producto (ID/código/barras).';
            return;
          }

          const params = new URLSearchParams(activeParams.toString());
          params.set('producto_id', pid);
          if (basketStatus) basketStatus.textContent = 'Calculando co-ocurrencia…';

          const data = await fetchJson(`/reports/market/api/basket/?${params.toString()}`);
          renderBasketTable(data.recommendations || []);
          if (basketStatus) basketStatus.textContent = `Listo. Ventas en filtro: ${formatCLP(data.total_sales || 0)} | Ventas con A: ${formatCLP(data.sales_with_product || 0)}`;
        } catch (err) {
          console.error(err);
          const basketStatus = document.getElementById('basketStatus');
          if (basketStatus) basketStatus.textContent = (err && err.message) ? err.message : 'Error al calcular basket';
          renderBasketTable([]);
        }
      });
    }

    if (attachBtn) {
      attachBtn.addEventListener('click', async () => {
        try {
          if (!ensureFiltersApplied()) {
            const attachStatus = document.getElementById('attachStatus');
            if (attachStatus) attachStatus.textContent = 'Primero aplica filtros.';
            return;
          }
          const pid = (document.getElementById('attachPrimaryId')?.value || '').trim();
          const attachStatus = document.getElementById('attachStatus');
          if (!pid) {
            if (attachStatus) attachStatus.textContent = 'Ingresa un producto A (ID/código/barras).';
            return;
          }
          const params = new URLSearchParams(activeParams.toString());
          params.set('primary_id', pid);
          if (attachStatus) attachStatus.textContent = 'Calculando adjuntos…';
          const data = await fetchJson(`/reports/market/api/attach-rate/?${params.toString()}`);
          renderAttach(data);
          if (attachStatus) attachStatus.textContent = 'Listo.';
        } catch (err) {
          console.error(err);
          const attachStatus = document.getElementById('attachStatus');
          if (attachStatus) attachStatus.textContent = err?.message || 'Error al calcular adjuntos';
          renderAttach({ attached: [], tickets_with_primary: 0 });
        }
      });
    }

    if (runwayBtn) {
      runwayBtn.addEventListener('click', async () => {
        const runwayStatus = document.getElementById('runwayStatus');
        const runwayResult = document.getElementById('runwayResult');
        try {
          if (!ensureFiltersApplied()) {
            if (runwayStatus) runwayStatus.textContent = 'Primero aplica filtros.';
            return;
          }
          const pid = (document.getElementById('runwayProductId')?.value || '').trim();
          if (!pid) {
            if (runwayStatus) runwayStatus.textContent = 'Ingresa un producto (ID/código/barras).';
            return;
          }

          const params = new URLSearchParams(activeParams.toString());
          params.set('producto_id', pid);
          if (runwayStatus) runwayStatus.textContent = 'Calculando runway…';

          const data = await fetchJson(`/reports/market/api/runway/?${params.toString()}`);
          const days = data.runway_days;
          const daysTxt = (days === null || days === undefined) ? 'N/D' : `${days.toFixed(1)} días`;
          if (runwayResult) {
            runwayResult.innerHTML = `
              <div class="kpi-card">
                <h3>${daysTxt}</h3>
                <p class="mb-0">${data.producto_nombre || ('Producto #' + data.producto_id)} | Stock: ${formatCLP(data.stock || 0)} | Promedio diario: ${Number(data.avg_daily_units || 0).toFixed(2)} u/día</p>
              </div>
            `;
          }
          if (runwayStatus) runwayStatus.textContent = 'Listo.';
        } catch (err) {
          console.error(err);
          if (runwayStatus) runwayStatus.textContent = err?.message || 'Error calculando runway';
          if (runwayResult) runwayResult.innerHTML = '';
        }
      });
    }

    if (elasticityBtn) {
      elasticityBtn.addEventListener('click', async () => {
        const status = document.getElementById('elasticityStatus');
        try {
          if (!ensureFiltersApplied()) {
            if (status) status.textContent = 'Primero aplica filtros.';
            return;
          }
          const pid = (document.getElementById('elasticityProductId')?.value || '').trim();
          if (!pid) {
            if (status) status.textContent = 'Ingresa un producto (ID/código/barras).';
            return;
          }
          const params = new URLSearchParams(activeParams.toString());
          params.set('producto_id', pid);
          if (status) status.textContent = 'Calculando elasticidad…';
          const data = await fetchJson(`/reports/market/api/elasticity/?${params.toString()}`);
          renderElasticity(data);
          if (status) status.textContent = 'Listo.';
        } catch (err) {
          console.error(err);
          if (status) status.textContent = err?.message || 'Error calculando elasticidad';
          renderElasticity({ available: false, message: err?.message || 'Error' });
        }
      });
    }
  });
})();
