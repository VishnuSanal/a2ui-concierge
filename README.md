# A2UI Android — Gift Concierge Demo

A native Android app that renders agent-driven UIs using the **A2UI** protocol, delivering a
90-second "Gift Concierge" shopping demo. There is no established Android-native A2UI renderer
today; this project closes that gap pragmatically by hosting the upstream Lit components inside
an embedded WebView, wrapped by a native Jetpack Compose chat shell — a hybrid that ships fast,
feels native where it matters, and provides a credible migration path to a fully-native Compose
renderer later. It is a high-fidelity prototype, not a production app.

## Architecture

```
[Android device — Kotlin / Jetpack Compose]
  ChatScreen (Compose)
    ├── TopAppBar, theme, scaffolding             ← Compose
    ├── MessageList (LazyColumn)                  ← Compose
    │     ├── UserBubble                          ← Compose
    │     ├── AgentTextBubble                     ← Compose (Markdown)
    │     └── AgentA2uiBubble                     ← AndroidView { WebView } hosting Lit components
    └── InputRow (text field + send)              ← Compose
            │
            ▼ HTTPS POST /chat (SSE response)
[Agent backend — Python / FastAPI]
  /chat        — accepts user message, streams A2UI fragments back
  GiftAgent    — Claude Sonnet 4.6 (Anthropic SDK) with shopping tools
    Tools: search_catalog, get_product, place_order, present_*  
  catalog.json — curated mock product catalog (~30 items)
```

## Repository layout

```
a2ui-android/
├── backend/        # Python / FastAPI agent (uv-managed)
├── host-bundle/    # Vite build that produces the bundled Lit JS for Android assets
└── app/            # Android Studio project (Kotlin / Jetpack Compose)
```

## Quickstart

**1. Backend** — export `ANTHROPIC_API_KEY` first, then:

```shell
cd backend && uv sync --all-extras && uv run uvicorn concierge.app:app --port 8000
```

**2. Host bundle** — writes the host JS into Android assets:

```shell
cd host-bundle && npm install && npm run build:android
```

**3. Android** — install and launch:

```shell
cd app && ./gradlew :app:installDebug && adb shell am start -n com.diegoz.a2uiconcierge/.MainActivity
```

The emulator reaches the backend at `10.0.2.2:8000` (host loopback). For a physical phone,
run `adb reverse tcp:8000 tcp:8000` instead.

## Pointers

- Spec: `docs/superpowers/specs/2026-05-07-a2ui-android-shopping-demo-design.md`
- Plan: `docs/superpowers/plans/2026-05-07-a2ui-android-shopping-demo.md`
- A2UI shapes ref: `docs/a2ui-shapes.md`
- Smoke checklist: `docs/smoke-checklist.md`
- Runbook (tab this open before a demo): `docs/runbook.md`

## Status

Demo prototype. Not for production. See spec §3 for non-goals.
