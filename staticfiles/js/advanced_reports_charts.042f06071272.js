(function(){
  function drawHeatmap(data){
    // data: {dow: {hr: {transacciones, ingreso}}}
    // build matrix 7x24
    const labels = ['Dom','Lun','Mar','Mie','Jue','Vie','Sab'];
    const matrix = [];
    for(let d=1; d<=7; d++){
      const row = [];
      for(let h=0; h<24; h++){
        const cell = (data[d] && data[d][h]) ? data[d][h].transacciones : 0;
        row.push(cell);
      }
      matrix.push(row);
    }
    // Flatten and use a bar-scatter style (Chart.js doesn't have native heatmap here)
    const ctx = document.getElementById('heatmapChart').getContext('2d');
    // Simple rendering: show as stacked bars per day (24 bars each)
    const datasets = [];
    for(let h=0; h<24; h++){
      datasets.push({ label: String(h), data: matrix.map(r=>r[h]), backgroundColor: 'rgba(99,102,241,0.15)' });
    }
    const labelsX = labels;
    if(window._heatmapChart) window._heatmapChart.destroy();
    window._heatmapChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labelsX,
        datasets: datasets
      },
      options: { responsive:true, plugins:{ legend:{display:false} }, scales:{ x:{ stacked:true }, y:{ beginAtZero:true } } }
    });
  }

  function drawTrend(thisData, prevData){
    const ctx = document.getElementById('trendChart').getContext('2d');
    const labels = thisData.map(d=>d.day);
    const dataThis = thisData.map(d=>d.ingreso);
    const dataPrev = prevData.map(d=>d.ingreso);
    if(window._trendChart) window._trendChart.destroy();
    window._trendChart = new Chart(ctx, {
      type:'line',
      data:{ labels: labels, datasets:[ {label:'Este mes', data:dataThis, borderColor:'rgba(56,189,248,0.9)', backgroundColor:'rgba(56,189,248,0.15)', tension:0.3}, {label:'Mes anterior', data:dataPrev, borderColor:'rgba(167,139,250,0.9)', backgroundColor:'rgba(167,139,250,0.12)', tension:0.3} ] },
      options:{ responsive:true, plugins:{ legend:{position:'top'} }, scales:{ y:{ beginAtZero:true } } }
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    try{
      const d = window.AdvReportsData || {};
      drawHeatmap(d.heatmap || {});
      drawTrend(d.trend_this || [], d.trend_prev || []);
    }catch(e){ console.error('charts init error', e); }
  });
})();
