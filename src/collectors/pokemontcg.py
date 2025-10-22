# src/collectors/pokemontcg.py
import requests

API_URL = "https://api.pokemontcg.io/v2/cards"

def fetch_card_entries(queries, api_key=None, max_cards=2):
    headers = {"X-Api-Key": api_key} if api_key else {}
    results = []
    for q in queries:
        params = {"q": f'name:"{q}"'} if 'name:' not in q else {"q": q}
        try:
            r = requests.get(API_URL, headers=headers, params=params, timeout=20)
            r.raise_for_status()
            data = r.json().get("data", [])[:max_cards]
        except Exception:
            data = []
        for card in data:
            entry = {"name": card.get("name"), "set": (card.get("set") or {}).get("name")}
            p_now = None
            tp = (card.get("tcgplayer") or {}).get("prices") or {}
            cm = (card.get("cardmarket") or {}).get("prices") or {}
            for k in ["holofoil", "reverseHolofoil", "normal", "ultraRare", "1stEditionHolofoil"]:
                if k in tp and "market" in tp[k]:
                    p_now = tp[k]["market"]
                    break
            if p_now is None:
                for k in ["avg1", "avg7", "avg30"]:
                    if k in cm:
                        p_now = cm[k]
                        break
            entry["now"] = float(p_now) if p_now is not None else None
            entry["cardmarket"] = {"prices": cm} if cm else {}
            images = card.get("images") or {}
            entry["image_small"] = images.get("small")
            entry["image_large"] = images.get("large")
            results.append(entry)
    return results
