# A2UI v0.8 Wire Shapes — Lumen Concierge

This project speaks the **A2UI v0.8** protocol. Every agent bubble is a
self-contained A2UI **surface**, transmitted as a `surfaceUpdate` followed
by a `beginRendering` and (when the user closes a transient sheet) a
`deleteSurface`. Each agent bubble carries a single root component drawn
from the project's custom catalog `lumen.com:concierge/v1`.

**Source consulted:**
- `https://a2ui.org/specification/v0.8-a2ui` — spec overview
- `https://raw.githubusercontent.com/google/A2UI/main/specification/v0_8/json/server_to_client.json`
- `https://raw.githubusercontent.com/google/A2UI/main/specification/v0_8/json/client_to_server.json`
- `https://raw.githubusercontent.com/google/A2UI/main/specification/v0_8/json/standard_catalog_definition.json`
- `https://raw.githubusercontent.com/google/A2UI/main/specification/v0_8/json/catalog_description_schema.json`

---

## 1. Envelope (server → client)

Every A2UI message follows the v0.8 server-to-client schema and contains
exactly one of `surfaceUpdate`, `dataModelUpdate`, `beginRendering`, or
`deleteSurface`. Each `/chat` SSE `event: a2ui` frame carries one such
message — one A2UI message per line, matching the spec's JSONL guidance.

A typical agent bubble emits **two messages** back-to-back: a
`surfaceUpdate` containing the root component, then a `beginRendering`
pointing at it.

```jsonl
{"surfaceUpdate":{"surfaceId":"s-1d2c3b","components":[
  {"id":"c-9f8e7d","component":{"ChipGroup":{ /* props */ }}}
]}}
{"beginRendering":{"surfaceId":"s-1d2c3b","root":"c-9f8e7d",
                    "catalogId":"lumen.com:concierge/v1"}}
```

Properties such as `question`, `label`, `reasoning`, `txHash`, `shipDate`
are **BoundValue** objects per spec: `{"literalString": "..."}` for
literals or `{"path": "/order/total"}` for data-model references. Arrays
inside our custom-catalog components (options, items, fields,
variantGroups) are inline — the v0.8
`catalog_description_schema.json` lets a custom catalog define its own
property shapes.

Producer: `backend/src/concierge/a2ui.py` (`chips()`, `products()`,
`product_detail()`, `form()`, `confirmation()`, `payment_challenge()`,
`tx_detail()`). Each returns `list[dict]` — a (surfaceUpdate,
beginRendering) pair.

Consumers:
- `host-bundle/src/shim.js` (Android WebView host) — `window.a2ui.ingest(msg)`
  dispatches by message type, buffers `surfaceUpdate`/`dataModelUpdate`
  per `surfaceId`, mounts the root on `beginRendering`, and resolves
  BoundValues against the surface's data model before assigning props.
- `host-bundle/index.html` (web app) — identical interpreter, mounted
  into per-bubble chat rows instead of a single `#a2ui-root`.

## 2. Catalog: `lumen.com:concierge/v1`

The custom catalog defines seven composite commerce components. They are
not part of the v0.8 standard catalog — the standard catalog primitives
(Text/Image/Row/Column/Card/...) are recognised in the interpreter but
unused by the demo, which renders rich purpose-built widgets directly.

| Component         | Standard-catalog peers (informative) |
|-------------------|----------------------------------------|
| `ChipGroup`       | `MultipleChoice` (variant: chips, maxAllowedSelections: 1) |
| `CardGrid`        | none — would require `List` + `Card` + `Column` + `Image` + `Text` |
| `ProductDetail`   | partial: `MultipleChoice` per variant group, `Image` for gallery |
| `ConciergeForm`   | `CheckBox` (toggle), `TextField` (text + address fallback) |
| `ConfirmationCard`| none — would require `Card` + `Column` + `Text` + `Divider` |
| `PaymentChallenge`| none — bespoke payment sheet (DPC + x402) |
| `TxDetail`        | none — bespoke tx-receipt sheet |

### 2.1 ChipGroup

