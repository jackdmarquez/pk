# src/collectors/pokemontcg.py
import os, re, time, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api.pokemontcg.io/v2/cards"

SET_HINTS = [
    "Evolving Skies", "Fusion Strike", "Lost Origin", "Silver Tempest",
    "Scarlet & Violet 151", "Scarlet Violet 151", "Team Up",
    "Base Set", "Neo Genesis", "EX Deoxys", "Champion's Path", "Champions Path"
]

def _extract_number(qstr):
    m = re.search(r'\b(\d{1,3}/\d{1,3})\b', qstr)
    return m.group(1) if m else None

def _extract_set(qstr):
    for s in SET_HINTS:
        if s.lower() in qstr.lower():
            return s
    return None

def _extract_main_name(qstr):
    m = re.search(r'\b([A-Z][a-zA-Z]*)\b', qstr)
    if m:
        return m.group(1)
    return qstr.split()[0] if qstr.split() else qstr

def _build_candidate_queries(user_q):
    user_q = user_q.strip()
    number = _extract_number(user_q)
    set_name = _extract_set(user_q)
    main = _extract_main_name(user_q)

    candidates = []
    if number and set_name:
        candidates.append(f'number:"{number}" AND set.name:"{set_name}"')
    if set_name and main:
        candidates.append(f'name:"{main}" AND set.name:"{set_name}"')
    if main:
        candidates.append(f'name:"{main}"')
    if 'name:' in user_q or 'set.name:' in user_q or 'number:' in user_q:
        candidates.insert(0, user_q)

    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def _session():
    # Configurables por env
    total = int(os.getenv("POKEMONTCG_RETRIES", "3"))
    backoff = float(os.getenv("POKEMONTCG_BACKOFF", "1.5"))
    status_forcelist = [429, 500, 502, 503, 504]

    retry = Retry(
        total=total,
        read=total,
        connect=total,
        status=total,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def fetch_card_entries(queries, api_key=None, max_cards=2):
    headers = {"X-Api-Key": api_key} if api_key else {}
    timeout = float(os.getenv("POKEMONTCG_TIMEOUT", "30"))  # ↑ de 20 a 30
    throttle = float(os.getenv("POKEMONTCG_THROTTLE", "0.4"))  # pausa entre requests
    sess = _session()

    results = []
    for raw_q in queries:
        for q in _build_candidate_queries(raw_q):
            params = {"q": q}
            try:
                r = sess.get(API_URL, headers=headers, params=params, timeout=timeout)
                print("[pokemontcg] q=", q, "status=", r.status_code)
                r.raise_for_status()
                data = r.json().get("data", [])[:max_cards]
            except requests.exceptions.RequestException as e:
                print("[pokemontcg] network error:", type(e).__name__, str(e)[:200])
                # seguimos con el próximo intento / query
                time.sleep(throttle)
                continue
            except ValueError as e:
                print("[pokemontcg] parse error:", str(e)[:200])
                time.sleep(throttle)
                continue

            if not data:
                time.sleep(throttle)
                continue

            for card in data:
                entry = {"name": card.get("name"), "set": (card.get("set") or {}).get("name")}
                # precios
                p_now = None
                tp = (card.get("tcgplayer") or {}).get("prices") or {}
                cm = (card.get("cardmarket") or {}).get("prices") or {}
                for k in ["holofoil", "reverseHolofoil", "normal", "ultraRare", "1stEditionHolofoil"]:
                    if k in tp and "market" in tp[k]:
                        p_now = tp[k]["market"]; break
                if p_now is None:
                    for k in ["avg1", "avg7", "avg30"]:
                        if k in cm:
                            p_now = cm[k]; break
                entry["now"] = float(p_now) if p_now is not None else None
                entry["cardmarket"] = {"prices": cm} if cm else {}
                images = card.get("images") or {}
                entry["image_small"] = images.get("small")
                entry["image_large"] = images.get("large")
                results.append(entry)

            # si encontró algo, no probamos más variantes de esa query base
            if results:
                time.sleep(throttle)
                break

            time.sleep(throttle)
    return results
