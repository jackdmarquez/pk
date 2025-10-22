import os, time, yaml, datetime as dt
from math import ceil
from statistics import median
from .collectors.pokemontcg import fetch_card_entries
from .signals import price_spike_signal
from .alerting import send_telegram_text, send_telegram_photo
from .utils import slugify, ensure_dir, append_history_csv, load_last_n, now_ts
from .health import write_health

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

    if os.getenv("SEND_PING","false").lower() in ("1","true","yes"):
        send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "🤖 Bot iniciado (healthcheck).")

    MAX_RUNTIME = float(os.getenv("MAX_RUNTIME_SEC", "0"))
    start_time = time.time()
    batch_size = int(os.getenv("WATCH_BATCH_SIZE", "0"))
    full_watch = list(cfg["watchlist"])
    watch = list(full_watch)
    if batch_size and batch_size < len(watch):
        chunks = ceil(len(watch) / batch_size)
        slot = dt.datetime.utcnow().hour % max(chunks, 1)
        start = slot * batch_size
        end = min(len(watch), start + batch_size)
        print(f"[batch] Procesando cartas {start}..{end-1} de {len(watch)}")
        watch = watch[start:end]

    force_test = os.getenv("FORCE_TEST_ALERT","false").lower() in ("1","true","yes")

    stats = {
        "started": now_ts(),
        "duration_sec": 0.0,
        "cards_total": len(full_watch),
        "batch_size": batch_size or len(full_watch),
        "processed": 0,
        "timeouts": 0,
        "net_errors": 0,
        "parse_errors": 0,
        "alerts_sent": 0,
        "items": []
    }

    for item in watch:
        if MAX_RUNTIME and (time.time() - start_time) > MAX_RUNTIME:
            print("[watchdog] Tiempo máximo alcanzado, detengo el loop."); break
        name = item["name"]
        try:
            base_queries = item["queries"]
            min_grade = item.get("min_grade")
            language = item.get("language")
            include_terms = item.get("include_terms", [])
            queries, _ = augment_queries(base_queries, min_grade, language, include_terms)

            print(f"[watch] {name}")
            entries = fetch_card_entries(queries, api_key=pokemontcg_key, max_cards=2)
            print(f"[{name}] entries={{len(entries)}} samples={{[e.get('now') for e in entries][:3]}}")

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
            fname = os.path.join(DATA_DIR, f"{slugify(name)}.csv")
            last_prices = load_last_n(fname, cfg["thresholds"]["breakout_days"])
            p_24h = last_prices[-1] if last_prices else price_now
            p_7d  = last_prices[0]  if last_prices else price_now

            append_history_csv(fname, {"ts": now_ts(), "price_now": price_now, "market_now": p_market_now},
                               fieldnames=["ts","price_now","market_now"])

            ok, meta = price_spike_signal({"now": price_now, "24h_ago": p_24h, "7d_ago": p_7d}, last_prices, cfg)

            trend_ok = True
            avg7_ok = True
            if (use_trend or min_avg7 > 0) and entries:
                trend_ok = False; avg7_ok = False
                for e in entries:
                    cm = (e.get("cardmarket") or {}).get("prices") if isinstance(e, dict) else None
                    if not cm: continue
                    t_ok = (cm.get("avg1",0) >= cm.get("avg7",0) >= cm.get("avg30",0)) if use_trend else True
                    a_ok = (cm.get("avg7",0) >= min_avg7) if min_avg7>0 else True
                    if t_ok and a_ok:
                        trend_ok, avg7_ok = True, True; break

            if force_test:
                ok = True; meta = {"pct_24h": 0.25, "pct_7d": 0.40, "breakout": True}

            alerted = False
            if ok and trend_ok and avg7_ok and price_now > 0:
                title = f"📈 Spike: {name}"
                body = (f"Δ24h: {meta['pct_24h']*100:.1f}% | Δ7d: {meta['pct_7d']*100:.1f}% | breakout: {meta['breakout']}"
                        f"Ahora: ${price_now:.2f} (PokémonTCG/CM)"
                        f"Queries: {', '.join(queries)}")
                if image_url:
                    send_telegram_photo("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", image_url, caption=f"<b>{title}</b>")
                    send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", body)
                else:
                    send_telegram_text("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", f"<b>{title}</b>\n{body}")
                alerted = True; stats["alerts_sent"] += 1
            else:
                print(f"no alert: ok={ok}, trend_ok={trend_ok}, avg7_ok={avg7_ok}, now=${price_now:.2f}")

            stats["processed"] += 1
            stats["items"].append({
                "name": name,
                "entries": len(entries),
                "price_now": float(price_now or 0),
                "pct_24h": float(meta.get("pct_24h",0)) if isinstance(meta, dict) else 0.0,
                "pct_7d": float(meta.get("pct_7d",0)) if isinstance(meta, dict) else 0.0,
                "breakout": bool(meta.get("breakout", False)) if isinstance(meta, dict) else False,
                "alerted": alerted,
                "note": "" if price_now else "sin precio"
            })

        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:200]}"
            stats["processed"] += 1
            if "Timeout" in msg or "Read timed out" in msg:
                stats["timeouts"] += 1
            elif "network" in msg.lower() or "connection" in msg.lower():
                stats["net_errors"] += 1
            elif "parse" in msg.lower() or "JSONDecodeError" in msg:
                stats["parse_errors"] += 1
            stats["items"].append({
                "name": name,
                "entries": 0,
                "price_now": 0.0,
                "pct_24h": 0.0,
                "pct_7d": 0.0,
                "breakout": False,
                "alerted": False,
                "note": msg
            })
            print(f"[{name}] ERROR (continuo con la siguiente):", msg); continue

    stats["duration_sec"] = round(time.time() - start_time, 3)
    write_health(stats)

if __name__ == "__main__":
    main()
