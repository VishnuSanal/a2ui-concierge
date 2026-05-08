# Demo Runbook — Gift Concierge

Tab this open the morning of the demo. The smoke checklist (`docs/smoke-checklist.md`) covers
system health; this covers what to do on stage.

---

## Pre-demo checklist

- [ ] Backend running with API key — `curl http://localhost:8000/health` returns `ok`.
- [ ] Tunnel up (Cloudflare Tunnel or `adb reverse tcp:8000 tcp:8000` for USB).
- [ ] Phone unlocked, plugged in, screen mirroring on (so the audience sees what you tap).
- [ ] Screen recording armed (or laptop OBS configured) — start it before opening the app.
- [ ] Backup screenshots open in another tab (`docs/screenshots/beat-3.png`, `beat-6.png`).

---

## Demo script

| Beat | What you type or do | Why this beat exists |
|------|---------------------|----------------------|
| 1 | Open the app. Type **"Need a gift for my sister — minimalist, under $150"**. Tap send. | Native chrome on display. |
| 2 | Tap the **Jewelry** chip. | Agent reasoning made tangible — reframes a vague request into a focused choice. |
| 3 | Brief silence (~3 s). Pick the **Bar Pendant** card. | The "I see what you mean" moment — three curated picks instead of an infinite scroll. |
| 4 | Pick **Silver / 16"**. Tap **Continue**. | A2UI doing real product configuration, not just text. |
| 5 | Toggle **gift wrap** on. Type **"Happy birthday, sis — love you"**. Pick the **Brooklyn** address. Tap **Place order**. | A native-feeling form inside the chat thread. |
| 6 | Wait for the confirmation card. Subtle haptic confirms. Pause for applause. | The whole flow closed in under 90 seconds. |

---

## If the agent goes off-script

- **"Show me three picks"** — nudges the model to call `present_products`.
- **"Use the chip group"** — coaxes it back to `present_chips` if it tried to ask in plain text.
- **"Place the order"** — short-circuits to `place_order` and `present_confirmation` if a flow stalled.

---

## Recovery moves

- **Agent first-byte > 5 s:** speak the line "Models keep getting better — even this latency is dropping every quarter."
- **WebView blank:** tap and hold the bubble for 1 s; if it doesn't recover in 2 s, switch to the slide screenshots and continue narrating.
- **Network drops:** use the offline screenshots; do NOT try to reconnect on stage.

---

## Hot reload during the talk

- The phone caches the host bundle in the APK. To swap a Lit component live, you'd need to rebuild the APK — don't.
- The agent prompt is editable in `backend/src/concierge/prompts.py` and reloads on the next request — useful for "watch me change the agent's persona" demos.

---

## How to leave

"If you want to play with this yourself, the repo and runbook are linked on the last slide."
