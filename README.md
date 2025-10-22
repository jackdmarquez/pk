# Pokémon-only Spike Bot — Telegram + Panel (sin eBay)

Monitorea **spikes de precio** usando **PokémonTCG API** (TCGplayer/Cardmarket) y envía **alertas por Telegram** (foto + texto). Incluye **panel HTML + CSV** en `/docs` y **auto-commit** tras cada corrida para actualizar **GitHub Pages**.

## 🔑 Secrets requeridos (GitHub → Settings → Secrets and variables → Actions)
- `TELEGRAM_BOT_TOKEN` — Token del bot creado con **@BotFather**.
- `TELEGRAM_CHAT_ID` — ID de tu chat/usuario/grupo destino.
- `POKEMONTCG_API_KEY` — *(opcional, recomendado)* para mayor cuota de la API.

## ▶️ Cómo usar
1. Sube este repo a tu GitHub.
2. Crea los **Secrets** anteriores.
3. Ve a **Actions** → ejecuta **price-spike-bot** o espera el cron (cada 15 min).
4. Activa **GitHub Pages** (Settings → Pages → *Deploy from a branch* → tu rama, carpeta **/docs**).

## ⚙️ Señales
- Alerta cuando: **Δ% 24h ≥ umbral**, **Δ% 7d ≥ umbral**, y **breakout** vs. máximo de `breakout_days`.
- Opcional: filtro de **tendencia Cardmarket** (`avg1 ≥ avg7 ≥ avg30`) y mínimo `avg7` en USD.

## ⚠️ Notas
- Sin eBay: no hay inventario/asks ni vendidos. Se prioriza el **market** de TCGplayer; si falta, se usa **Cardmarket avg1/avg7/avg30**.
- Usa umbrales conservadores si ves ruido.