```json
{"ChipGroup": {
  "question": {"literalString": "What does she lean toward?"},
  "options": [
    {"value": "jewelry",    "label": {"literalString": "Jewelry"}},
    {"value": "home",       "label": {"literalString": "Home"}},
    {"value": "stationery", "label": {"literalString": "Stationery"}},
    {"value": "skincare",   "label": {"literalString": "Skincare"}}
  ],
  "selections": {"literalArray": []},
  "maxAllowedSelections": 1,
  "variant": "chips",
  "action": {"name": "chip-group"}
}}
```

Mirrors the standard-catalog `MultipleChoice` shape exactly for
`options`, `selections`, `maxAllowedSelections`, and `variant`; adds a
`question` BoundString and a single `action` for the selection event.

### 2.2 CardGrid

```json
{"CardGrid": {
  "section":   {"literalString": "Quietly Romantic"},
  "reasoning": {"literalString": "Three minimalist picks…"},
  "items": [
    {"id": "bar-pendant", "name": "Bar Pendant", "price": 124,
     "salePrice": null, "vendor": "Lumen Goods",
     "imageUrl": "https://…", "why": "Clean horizontal bar…"}
  ],
  "action": {"name": "card-grid"}
}}
```

`items[]` is inline (custom-catalog escape hatch); field names follow the
standard-catalog camelCase convention (`imageUrl`, `salePrice`).

### 2.3 ProductDetail

```json
{"ProductDetail": {
  "product": {
    "id": "bar-pendant", "name": "Bar Pendant", "price": 124,
    "salePrice": null, "vendor": "Lumen Goods", "inStock": true,
    "imageUrl": "https://…", "images": ["https://…"],
    "description": "…"
  },
  "variantGroups": [
    {"name": "finish", "options": ["gold", "silver"], "select": "single"},
    {"name": "length", "options": ["16\"", "18\""], "select": "single"}
  ],
  "requiresAgeVerification": {"literalBoolean": false},
  "action": {"name": "product-detail"}
}}
```

### 2.4 ConciergeForm

```json
{"ConciergeForm": {
  "fields": [
    {"type": "toggle",  "name": "gift_wrap", "label": {"literalString": "Gift wrap (+$8)"}},
    {"type": "text",    "name": "note",      "label": {"literalString": "Gift note"}, "maxLength": 120},
    {"type": "address", "name": "ship_to",   "label": {"literalString": "Ship to"}}
  ],
  "action": {"name": "form"}
}}
```

Field types `toggle` and `text` correspond to the standard-catalog
`CheckBox` and `TextField`; `address` is a custom field that the Lit
component renders as a saved-address pill picker. `maxLength` is
camelCased per standard-catalog convention.

### 2.5 ConfirmationCard

```json
{"ConfirmationCard": {
  "orderId": "A2UI-7741",
  "items": [
    {"label": "Bar Pendant · Silver · 16\"", "amount": 124},
    {"label": "Gift wrap", "amount": 8}
  ],
  "total": 132,
  "shipDate": {"literalString": "Mon, May 11"},
  "txHash": {"literalString": "0xab…"},
  "explorerUrl": {"literalString": "https://sepolia.basescan.org/tx/0xab…"},
  "action": {"name": "confirmation-card"}
}}
```

### 2.6 PaymentChallenge

```json
{"PaymentChallenge": {
  "orderId": "A2UI-7741",
  "label":   {"literalString": "Lumen Goods — Bar Pendant"},
  "amountDisplay": {"literalString": "$132.00"},
  "items":   [ /* line items */ ],
  "challenge": { /* unsigned EIP-3009 challenge */ },
  "requiresAgeVerification": {"literalBoolean": true},
  "ageDcqlQueryJson":     {"literalString": "{...}"},
  "dpcDcqlQueryJson":     {"literalString": "{...}"},
  "loyaltyDiscountPct":   10,
  "loyaltyDcqlQueryJson": {"literalString": "{...}"},
  "action": {"name": "payment-challenge"}
}}
```

