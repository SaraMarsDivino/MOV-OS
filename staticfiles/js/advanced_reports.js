// Placeholder for enhanced Advanced Reports interactivity.
// Will add dynamic charts, section toggling, and async reloads.
document.addEventListener('DOMContentLoaded', function () {
  if (typeof ADV_DATA === 'undefined') return;
  // Parse datasets
  let daily = ADV_DATA.daily || [];
  let wave_labels = ADV_DATA.wave_labels || [];
  let wave_gains = ADV_DATA.wave_gains || [];
  let hourly = ADV_DATA.hourly || [];
  let heat = ADV_DATA.heat || [];

  function fmtNumber(v){
    if (v === null || typeof v === 'undefined') return '0';
    try{ return new Intl.NumberFormat('es-CL').format(Math.round(v)); }catch(e){return v}
  }

  try {
    const ctxD = document.getElementById('chartDaily');
    if (ctxD && daily.length) {
      const labels = daily.map(d => d.day);
      const ingresos = daily.map(d => d.ingreso);
      const ganancias = daily.map(d => d.ganancia_neta);
      new Chart(ctxD.getContext('2d'), {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            { label: 'Ingreso', data: ingresos, borderColor: '#40C4FF', backgroundColor: 'rgba(64,196,255,0.08)', tension:0.2 },
            { label: 'Ganancia neta', data: ganancias, borderColor: '#35B400', backgroundColor: 'rgba(53,180,0,0.06)', tension:0.2 }
          ]
        },
        options: { responsive: true, plugins:{ legend:{ labels:{ color:'#fff' } }, tooltip:{ callbacks:{ label: (ctx)=> fmtNumber(ctx.raw) } } }, scales:{ x:{ ticks:{ color:'#ddd' } }, y:{ ticks:{ color:'#ddd' } } }
      });
    }
  } catch(e){ console.error(e) }

  try {
    const ctxW = document.getElementById('waveChart');
    if (ctxW && wave_labels.length) {
      new Chart(ctxW.getContext('2d'), {
        type: 'bar',
        data: { labels: wave_labels, datasets:[{ label:'Ganancia neta (mensual)', data: wave_gains, backgroundColor:'#1d6fa8' }] },
        options: { responsive:true, plugins:{ legend:{ display:false }, tooltip:{ callbacks:{ label:(ctx)=> fmtNumber(ctx.raw) } } }, scales:{ x:{ ticks:{ color:'#ddd' } }, y:{ ticks:{ color:'#ddd' } } }
      });
    }
  } catch(e){ console.error(e) }

  try {
    const ctxH = document.getElementById('chartHourly');
    if (ctxH && hourly.length) {
      const labels = hourly.map(h=> h.hora + ':00');
      const ventas = hourly.map(h=> h.ventas);
      new Chart(ctxH.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets:[{ label:'Ventas por hora', data:ventas, backgroundColor:'#FF9A4D' }] },
        options: { responsive:true, plugins:{ legend:{ display:false } }, scales:{ x:{ ticks:{ color:'#ddd' } }, y:{ ticks:{ color:'#ddd' } } }
      });
    }
  } catch(e){ console.error(e) }

  try {
    const heatContainer = document.getElementById('heatmapContainer');
    if (heatContainer && heat.length){
      let maxVal = 0;
      heat.forEach(row => row.forEach(cell => { maxVal = Math.max(maxVal, cell.ventas); }));
      const days = ['Lun','Mar','Mie','Jue','Vie','Sab','Dom'];
      let html = '<div class="heatmap-grid">';
      html += '<div class="heatmap-row heatmap-header"><div class="cell head empty"></div>';
      for(let h=0; h<24; h++) html += `<div class="cell head">${h}</div>`;
      html += '</div>';
      for(let d=0; d<7; d++){
        html += `<div class="heatmap-row"><div class="cell day">${days[d]}</div>`;
        for(let h=0; h<24; h++){
          const cell = heat[d][h] || {ventas:0, ingreso:0};
          const v = cell.ventas || 0;
          const intensity = maxVal ? Math.round((v/maxVal)*220) : 0;
          html += `<div class="cell" title="${v} ventas; $${Math.round(cell.ingreso)}" style="background: rgba(64,196,255,${0.05 + (intensity/255)}); color:#fff;">${v>0?v:''}</div>`;
        }
        html += '</div>';
      }
      html += '</div>';
      heatContainer.innerHTML = html;
    }
  } catch(e){console.error(e)}

  try{
    const topBody = document.getElementById('topProductosBody');
    if (topBody && ADV_DATA.top_products && ADV_DATA.top_products.length){
      topBody.innerHTML = '';
      ADV_DATA.top_products.forEach(p => {
        const tr = document.createElement('tr');
        const td1 = document.createElement('td'); td1.textContent = p.producto || p['producto__nombre'] || '';
        const td2 = document.createElement('td'); td2.textContent = p.cantidad || p.total_cantidad || '';
        tr.appendChild(td1); tr.appendChild(td2); topBody.appendChild(tr);
      });
    }
  }catch(e){console.error(e)}

});
