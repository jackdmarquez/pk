# src/collectors/pokemontcg.py
import re, requests

API_URL = "https://api.pokemontcg.io/v2/cards"

SET_HINTS = [
    "Evolving Skies", "Fusion Strike", "Lost Origin", "Silver Tempest",
    "Scarlet & Violet 151", "Scarlet Violet 151", "Team Up",
    "Base Set", "Neo Genesis", "EX Deoxys", "Champion's Path"
]

def _extract_number(qstr):
    m = re.search(r'\b(\d{1,3}/\d{1,3})\b', qstr)
    return m.group(1) if m else None

def _extract_set(qstr):
    # busca la primera coincidencia de set por “hint”
    for s in SET_HINTS:
        if s.lower() in qstr.lower():
            return s
    return None

def _extract_main_name(qstr):
    # primer token con mayúscula al inicio suele ser el nombre (Umbreon, Rayquaza…)
    # si contiene &, devuelve la primera parte
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
    # por si el usuario ya pasó una q válida:
    if 'name:' in user_q or 'set.name:' in user_q or 'number:' in user_q:
        candidates.insert(0, user_q)
    # dedup conservando orden
    seen, out = set(), []
    for c in candidates:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def fetch_card_entries(queries, api_key=None, max_cards=2):
    headers = {"X-Api-Key": api_key} if api_key else {}
    results = []
    for raw_q in queries:
        for q in _build_candidate_queries(raw_q):
            params = {"q": q}
            r = requests.get(API_URL, headers=headers, params=params, timeout=20)
            print("[pokemontcg] q=", q, "status=", r.status_code)
            try:
                r.raise_for_status()
            except Exception:
                print("[pokemontcg] error body:", r.text[:800])
                continue
            data = r.json().get("data", [])[:max_cards]
            if not data:
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
                # imágenes
                images = card.get("images") or {}
                entry["image_small"] = images.get("small")
                entry["image_large"] = images.get("large")
                results.append(entry)
            # si ya conseguimos algo con esta query, no hace falta probar las siguientes variantes
            if results:
                break
    return results