`challenge` is treated as an opaque object (the Android side reads
EIP-3009 fields from it). DCQL query JSON is shipped as a literal string
so the Android Credential Manager call doesn't double-encode it.

### 2.7 TxDetail

```json
{"TxDetail": {
  "orderId": "A2UI-7741",
  "txHash":      {"literalString": "0xab…"},
  "explorerUrl": {"literalString": "https://…"},
  "network":     {"literalString": "base-sepolia"},
  "amountDisplay": {"literalString": "$132.00"},
  "total":     132,
  "items":     [ /* line items */ ],
  "shipDate":  {"literalString": "Mon, May 11"},
  "payTo":     {"literalString": "0x…"}
}}
```

The TxDetail surface is synthesised client-side (no network round trip)
when the user taps the "view tx" row on a confirmation card — the
Android `ChatViewModel.buildTxDetailSurface()` builds a fresh
`(surfaceUpdate, beginRendering)` pair and feeds it to the same
WebView interpreter.

## 3. Client → server: `userAction` envelope

User interactions inside a bubble bubble up as `a2ui-action`
`CustomEvent`s; the shim wraps each into the v0.8 client-to-server
`userAction` envelope (see `client_to_server.json`):

```json
{"userAction": {
  "name": "chip-group",
  "surfaceId": "s-1d2c3b",
  "sourceComponentId": "c-9f8e7d",
  "timestamp": "2026-05-20T18:42:11.043Z",
  "context": {"value": "jewelry"}
}}
```

Both the Android `ChatViewModel.extractUserAction()` and the web
`handleUserAction()` translate this envelope into the legacy
`[ui-action] {component: "<name>", ...context}` string the agent's
prompts (`backend/src/concierge/prompts.py`) still consume. The
translation is a thin compatibility shim — the wire format is fully
v0.8.

Pure UI dismissals (`*-close`) are intercepted at the bridge and never
sent to the agent.

## 4. Data binding and the BoundValue resolver

The shim's `resolveValue` walks each component's props and substitutes:

| Shape                                | Resolves to                |
|--------------------------------------|----------------------------|
| `{"literalString": "x"}`             | the string `"x"`           |
| `{"literalNumber": 1}`               | the number `1`             |
| `{"literalBoolean": true}`           | `true`                     |
| `{"literalArray": ["a", "b"]}`       | the array                  |
| `{"path": "/cart/total"}`            | `surface.dataModel.cart.total` |

Nested objects and arrays are walked recursively so option arrays of
`{value, label: {literalString}}` come out as `{value, label: "..."}`
before the prop is assigned to the custom-element.

`dataModelUpdate` messages patch the surface's data model and re-render
any bound props; the demo currently emits a fresh surface per turn, so
this path is exercised only when a future flow needs incremental updates
(e.g. live price ticks).

## 5. Lifecycle summary

```
agent.turn() yields AgentEvent("a2ui", msg)
    │  one v0.8 message per yield
    ▼
app.py    → SSE event: a2ui  data: <single v0.8 message>
    │
    ├─→ Android: SseClient → ChatViewModel.handleA2uiMessage
    │     • buffer surfaceUpdate frames by surfaceId
    │     • commit a chat bubble (or open a modal sheet) on beginRendering
    │     • AgentA2uiBubble replays the frame list through
    │       window.a2ui.ingest()
    │
    └─→ Web: SSE parser in index.html
          • ingest() → mountSurfaceBubble() on beginRendering
          • a2ui-action listener wraps interactions into userAction
            envelopes, translates to legacy [ui-action] payloads, then
            POSTs the next /chat turn
```

When adding a new component, you must:
1. Add a builder to `backend/src/concierge/a2ui.py` that returns a
   `(surfaceUpdate, beginRendering)` pair with the new component type.
2. Register the component type in `COMPONENT_TAG` in both
   `host-bundle/src/shim.js` and `host-bundle/index.html`.
3. Author a Lit element under `host-bundle/src/components/` that fires
   `a2ui-action` events for any user interactions.
4. Add a fixture under `backend/tests/fixtures/` and an entry in this
   document with the component's prop schema.
