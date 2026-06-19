(function () {
  'use strict';
  var g = document.getElementById('id_gravidade');
  var u = document.getElementById('id_urgencia');
  var t = document.getElementById('id_tendencia');
  var display = document.getElementById('gut-display');
  var suggest = document.getElementById('gut-suggestion');

  if (!g || !u || !t || !display) return;

  function calc() {
    var gv = parseInt(g.value, 10);
    var uv = parseInt(u.value, 10);
    var tv = parseInt(t.value, 10);
    if (isNaN(gv) || isNaN(uv) || isNaN(tv)) {
      display.textContent = '—';
      display.className = 'badge bg-secondary fs-5';
      if (suggest) suggest.textContent = '';
      return;
    }
    var gut = gv * uv * tv;
    display.textContent = gut;
    var cls, label;
    // Limiares espelham Achado.LIMITE_GUT_P1/P2 em apps/inspecoes/models.py —
    // mudar um lado sem o outro reintroduz a divergência que já existiu aqui.
    if (gut >= 75) {
      cls = 'bg-danger';
      label = 'Sugestão: Crítico (P1)';
    } else if (gut >= 20) {
      cls = 'bg-warning text-dark';
      label = 'Sugestão: Regular (P2)';
    } else {
      cls = 'bg-success';
      label = 'Sugestão: Mínimo (P3)';
    }
    display.className = 'badge ' + cls + ' fs-5';
    if (suggest) suggest.textContent = label;
  }

  g.addEventListener('input', calc);
  u.addEventListener('input', calc);
  t.addEventListener('input', calc);
  calc();
})();
