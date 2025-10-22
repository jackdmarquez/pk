# src/run.py
import os, yaml
from statistics import median
from .collectors.pokemontcg import fetch_card_entries
from .signals import price_spike_signal
from .alerting import send_telegram_text, send_telegram_photo
from .utils import slugify, ensure_dir, append_history_csv, load_last_n, now_ts
from .alerting import send_telegram_text


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

def load_cfg():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def augment_queries(base_queries, min_grade=None, language=None, include_terms=None):
    q = list(base_queries)
    include_terms = include_terms or []
    if language and language.lower().startswith("en"):
        include_terms.append("English")
    if min_grade:
        mg = str(min_grade).upper()
        if "PSA10" in mg or "PSA 10" in mg: include_terms.append('"PSA 10"')
        elif "PSA9" in mg or "PSA 9" in mg: include_terms.append('"PSA 9"')
    return q, include_terms

def main():
    cfg = load_cfg()
    ensure_dir(DATA_DIR); ensure_dir(DOCS_DIR)

    pokemontcg_key = os.getenv(cfg["sources"]["pokemontcg"]["api_key_env"], "")
    use_trend = cfg.get("run", {}).get("use_cardmarket_trend", True)
    min_avg7 = cfg["thresholds"].get("min_avg7_usd", 0)

    cards_summary = []

    if os.getenv("SEND_PING","0") == "1":
        send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "🤖 Bot iniciado (healthcheck).")


    for item in cfg["watchlist"]:
        try:
            base_queries = item["queries"]
            min_grade = item.get("min_grade")
            language = item.get("language")
            include_terms = item.get("include_terms", [])
            queries, _ = augment_queries(base_queries, min_grade, language, include_terms)

            name = item["name"]
            print(f"[watch] {name}")

            entries = fetch_card_entries(queries, api_key=pokemontcg_key, max_cards=2)
            print(f"[{name}] entries={len(entries)} samples={[e.get('now') for e in entries][:3]}")

            # --- precios ---
            from statistics import median
            market_candidates = [e["now"] for e in entries if e.get("now") is not None]
            p_market_now = median(market_candidates) if market_candidates else 0.0

            if p_market_now == 0.0:
                cm_values = []
                for e in entries:
                    cm = (e.get("cardmarket") or {}).get("prices") if isinstance(e, dict) else None
                    if cm:
                        for k in ("avg1","avg7","avg30"):
                            if cm.get(k): cm_values.append(cm[k])
                p_market_now = median(cm_values) if cm_values else 0.0

            image_url = None
            for e in entries:
                if e.get("image_large"): image_url = e["image_large"]; break

            price_now = p_market_now

            # --- histórico ---
            fname = os.path.join(DATA_DIR, f"{slugify(name)}.csv")
            last_prices = load_last_n(fname, cfg["thresholds"]["breakout_days"])
            p_24h = last_prices[-1] if last_prices else price_now
            p_7d  = last_prices[0]  if last_prices else price_now

            append_history_csv(fname, {
                "ts": now_ts(),
                "price_now": price_now,
                "market_now": p_market_now
            }, fieldnames=["ts","price_now","market_now"])

            # --- señales ---
            ok, meta = price_spike_signal(
                {"now": price_now, "24h_ago": p_24h, "7d_ago": p_7d},
                last_prices,
                cfg
            )

            # --- filtros Cardmarket (opcionales) ---
            use_trend = cfg.get("run", {}).get("use_cardmarket_trend", True)
            min_avg7 = cfg["thresholds"].get("min_avg7_usd", 0)
            trend_ok = True
            avg7_ok = True
            if (use_trend or min_avg7 > 0) and entries:
                trend_ok = False
                avg7_ok = False
                for e in entries:
                    cm = (e.get("cardmarket") or {}).get("prices") if isinstance(e, dict) else None
                    if not cm: continue
                    t_ok = (cm.get("avg1",0) >= cm.get("avg7",0) >= cm.get("avg30",0)) if use_trend else True
                    a_ok = (cm.get("avg7",0) >= min_avg7) if min_avg7>0 else True
                    if t_ok and a_ok:
                        trend_ok, avg7_ok = True, True
                        break

            # --- alerta ---
            force_test = os.getenv("FORCE_TEST_ALERT","false").lower() in ("1","true","yes")
            if force_test:
                ok = True
                meta = {"pct_24h": 0.25, "pct_7d": 0.40, "breakout": True}

            if ok and trend_ok and avg7_ok and price_now > 0:
                title = f"📈 Spike: {name}"
                body = (
                    f"Δ24h: {meta['pct_24h']*100:.1f}% | Δ7d: {meta['pct_7d']*100:.1f}% | breakout: {meta['breakout']}\n"
                    f"Ahora: ${price_now:.2f} (PokémonTCG/CM)\n"
                    f"Queries: {', '.join(queries)}"
                )
                if image_url:
                    send_telegram_photo("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", image_url, caption=f"<b>{title}</b>")
                    send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", body)
                else:
                    send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", f"<b>{title}</b>\n{body}")
            else:
                print(f"no alert: ok={ok}, trend_ok={trend_ok}, avg7_ok={avg7_ok}, now=${price_now:.2f}")

        except Exception as e:
            # Nunca abortes toda la corrida por una carta
            print(f"[{item.get('name','?')}] ERROR (continuo con la siguiente):", type(e).__name__, str(e)[:300])
            continue


    # generar panel al final
    from .panel import build_panel
    build_panel()

if __name__ == "__main__":
    main()
