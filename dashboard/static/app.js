// Shared utilities
function el(id) { return document.getElementById(id); }
function show(id) { const e = el(id); if (e) e.style.display = 'block'; }
function hide(id) { const e = el(id); if (e) e.style.display = 'none'; }
