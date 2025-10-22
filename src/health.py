import os, json, html
from .utils import ensure_dir
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
def write_health(stats: dict):
    ensure_dir(DOCS_DIR)
    with open(os.path.join(DATA_DIR, "status.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    health_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Health — Pokémon Bot</title>
<style>
body{{font-family:Arial, sans-serif; padding:20px; max-width:1100px; margin:auto;}}
h1{{margin-top:0}} table{{border-collapse:collapse; width:100%; margin-top:10px}}
th,td{{border:1px solid #ddd; padding:8px; font-size:14px}} th{{background:#f5f5f5; text-align:left}}
.badge{{display:inline-block; padding:2px 8px; border-radius:12px; background:#eee; margin-right:6px}}
.small{{color:#666; font-size:13px}} .btn{{display:inline-block; padding:10px 14px; border:1px solid #444; border-radius:8px; text-decoration:none; margin:6px 6px 0 0}}
</style>
<script>
function buildActionsUrl() {
  const host = window.location.hostname;
  const path = window.location.pathname;
  const owner = host.split('.')[0];
  const repo = path.split('/')[1] || "";
  if(!owner || !repo) return null;
  return `https://github.com/${owner}/${repo}/actions/workflows/cron.yml`;
}
window.addEventListener('DOMContentLoaded', () => {
  const a = buildActionsUrl();
  if (a) {
    document.querySelectorAll('.actions-link').forEach(b => b.setAttribute('href', a));
  }
});
</script>
</head><body>
<h1>Health Dashboard</h1>
<div class="small">Started: {html.escape(stats.get('started',''))} UTC · Duration: {stats.get('duration_sec',0):.1f}s · Batch: {stats.get('batch_size',0)} · Processed: {stats.get('processed',0)}/{stats.get('cards_total',0)}</div>
<div style="margin-top:10px;">
  <a class="btn actions-link" href="#" target="_blank">🔁 Abrir "Run workflow"</a>
  <a class="btn actions-link" href="#" target="_blank">📣 Abrir y activar send_ping</a>
  <a class="btn actions-link" href="#" target="_blank">🧪 Abrir y activar force_test_alert</a>
</div>
<h2>Resumen</h2>
<div>
  <span class="badge">timeouts: {stats.get('timeouts',0)}</span>
  <span class="badge">net_errors: {stats.get('net_errors',0)}</span>
  <span class="badge">parse_errors: {stats.get('parse_errors',0)}</span>
  <span class="badge">alerts_sent: {stats.get('alerts_sent',0)}</span>
</div>
<h2>Cartas procesadas</h2>
<table>
  <thead><tr><th>Carta</th><th>entries</th><th>precio_now</th><th>Δ24h</th><th>Δ7d</th><th>breakout</th><th>alertada</th><th>nota</th></tr></thead>
  <tbody>
"""
    for item in stats.get("items", []):
        note = html.escape(item.get("note",""))
        health_html += f"<tr><td>{html.escape(item.get('name',''))}</td><td>{item.get('entries',0)}</td><td>${item.get('price_now',0):.2f}</td><td>{item.get('pct_24h',0)*100:.1f}%</td><td>{item.get('pct_7d',0)*100:.1f}%</td><td>{'✅' if item.get('breakout') else '—'}</td><td>{'📣' if item.get('alerted') else '—'}</td><td>{note}</td></tr>\n"
    health_html += """
  </tbody>
</table>
<p class="small">Tip: los botones abren la página del workflow. Allí puedes marcar <i>send_ping</i> y/o <i>force_test_alert</i> y presionar <b>Run workflow</b>.</p>
</body></html>
"""
    with open(os.path.join(DOCS_DIR, "health.html"), "w", encoding="utf-8") as f:
        f.write(health_html)
