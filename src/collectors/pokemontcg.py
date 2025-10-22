import os, re, time, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
API_URL = "https://api.pokemontcg.io/v2/cards"
# ...
# No olvides que _session() ya está definido; lo mantenemos igual.

SET_HINTS = [
    "Evolving Skies", "Fusion Strike", "Lost Origin", "Silver Tempest",
    "Scarlet & Violet 151", "Scarlet Violet 151", "Team Up",
    "Base Set", "Neo Genesis", "EX Deoxys", "Champion's Path", "Champions Path"
]
GENERIC_TOKENS = {"pokemon","tcg","card","cards","alternate","alt","art","alternateart",
                  "special","illustration","promo","ex","v","vmax","gx","sv","sv151",
                  "sws","swsh","champion","champions","path","team","up","neo","base","set"}
def _extract_number(qstr):
    m = re.search(r'\b(\d{1,3}/\d{1,3})\b', qstr)
    return m.group(1) if m else None
def _extract_set(qstr):
    for s in SET_HINTS:
        if s.lower() in qstr.lower():
            return s
    return None
def _extract_main_name(qstr: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9&/\-\' ]+', ' ', qstr)
    tokens = [t for t in cleaned.split() if t]
    filtered = []
    for t in tokens:
        tl = t.lower()
        if tl in GENERIC_TOKENS: 
            continue
        if tl == "pokemon": 
            continue
        filtered.append(t)
    for t in filtered:
        if re.match(r'^[A-Z][a-zA-Z0-9\'-]*$', t):
            return t
    return filtered[0] if filtered else (tokens[0] if tokens else qstr)
def _build_candidate_queries(user_q: str):
    user_q = user_q.strip()
    number = _extract_number(user_q)
    set_name = _extract_set(user_q)
    main = _extract_main_name(user_q)

    candidates = []

    # 1) Si tenemos número + set, es la más precisa
    if number and set_name:
        candidates.append(f'number:"{number}" set.name:"{set_name}"')

    # 2) name+set con comillas
    if set_name and main:
        candidates.append(f'name:"{main}" set.name:"{set_name}"')

    # 3) name+set SIN comillas (algunos edges responden mejor)
    if set_name and main:
        candidates.append(f'name:{main} set.name:"{set_name}"')

    # 4) name wildcard (tolerante a sufix/prefix)
    if main:
        candidates.append(f'name:{main}*')

    # 5) name simple citado
    if main:
        candidates.append(f'name:"{main}"')

    # 6) Query “raw” si ya venía formateada por el usuario
    if 'name:' in user_q or 'set.name:' in user_q or 'number:' in user_q:
        candidates.insert(0, user_q)

    # dedup + límite
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            out.append(c); seen.add(c)
    max_variants = int(os.getenv("MAX_QUERY_VARIANTS", "5"))
    return out[:max_variants]

def _session():
    total = int(os.getenv("POKEMONTCG_RETRIES", "2"))
    backoff = float(os.getenv("POKEMONTCG_BACKOFF", "1.0"))
    status_forcelist = [429, 500, 502, 503, 504]
    retry = Retry(total=total, read=total, connect=total, status=total,
                  backoff_factor=backoff, status_forcelist=status_forcelist,
                  allowed_methods=frozenset(["GET"]), raise_on_status=False)
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def fetch_card_entries(queries, api_key=None, max_cards=2):
    headers = {
        "Accept": "application/json",
        "User-Agent": "pk-spike-bot/1.1 (+github-actions)"
    }
    if api_key:
        headers["X-Api-Key"] = api_key
    else:
        print("[pokemontcg] WARN: no API key provided (X-Api-Key missing)")

    timeout  = float(os.getenv("POKEMONTCG_TIMEOUT", "20"))
    throttle = float(os.getenv("POKEMONTCG_THROTTLE", "0.50"))
    sess = _session()

    results = []
    for raw_q in queries:
        for q in _build_candidate_queries(raw_q):
            params = {"q": q}
            try:
                r = sess.get(API_URL, headers=headers, params=params, timeout=timeout)
                print("[pokemontcg] q=", q, "status=", r.status_code)

                # Algunos edges devuelven 404 “suave” en búsquedas válidas;
                # lo tratamos como "sin resultados" y probamos la siguiente variante.
                if r.status_code == 404:
                    print("[pokemontcg] WARN: 404 recibido (edge). Probando siguiente variante…")
                    time.sleep(throttle)
                    continue

                r.raise_for_status()
                payload = r.json()
                data = (payload.get("data") or [])[:max_cards]

            except requests.exceptions.ReadTimeout as e:
                print("[pokemontcg] timeout:", str(e)[:200])
                time.sleep(throttle * 2)
                continue
            except requests.exceptions.ConnectionError as e:
                print("[pokemontcg] connection error:", str(e)[:200])
                # Reset de sesión por si hay socket en mal estado
                sess.close(); sess = _session()
                time.sleep(throttle * 2)
                continue
            except requests.exceptions.RequestException as e:
                print("[pokemontcg] network error:", type(e).__name__, str(e)[:200])
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
                entry = {
                    "name": card.get("name"),
                    "set": (card.get("set") or {}).get("name")
                }
                p_now = None
                tp = (card.get("tcgplayer") or {}).get("prices") or {}
                cm = (card.get("cardmarket") or {}).get("prices") or {}

                for k in ["holofoil", "reverseHolofoil", "normal", "ultraRare", "1stEditionHolofoil"]:
                    if k in tp and "market" in tp[k]:
                        p_now = tp[k]["market"]; break

                if p_now is None:
                    for k in ["avg1","avg7","avg30"]:
                        if k in cm:
                            p_now = cm[k]; break

                entry["now"] = float(p_now) if p_now is not None else None
                entry["cardmarket"] = {"prices": cm} if cm else {}
                images = card.get("images") or {}
                entry["image_small"] = images.get("small")
                entry["image_large"] = images.get("large")
                results.append(entry)

            if results:
                time.sleep(throttle)
                break  # no sigas variantes si ya obtuviste algo

            time.sleep(throttle)

    return results


