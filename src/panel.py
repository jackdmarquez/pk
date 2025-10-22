import os, csv, glob
from .utils import ensure_dir
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
def summarize_card(csv_path):
    name = os.path.splitext(os.path.basename(csv_path))[0].replace("-", " ").title()
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({"ts": r.get("ts",""),
                             "price_now": float(r.get("price_now",0) or 0),
                             "market_now": float(r.get("market_now",0) or 0)})
            except: pass
    if not rows: return None
    last = rows[-1]; p_now = last["price_now"]
    p_24h = rows[-2]["price_now"] if len(rows)>1 else p_now
    p_7d  = rows[0]["price_now"]
    pct_24h = (p_now - p_24h)/p_24h if p_24h else 0
    pct_7d  = (p_now - p_7d)/p_7d if p_7d else 0
    breakout = p_now > max([r["price_now"] for r in rows])
    return {"name": name, "price_now": p_now, "market_now": last["market_now"],
            "pct_24h": pct_24h, "pct_7d": pct_7d, "breakout": breakout}
def build_panel():
    ensure_dir(DOCS_DIR)
    card_csvs = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    summary = []
    for path in card_csvs:
        s = summarize_card(path)
        if s: summary.append(s)
    fields = ["name","price_now","market_now","pct_24h","pct_7d","breakout"]
    with open(os.path.join(DOCS_DIR, "data.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in summary: w.writerow(r)
    html = ["<!doctype html><html><head><meta charset='utf-8'><title>Pokémon Panel</title>",
            "<style>body{font-family:Arial,sans-serif;padding:20px;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ddd;padding:8px;}th{background:#f5f5f5}</style></head><body>",
            "<h1>Pokémon Price Panel</h1>",
            "<p><a href='health.html'>Ver Health Dashboard</a></p>",
            "<table><thead><tr><th>Carta</th><th>Ahora</th><th>Market</th><th>Δ24h</th><th>Δ7d</th><th>Breakout</th></tr></thead><tbody>"]
    for r in summary:
        html.append(f"<tr><td>{r['name']}</td><td>${r['price_now']:.2f}</td><td>${r['market_now']:.2f}</td><td>{r['pct_24h']*100:.1f}%</td><td>{r['pct_7d']*100:.1f}%</td><td>{'✅' if r['breakout'] else '—'}</td></tr>")
    html.append("</tbody></table></body></html>")
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(html))
if __name__ == "__main__":
    build_panel()
