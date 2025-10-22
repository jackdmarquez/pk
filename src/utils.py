# src/utils.py
import os, csv, re, datetime as dt
from typing import List, Dict, Any

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def now_ts() -> str:
    return dt.datetime.utcnow().isoformat()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def append_history_csv(path: str, row: Dict[str, Any], fieldnames: List[str]):
    file_exists = os.path.exists(path)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def load_last_n(path: str, n_days: int) -> list:
    if not os.path.exists(path):
        return []
    rows = []
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=n_days)).isoformat()
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get('ts','') >= cutoff:
                try:
                    rows.append(float(r.get('price_now', '0') or 0))
                except:
                    pass
    return rows[-1000:]
