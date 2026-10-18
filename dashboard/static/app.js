function el(id) { return document.getElementById(id); }
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}
async function getJSON(url) { return (await fetch(url)).json(); }
async function postJSON(url, body) {
  const resp = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                 body: JSON.stringify(body)});
  return resp.json();
}
const NAV = `<nav class="nav"><a class="nav-brand" href="/">ENG-05 · The Harness Model</a>
  <div class="nav-links"><a href="/">Overview</a><a href="/demo">Demo</a>
  <a href="/metrics">Metrics</a><a href="/eval">Eval</a></div></nav>`;
document.body.insertAdjacentHTML('afterbegin', NAV);
