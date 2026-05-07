# A2UI Android — Gift Concierge Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a 90-second "Gift Concierge" shopping demo on a native Android phone that renders agent-driven UI through an A2UI hybrid architecture.

**Architecture:** Three deployables — a Python/FastAPI agent backend (Claude Sonnet 4.6 with shopping tools that emit A2UI JSON over SSE), a built JavaScript host bundle (upstream A2UI Lit components + a thin shim with a JS↔native bridge), and a Jetpack Compose Android app that owns the chat shell and embeds a per-message WebView for A2UI bubbles.

**Tech Stack:** Python 3.12 · FastAPI · `sse-starlette` · Anthropic SDK (`claude-sonnet-4-6`) · `pytest` · Vite · Lit (upstream A2UI components) · Kotlin · Jetpack Compose · Material 3 · OkHttp · `compose-markdown` · JUnit/Robolectric.

**Spec:** [`docs/superpowers/specs/2026-05-07-a2ui-android-shopping-demo-design.md`](../specs/2026-05-07-a2ui-android-shopping-demo-design.md)

---

## Repository layout

The plan creates this layout. Path references in tasks below are relative to the repo root `/Users/diegozuluaga/tools/git/a2ui-android`.

```
a2ui-android/
├── backend/                          # Python FastAPI agent
│   ├── pyproject.toml
│   ├── src/concierge/
│   │   ├── __init__.py
│   │   ├── app.py                    # FastAPI app + /chat SSE
│   │   ├── agent.py                  # Claude agent loop
│   │   ├── catalog.py                # catalog loader/search
│   │   ├── catalog.json              # mock product data
│   │   ├── a2ui.py                   # A2UI JSON serializers
│   │   ├── tools.py                  # tool definitions
│   │   └── prompts.py                # system prompt
│   └── tests/
│       ├── test_catalog.py
│       ├── test_a2ui.py
│       ├── test_tools.py
│       └── test_app.py
├── host-bundle/                      # JS host shim + Lit components
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html                    # browser dev playground
│   └── src/
│       ├── shim.js                   # window.a2ui + AndroidBridge
│       ├── theme.css                 # CSS custom property contract
│       └── components/               # local Lit fallbacks if upstream gaps
├── app/                              # Android app (Gradle KTS)
│   ├── build.gradle.kts
│   ├── settings.gradle.kts
│   ├── gradle.properties
│   └── app/src/main/
│       ├── AndroidManifest.xml
│       ├── kotlin/com/diegoz/a2uiconcierge/
│       │   ├── MainActivity.kt
│       │   ├── ui/
│       │   │   ├── ChatScreen.kt
│       │   │   ├── ChatViewModel.kt
│       │   │   ├── UserBubble.kt
│       │   │   ├── AgentTextBubble.kt
│       │   │   ├── AgentA2uiBubble.kt
│       │   │   └── InputRow.kt
│       │   ├── theme/
│       │   │   ├── Theme.kt
│       │   │   ├── Color.kt
│       │   │   └── Type.kt
│       │   ├── chat/
│       │   │   ├── Message.kt
│       │   │   ├── ChatRepository.kt
│       │   │   └── SseClient.kt
│       │   └── a2ui/
│       │       ├── A2uiBridge.kt
│       │       └── ThemeTokens.kt
│       └── assets/
│           ├── host.html
│           └── a2ui-host.js          # built artifact from host-bundle
└── docs/
    ├── superpowers/specs/...
    ├── superpowers/plans/...
    └── runbook.md                    # printable demo runbook (Task E1)
```

## Phase A — Backend

### Task A1: Backend scaffold + hello-world

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/concierge/__init__.py`
- Create: `backend/src/concierge/app.py`
- Create: `backend/tests/test_app.py`
- Create: `backend/.python-version`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[project]
name = "concierge"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "sse-starlette>=2.1",
  "uvicorn[standard]>=0.30",
  "anthropic>=0.40",
  "pydantic>=2.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "httpx>=0.27", "pytest-asyncio>=0.24"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/concierge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 2: Create the package directory**

```bash
mkdir -p backend/src/concierge backend/tests
echo "3.12" > backend/.python-version
touch backend/src/concierge/__init__.py
```

- [ ] **Step 3: Write the failing health-check test**

`backend/tests/test_app.py`:

```python
from fastapi.testclient import TestClient
from concierge.app import app

def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 4: Run the test and confirm it fails**

```bash
cd backend && uv sync --all-extras && uv run pytest tests/test_app.py::test_health -v
```

Expected: `ModuleNotFoundError: No module named 'concierge.app'`.

- [ ] **Step 5: Write minimal `app.py` to pass**

`backend/src/concierge/app.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="A2UI Gift Concierge")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run the test and confirm pass**

```bash
cd backend && uv run pytest tests/test_app.py -v
```

Expected: `test_health PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "Scaffold FastAPI backend with health endpoint"
```

---

### Task A2: A2UI JSON shape discovery and fixtures

This task is research-flavored: capture the exact A2UI JSON shapes for the five surfaces the demo needs, store them as fixtures, and use them as the reference for serializers in Task A4.

**Files:**
- Create: `backend/tests/fixtures/a2ui_chips.json`
- Create: `backend/tests/fixtures/a2ui_products.json`
- Create: `backend/tests/fixtures/a2ui_product_detail.json`
- Create: `backend/tests/fixtures/a2ui_form.json`
- Create: `backend/tests/fixtures/a2ui_confirmation.json`
- Create: `docs/a2ui-shapes.md`

- [ ] **Step 1: Read the upstream A2UI v0.8 spec**

Open in a browser: `https://github.com/google/A2UI/tree/main/docs/specification/v0.8` and `https://github.com/google/A2UI/tree/main/docs/reference/components`. Identify the JSON for: single-select chip group, card grid (image + title + price), product detail with radio variant pickers, form with text input + toggle + address field, confirmation card with summary list.

- [ ] **Step 2: Document each shape**

`docs/a2ui-shapes.md` (one section per surface). Each section: brief description, an annotated JSON example, and any unknowns/gaps. If a needed surface is missing from v0.8, note that and pick the closest existing component to extend in `host-bundle/src/components/`.

- [ ] **Step 3: Save canonical fixtures**

Save one realistic instance per surface, hand-edited to match the storyboard, into `backend/tests/fixtures/a2ui_*.json`. These become both test fixtures and the source of truth for the serializers in Task A4.

- [ ] **Step 4: Verify fixtures load as JSON**

```bash
cd backend && uv run python -c "import json,glob; [json.load(open(p)) for p in glob.glob('tests/fixtures/a2ui_*.json')]; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/fixtures docs/a2ui-shapes.md
git commit -m "Capture A2UI v0.8 JSON shapes for the five demo surfaces"
```

---

### Task A3: Mock catalog and loader

**Files:**
- Create: `backend/src/concierge/catalog.json`
- Create: `backend/src/concierge/catalog.py`
- Create: `backend/tests/test_catalog.py`

- [ ] **Step 1: Author the catalog**

`backend/src/concierge/catalog.json` — at least 25 products, distributed across categories `jewelry` (15+), `home` (5), `stationery` (5), `skincare` (5). Each entry:

```json
{
  "id": "lum-jewel-001",
  "name": "Bar Pendant Necklace",
  "category": "jewelry",
  "vibe_tags": ["minimalist", "warm"],
  "price": 124,
  "image_url": "https://images.unsplash.com/photo-...",
  "description": "Brushed silver bar on a delicate chain.",
  "variants": {
    "finish": ["gold", "silver", "rose"],
    "length": ["16\"", "18\""]
  }
}
```

Curate names and image URLs so the screenshots will look great. Avoid stock-photo cheese.

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_catalog.py`:

```python
import pytest
from concierge.catalog import load_catalog, search, get

def test_load_catalog_returns_at_least_25_items():
    catalog = load_catalog()
    assert len(catalog) >= 25

def test_search_filters_by_category():
    results = search(category="jewelry")
    assert len(results) >= 15
    assert all(p["category"] == "jewelry" for p in results)

def test_search_respects_price_max():
    results = search(price_max=100)
    assert all(p["price"] <= 100 for p in results)

def test_search_matches_any_vibe_tag():
    results = search(vibe_tags=["minimalist"])
    assert all("minimalist" in p["vibe_tags"] for p in results)

def test_get_returns_full_product():
    p = get("lum-jewel-001")
    assert p["id"] == "lum-jewel-001"
    assert "variants" in p

def test_get_unknown_id_raises():
    with pytest.raises(KeyError):
        get("does-not-exist")
```

- [ ] **Step 3: Run and confirm failure**

```bash
cd backend && uv run pytest tests/test_catalog.py -v
```

Expected: `ModuleNotFoundError: No module named 'concierge.catalog'`.

- [ ] **Step 4: Implement `catalog.py`**

`backend/src/concierge/catalog.py`:

```python
from __future__ import annotations
import json
from functools import lru_cache
from importlib import resources
from typing import Any

@lru_cache(maxsize=1)
def load_catalog() -> list[dict[str, Any]]:
    with resources.files("concierge").joinpath("catalog.json").open() as f:
        return json.load(f)

def search(
    *,
    category: str | None = None,
    price_max: float | None = None,
    vibe_tags: list[str] | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    items = load_catalog()
    if category:
        items = [p for p in items if p["category"] == category]
    if price_max is not None:
        items = [p for p in items if p["price"] <= price_max]
    if vibe_tags:
        wanted = set(vibe_tags)
        items = [p for p in items if wanted.intersection(p["vibe_tags"])]
    return items[:limit]

def get(product_id: str) -> dict[str, Any]:
    for p in load_catalog():
        if p["id"] == product_id:
            return p
    raise KeyError(product_id)
```

- [ ] **Step 5: Run tests and confirm pass**

```bash
cd backend && uv run pytest tests/test_catalog.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/concierge/catalog.json backend/src/concierge/catalog.py backend/tests/test_catalog.py
git commit -m "Add mock catalog and search/get loader"
```

---

### Task A4: A2UI serializers

Each serializer takes typed Python params and returns a `dict` matching one of the fixtures from Task A2. The router in Task A5 wraps these for tool calls.

**Files:**
- Create: `backend/src/concierge/a2ui.py`
- Create: `backend/tests/test_a2ui.py`

- [ ] **Step 1: Write failing tests against fixtures**

`backend/tests/test_a2ui.py`:

```python
import json
from pathlib import Path
from concierge import a2ui

FIX = Path(__file__).parent / "fixtures"

def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())

def test_chips_matches_fixture_shape():
    out = a2ui.chips(
        question="What does she lean toward?",
        options=[("jewelry", "Jewelry"), ("home", "Home"),
                 ("stationery", "Stationery"), ("skincare", "Skincare")],
    )
    fixture = _load("a2ui_chips.json")
    assert set(out.keys()) == set(fixture.keys())
    assert out["component"] == fixture["component"]

def test_products_carries_image_and_price():
    out = a2ui.products(
        reasoning="Three minimalist picks.",
        items=[
            {"id": "x", "name": "Thread Necklace", "price": 89,
             "image_url": "https://example.com/a.jpg", "why": "Warm tone."},
        ],
    )
    fixture = _load("a2ui_products.json")
    assert out["component"] == fixture["component"]
    assert out["items"][0]["price"] == 89

def test_product_detail_includes_variant_groups():
    out = a2ui.product_detail(
        product={"id": "x", "name": "Bar Pendant", "price": 124,
                 "image_url": "https://example.com/x.jpg"},
        variants={"finish": ["gold", "silver"], "length": ["16\"", "18\""]},
    )
    assert any(g["name"] == "finish" for g in out["variant_groups"])

def test_form_returns_fields():
    out = a2ui.form(fields=[
        {"type": "toggle", "name": "gift_wrap", "label": "Gift wrap"},
        {"type": "text", "name": "note", "label": "Note", "max_length": 120},
        {"type": "address", "name": "ship_to", "label": "Ship to"},
    ])
    assert len(out["fields"]) == 3

def test_confirmation_summarizes():
    out = a2ui.confirmation(
        order_id="A2UI-7741",
        line_items=[("Bar Pendant · Silver · 16\"", 124),
                    ("Gift wrap", 8)],
        total=132,
        ship_date="Mon, May 11",
    )
    assert out["order_id"] == "A2UI-7741"
    assert out["total"] == 132
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd backend && uv run pytest tests/test_a2ui.py -v
```

Expected: import error on `concierge.a2ui`.

- [ ] **Step 3: Implement the serializers**

`backend/src/concierge/a2ui.py`:

```python
from __future__ import annotations
from typing import Any, Iterable

# NOTE: the exact field names below should match the fixtures captured in
# Task A2. If the upstream v0.8 spec differs, edit field names in lockstep
# with the fixtures so the tests pin both sides.

def chips(*, question: str, options: Iterable[tuple[str, str]]) -> dict[str, Any]:
    return {
        "component": "chip-group",
        "question": question,
        "select": "single",
        "options": [{"value": v, "label": l} for v, l in options],
    }

def products(*, reasoning: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "component": "card-grid",
        "reasoning": reasoning,
        "items": [
            {
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "image_url": p["image_url"],
                "why": p.get("why", ""),
            }
            for p in items
        ],
    }

def product_detail(*, product: dict[str, Any], variants: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "component": "product-detail",
        "product": {
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "image_url": product["image_url"],
        },
        "variant_groups": [
            {"name": name, "options": values, "select": "single"}
            for name, values in variants.items()
        ],
    }

def form(*, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {"component": "form", "fields": fields}

def confirmation(
    *,
    order_id: str,
    line_items: Iterable[tuple[str, float]],
    total: float,
    ship_date: str,
) -> dict[str, Any]:
    return {
        "component": "confirmation-card",
        "order_id": order_id,
        "items": [{"label": label, "amount": amount} for label, amount in line_items],
        "total": total,
        "ship_date": ship_date,
    }
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
cd backend && uv run pytest tests/test_a2ui.py -v
```

Expected: 5 passed. If any field name mismatches the fixture, edit both fixture and serializer until they line up — they are the contract.

- [ ] **Step 5: Commit**

```bash
git add backend/src/concierge/a2ui.py backend/tests/test_a2ui.py
git commit -m "Add A2UI serializers for the five demo surfaces"
```

---

### Task A5: Tools and agent

Wires Claude Sonnet 4.6 with seven tools (3 catalog + 4 `present_*` + place_order). Tests use a recorded fake to avoid live LLM calls.

**Files:**
- Create: `backend/src/concierge/prompts.py`
- Create: `backend/src/concierge/tools.py`
- Create: `backend/src/concierge/agent.py`
- Create: `backend/tests/test_tools.py`

- [ ] **Step 1: Write the system prompt**

`backend/src/concierge/prompts.py`:

```python
SYSTEM_PROMPT = """\
You are the concierge for Lumen Goods, a curated minimalist marketplace
that helps people find thoughtful gifts.

Your job: turn the user's request into a delightful, tight shopping flow.

Rules:
- Ask AT MOST ONE clarifying question before showing options. Use
  `present_chips` for that question — never plain text.
- When you show products, show AT MOST THREE picks via `present_products`.
  Lead with one short sentence of reasoning ("Three minimalist picks…").
- When the user picks a product, call `get_product` then `present_product_detail`.
- When the user is ready to buy, call `present_form` for note/wrap/address.
- After place_order, call `present_confirmation` and stop.

Never emit raw A2UI JSON in your text. Always go through the present_* tools.
"""
```

- [ ] **Step 2: Define tool schemas**

`backend/src/concierge/tools.py`:

```python
from __future__ import annotations
from typing import Any
import uuid
from datetime import date, timedelta
from concierge import catalog, a2ui

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_catalog",
        "description": "Search the Lumen Goods catalog by category, price ceiling, and vibe tags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string",
                             "enum": ["jewelry", "home", "stationery", "skincare"]},
                "price_max": {"type": "number"},
                "vibe_tags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "get_product",
        "description": "Get full detail for a single product by id.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "place_order",
        "description": "Place a (mock) order for a configured product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "variant_options": {"type": "object", "additionalProperties": {"type": "string"}},
                "gift_wrap": {"type": "boolean"},
                "note": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["product_id", "variant_options", "gift_wrap", "address"],
        },
    },
    {
        "name": "present_chips",
        "description": "Render a single-select chip group as the next agent bubble.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["value", "label"],
                    },
                },
            },
            "required": ["question", "options"],
        },
    },
    {
        "name": "present_products",
        "description": "Render up to three product cards as the next agent bubble.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                            "image_url": {"type": "string"},
                            "why": {"type": "string"},
                        },
                        "required": ["id", "name", "price", "image_url"],
                    },
                },
            },
            "required": ["reasoning", "items"],
        },
    },
    {
        "name": "present_product_detail",
        "description": "Render an expanded product detail bubble with variant pickers.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "present_form",
        "description": "Render a form bubble for note + gift wrap + address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_gift_wrap": {"type": "boolean"},
                "include_note": {"type": "boolean"},
            },
        },
    },
    {
        "name": "present_confirmation",
        "description": "Render the final order confirmation bubble.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"label": {"type": "string"}, "amount": {"type": "number"}},
                        "required": ["label", "amount"],
                    },
                },
                "total": {"type": "number"},
                "ship_date": {"type": "string"},
            },
            "required": ["order_id", "line_items", "total", "ship_date"],
        },
    },
]


def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool. Returns either tool output (for state-changing tools)
    or an A2UI fragment (for present_* tools, prefixed with `_a2ui`)."""
    if name == "search_catalog":
        return {"results": catalog.search(**args)}
    if name == "get_product":
        return catalog.get(args["product_id"])
    if name == "place_order":
        order_id = f"A2UI-{str(uuid.uuid4())[:4].upper()}"
        ship_date = (date.today() + timedelta(days=4)).strftime("%a, %b %d")
        return {"order_id": order_id, "ship_date": ship_date}
    if name == "present_chips":
        return {"_a2ui": a2ui.chips(
            question=args["question"],
            options=[(o["value"], o["label"]) for o in args["options"]],
        )}
    if name == "present_products":
        return {"_a2ui": a2ui.products(
            reasoning=args["reasoning"], items=args["items"],
        )}
    if name == "present_product_detail":
        product = catalog.get(args["product_id"])
        return {"_a2ui": a2ui.product_detail(
            product=product, variants=product["variants"],
        )}
    if name == "present_form":
        fields = []
        if args.get("include_gift_wrap", True):
            fields.append({"type": "toggle", "name": "gift_wrap", "label": "Gift wrap (+$8)"})
        if args.get("include_note", True):
            fields.append({"type": "text", "name": "note", "label": "Gift note", "max_length": 120})
        fields.append({"type": "address", "name": "ship_to", "label": "Ship to"})
        return {"_a2ui": a2ui.form(fields=fields)}
    if name == "present_confirmation":
        return {"_a2ui": a2ui.confirmation(
            order_id=args["order_id"],
            line_items=[(li["label"], li["amount"]) for li in args["line_items"]],
            total=args["total"],
            ship_date=args["ship_date"],
        )}
    raise ValueError(f"Unknown tool: {name}")
```

- [ ] **Step 3: Write tests for `run_tool`**

`backend/tests/test_tools.py`:

```python
from concierge.tools import run_tool

def test_search_catalog_returns_results_list():
    out = run_tool("search_catalog", {"category": "jewelry", "price_max": 150})
    assert "results" in out
    assert len(out["results"]) > 0

def test_get_product_returns_id():
    out = run_tool("get_product", {"product_id": "lum-jewel-001"})
    assert out["id"] == "lum-jewel-001"

def test_place_order_assigns_id_and_date():
    out = run_tool("place_order", {
        "product_id": "lum-jewel-001",
        "variant_options": {"finish": "silver", "length": "16\""},
        "gift_wrap": True,
        "address": "235 Pine St, Brooklyn NY",
    })
    assert out["order_id"].startswith("A2UI-")
    assert "ship_date" in out

def test_present_chips_returns_a2ui_payload():
    out = run_tool("present_chips", {
        "question": "What vibe?",
        "options": [{"value": "jewelry", "label": "Jewelry"}],
    })
    assert "_a2ui" in out
    assert out["_a2ui"]["component"] == "chip-group"

def test_present_form_default_includes_three_fields():
    out = run_tool("present_form", {})
    fields = out["_a2ui"]["fields"]
    names = [f["name"] for f in fields]
    assert names == ["gift_wrap", "note", "ship_to"]
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
cd backend && uv run pytest tests/test_tools.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Implement the agent loop**

`backend/src/concierge/agent.py`:

```python
from __future__ import annotations
from typing import Any, AsyncIterator
import json
from anthropic import AsyncAnthropic
from concierge.prompts import SYSTEM_PROMPT
from concierge.tools import TOOL_SCHEMAS, run_tool

MODEL = "claude-sonnet-4-6"

class AgentEvent:
    def __init__(self, kind: str, payload: Any):
        self.kind = kind  # "text" | "a2ui" | "end"
        self.payload = payload

class GiftAgent:
    def __init__(self, client: AsyncAnthropic | None = None):
        self.client = client or AsyncAnthropic()
        self.history: list[dict[str, Any]] = []

    async def turn(self, user_message: str) -> AsyncIterator[AgentEvent]:
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=TOOL_SCHEMAS,
                messages=self.history,
            )

            assistant_blocks: list[dict[str, Any]] = []
            tool_uses: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                    if block.text.strip():
                        yield AgentEvent("text", block.text)
                elif block.type == "tool_use":
                    assistant_blocks.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input,
                    })
                    tool_uses.append({"id": block.id, "name": block.name, "input": block.input})

            self.history.append({"role": "assistant", "content": assistant_blocks})

            if response.stop_reason != "tool_use":
                yield AgentEvent("end", None)
                return

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                output = run_tool(tu["name"], tu["input"])
                if "_a2ui" in output:
                    yield AgentEvent("a2ui", output["_a2ui"])
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": json.dumps({"rendered": True}),
                    })
                else:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": json.dumps(output),
                    })
            self.history.append({"role": "user", "content": tool_results})
```

- [ ] **Step 6: Smoke test the agent (mocked client)**

Append to `backend/tests/test_tools.py`:

```python
import pytest
from concierge.agent import GiftAgent, AgentEvent

class _StubResponse:
    def __init__(self, content, stop_reason): self.content = content; self.stop_reason = stop_reason

class _StubBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.type = kw["type"]

class _StubMessages:
    def __init__(self, scripted): self.scripted = list(scripted)
    async def create(self, **kw): return self.scripted.pop(0)

class _StubClient:
    def __init__(self, scripted): self.messages = _StubMessages(scripted)

@pytest.mark.asyncio
async def test_agent_emits_a2ui_then_end():
    scripted = [
        _StubResponse(
            content=[_StubBlock(type="tool_use", id="t1",
                                name="present_chips",
                                input={"question": "Vibe?",
                                       "options": [{"value": "jewelry", "label": "Jewelry"}]})],
            stop_reason="tool_use",
        ),
        _StubResponse(
            content=[_StubBlock(type="text", text="(awaiting selection)")],
            stop_reason="end_turn",
        ),
    ]
    agent = GiftAgent(client=_StubClient(scripted))
    kinds = [e.kind async for e in agent.turn("Need a gift for my sister")]
    assert "a2ui" in kinds
    assert kinds[-1] == "end"
```

- [ ] **Step 7: Run all backend tests**

```bash
cd backend && uv run pytest -v
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add backend/src/concierge/prompts.py backend/src/concierge/tools.py backend/src/concierge/agent.py backend/tests/test_tools.py
git commit -m "Add agent loop with tool routing and A2UI serializers"
```

---

### Task A6: `/chat` SSE endpoint

**Files:**
- Modify: `backend/src/concierge/app.py`
- Modify: `backend/tests/test_app.py`

- [ ] **Step 1: Write the failing endpoint test**

Append to `backend/tests/test_app.py`:

```python
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from concierge.app import app
from concierge.agent import AgentEvent

class _FakeAgent:
    def __init__(self, *_, **__): self.history = []
    async def turn(self, _msg):
        yield AgentEvent("text", "Three picks coming up.")
        yield AgentEvent("a2ui", {"component": "chip-group", "options": []})
        yield AgentEvent("end", None)

def test_chat_streams_sse_events():
    with patch("concierge.app.GiftAgent", _FakeAgent):
        client = TestClient(app)
        with client.stream("POST", "/chat",
                           json={"sessionId": "s1", "userMessage": "hi"}) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())
        assert "event: text" in body
        assert "event: a2ui" in body
        assert "event: end" in body
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd backend && uv run pytest tests/test_app.py::test_chat_streams_sse_events -v
```

Expected: 404 from `/chat`.

- [ ] **Step 3: Implement the endpoint**

Replace `backend/src/concierge/app.py`:

```python
from __future__ import annotations
import json
from collections import defaultdict
from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from concierge.agent import GiftAgent

app = FastAPI(title="A2UI Gift Concierge")

_sessions: dict[str, GiftAgent] = defaultdict(GiftAgent)

class ChatBody(BaseModel):
    sessionId: str
    userMessage: str

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/chat")
async def chat(body: ChatBody) -> EventSourceResponse:
    agent = _sessions[body.sessionId]
    async def event_stream():
        async for ev in agent.turn(body.userMessage):
            if ev.kind == "end":
                yield {"event": "end", "data": "{}"}
            elif ev.kind == "a2ui":
                yield {"event": "a2ui", "data": json.dumps(ev.payload)}
            else:
                yield {"event": "text", "data": json.dumps({"text": ev.payload})}
    return EventSourceResponse(event_stream())
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_app.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run the server manually and curl**

```bash
cd backend && uv run uvicorn concierge.app:app --port 8000 &
sleep 1 && curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}`. Then kill the server (`kill %1`).

- [ ] **Step 6: Commit**

```bash
git add backend/src/concierge/app.py backend/tests/test_app.py
git commit -m "Stream agent turn over SSE on POST /chat"
```

---

## Phase B — Host bundle (JS)

### Task B1: Scaffold host-bundle

**Files:**
- Create: `host-bundle/package.json`
- Create: `host-bundle/vite.config.js`
- Create: `host-bundle/index.html`
- Create: `host-bundle/src/shim.js` (minimal)
- Create: `host-bundle/src/theme.css`

- [ ] **Step 1: Init**

```bash
mkdir -p host-bundle/src/components
cd host-bundle && npm init -y
npm i lit
npm i -D vite
```

- [ ] **Step 2: Write `package.json` scripts**

Replace `host-bundle/package.json` to include:

```json
{
  "name": "a2ui-host-bundle",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "build:android": "vite build && cp dist/a2ui-host.iife.js ../app/app/src/main/assets/a2ui-host.js && cp ../host-bundle/index-android.html ../app/app/src/main/assets/host.html"
  },
  "dependencies": { "lit": "^3.2.0" },
  "devDependencies": { "vite": "^5.4.0" }
}
```

- [ ] **Step 3: Configure Vite for an IIFE single-file build**

`host-bundle/vite.config.js`:

```js
import { defineConfig } from "vite";
export default defineConfig({
  build: {
    lib: {
      entry: "src/shim.js",
      name: "A2UIHost",
      formats: ["iife"],
      fileName: () => "a2ui-host.iife.js",
    },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
```

- [ ] **Step 4: Write a minimal shim and theme**

`host-bundle/src/theme.css`:

```css
:root {
  --a2ui-color-bg: #f8f4ed;
  --a2ui-color-fg: #1b1b1f;
  --a2ui-color-accent: #5b6cff;
  --a2ui-color-success: #7ab87a;
  --a2ui-radius-md: 14px;
  --a2ui-font-sans: "Inter", system-ui, sans-serif;
  --a2ui-font-serif: "Fraunces", "Times New Roman", serif;
}
body { margin: 0; font-family: var(--a2ui-font-sans); color: var(--a2ui-color-fg); background: var(--a2ui-color-bg); }
```

`host-bundle/src/shim.js`:

```js
import "./theme.css";

const root = () => document.getElementById("a2ui-root");

function render(json) {
  const r = root(); if (!r) return;
  r.innerHTML = "";
  const node = document.createElement("pre");
  node.textContent = JSON.stringify(json, null, 2);
  r.appendChild(node);
  reportSize();
}

function applyTheme(tokens) {
  for (const [k, v] of Object.entries(tokens)) {
    document.documentElement.style.setProperty(`--a2ui-${k}`, v);
  }
}

function reportSize() {
  const h = document.body.scrollHeight;
  if (window.AndroidBridge?.onResize) window.AndroidBridge.onResize(h);
  window.parent?.postMessage({ type: "a2ui:resize", height: h }, "*");
}

new ResizeObserver(reportSize).observe(document.body);

window.a2ui = { render, applyTheme };
```

- [ ] **Step 5: Write a browser playground**

`host-bundle/index.html`:

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>A2UI Host Playground</title></head>
<body>
  <div id="a2ui-root"></div>
  <script type="module" src="/src/shim.js"></script>
  <script type="module">
    setTimeout(() => window.a2ui.render({
      component: "chip-group",
      question: "What does she lean toward?",
      options: [{ value: "jewelry", label: "Jewelry" }, { value: "home", label: "Home" }],
    }), 200);
  </script>
</body></html>
```

`host-bundle/index-android.html` (the file copied into Android assets):

```html
<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body>
  <div id="a2ui-root"></div>
  <script src="a2ui-host.js"></script>
</body></html>
```

- [ ] **Step 6: Manually verify in the browser**

```bash
cd host-bundle && npm run dev
```

Open the printed URL. Expected: the JSON for the chip group renders as plain `<pre>` text. (Real Lit components arrive in Task B3.)

- [ ] **Step 7: Commit**

```bash
git add host-bundle/
git commit -m "Scaffold host-bundle with Vite IIFE build and stub shim"
```

---

### Task B2: Real Lit components for the five surfaces

Replace the JSON `<pre>` placeholder with proper Lit web components for each A2UI surface. If the upstream A2UI Lit package covers them, use it; otherwise implement local fallbacks under `host-bundle/src/components/`.

**Files:**
- Modify: `host-bundle/src/shim.js`
- Create: `host-bundle/src/components/chip-group.js`
- Create: `host-bundle/src/components/card-grid.js`
- Create: `host-bundle/src/components/product-detail.js`
- Create: `host-bundle/src/components/concierge-form.js`
- Create: `host-bundle/src/components/confirmation-card.js`

- [ ] **Step 1: Check for an upstream Lit package**

```bash
npm search a2ui
```

If a real package exists (e.g. `@google/a2ui-lit`), install it and import its components. Otherwise proceed with local fallbacks below.

- [ ] **Step 2: Implement `chip-group.js` (single-select)**

`host-bundle/src/components/chip-group.js`:

```js
import { LitElement, html, css } from "lit";

export class ChipGroup extends LitElement {
  static properties = { question: {}, options: { type: Array }, selected: {} };
  static styles = css`
    :host { display: block; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: var(--a2ui-radius-md); background: #fff; font-family: var(--a2ui-font-sans); }
    .q { font-weight: 600; margin-bottom: 8px; }
    button { font: inherit; padding: 6px 12px; margin: 2px 4px 2px 0; border-radius: 999px; border: 1px solid #e5e7eb; background: #f3f4f8; cursor: pointer; }
    button[aria-pressed="true"] { background: var(--a2ui-color-accent); color: #fff; border-color: var(--a2ui-color-accent); }
  `;
  constructor() { super(); this.options = []; this.selected = null; }
  render() {
    return html`
      <div class="q">${this.question}</div>
      ${this.options.map(o => html`
        <button aria-pressed=${this.selected === o.value} @click=${() => this._pick(o.value)}>${o.label}</button>
      `)}
    `;
  }
  _pick(value) {
    this.selected = value;
    window.AndroidBridge?.onAction(JSON.stringify({ component: "chip-group", value }));
  }
}
customElements.define("a2ui-chip-group", ChipGroup);
```

- [ ] **Step 3: Implement `card-grid.js`**

`host-bundle/src/components/card-grid.js`:

```js
import { LitElement, html, css } from "lit";

export class CardGrid extends LitElement {
  static properties = { reasoning: {}, items: { type: Array } };
  static styles = css`
    :host { display: block; font-family: var(--a2ui-font-sans); }
    .reason { padding: 0 4px 8px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: var(--a2ui-radius-md); overflow: hidden; cursor: pointer; }
    .card img { width: 100%; height: 96px; object-fit: cover; display: block; }
    .body { padding: 8px; }
    .name { font-family: var(--a2ui-font-serif); font-weight: 600; font-size: 14px; }
    .price { color: #555; font-size: 13px; margin-top: 2px; }
    .why { color: #777; font-size: 12px; margin-top: 4px; }
  `;
  render() {
    return html`
      <div class="reason">${this.reasoning}</div>
      <div class="grid">
        ${this.items.map(p => html`
          <div class="card" @click=${() => this._tap(p)}>
            <img src=${p.image_url} alt=${p.name}>
            <div class="body">
              <div class="name">${p.name}</div>
              <div class="price">$${p.price}</div>
              ${p.why ? html`<div class="why">${p.why}</div>` : null}
            </div>
          </div>
        `)}
      </div>
    `;
  }
  _tap(p) {
    window.AndroidBridge?.onAction(JSON.stringify({ component: "card-grid", product_id: p.id }));
  }
}
customElements.define("a2ui-card-grid", CardGrid);
```

- [ ] **Step 4: Implement `product-detail.js`**

`host-bundle/src/components/product-detail.js`:

```js
import { LitElement, html, css } from "lit";

export class ProductDetail extends LitElement {
  static properties = { product: {}, variant_groups: { type: Array }, selection: { state: true } };
  static styles = css`
    :host { display: block; font-family: var(--a2ui-font-sans); background: #fff; border: 1px solid #e5e7eb; border-radius: var(--a2ui-radius-md); padding: 12px; }
    img { width: 100%; height: 140px; object-fit: cover; border-radius: 8px; }
    .name { font-family: var(--a2ui-font-serif); font-weight: 600; font-size: 16px; margin-top: 8px; }
    .price { color: #555; }
    .group { margin-top: 8px; }
    .label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
    button { font: inherit; padding: 4px 10px; margin: 2px 4px 2px 0; border-radius: 999px; border: 1px solid #e5e7eb; background: #f3f4f8; cursor: pointer; }
    button[aria-pressed="true"] { background: var(--a2ui-color-accent); color: #fff; border-color: var(--a2ui-color-accent); }
    .cta { margin-top: 12px; padding: 10px 14px; border-radius: 999px; border: 0; background: var(--a2ui-color-accent); color: #fff; font: inherit; cursor: pointer; }
  `;
  constructor() { super(); this.selection = {}; }
  render() {
    return html`
      <img src=${this.product.image_url}>
      <div class="name">${this.product.name}</div>
      <div class="price">$${this.product.price}</div>
      ${this.variant_groups.map(g => html`
        <div class="group">
          <div class="label">${g.name}</div>
          ${g.options.map(o => html`
            <button aria-pressed=${this.selection[g.name] === o} @click=${() => this._pick(g.name, o)}>${o}</button>
          `)}
        </div>
      `)}
      <button class="cta" @click=${this._confirm}>Continue</button>
    `;
  }
  _pick(group, value) { this.selection = { ...this.selection, [group]: value }; }
  _confirm() {
    window.AndroidBridge?.onAction(JSON.stringify({
      component: "product-detail", product_id: this.product.id, variants: this.selection,
    }));
  }
}
customElements.define("a2ui-product-detail", ProductDetail);
```

- [ ] **Step 5: Implement `concierge-form.js`**

`host-bundle/src/components/concierge-form.js`:

```js
import { LitElement, html, css } from "lit";

export class ConciergeForm extends LitElement {
  static properties = { fields: { type: Array }, values: { state: true } };
  static styles = css`
    :host { display: block; font-family: var(--a2ui-font-sans); background: #fff; border: 1px solid #e5e7eb; border-radius: var(--a2ui-radius-md); padding: 12px; }
    .row { margin-bottom: 10px; }
    .label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
    input, textarea { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 8px; font: inherit; }
    .toggle { display: flex; justify-content: space-between; align-items: center; }
    .switch { width: 36px; height: 20px; background: #ddd; border-radius: 12px; position: relative; cursor: pointer; }
    .switch.on { background: var(--a2ui-color-accent); }
    .knob { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; background: #fff; border-radius: 50%; transition: transform .15s; }
    .switch.on .knob { transform: translateX(16px); }
    .cta { padding: 10px 14px; border-radius: 999px; border: 0; background: var(--a2ui-color-accent); color: #fff; font: inherit; cursor: pointer; }
  `;
  constructor() { super(); this.values = {}; }
  render() {
    return html`
      ${this.fields.map(f => this._renderField(f))}
      <button class="cta" @click=${this._submit}>Place order</button>
    `;
  }
  _renderField(f) {
    if (f.type === "toggle") {
      const on = !!this.values[f.name];
      return html`<div class="row toggle"><span>${f.label}</span>
        <div class="switch ${on ? "on" : ""}" @click=${() => this._set(f.name, !on)}><div class="knob"></div></div>
      </div>`;
    }
    if (f.type === "text") {
      return html`<div class="row"><div class="label">${f.label}</div>
        <textarea rows="2" maxlength=${f.max_length || 200} @input=${e => this._set(f.name, e.target.value)}></textarea>
      </div>`;
    }
    if (f.type === "address") {
      return html`<div class="row"><div class="label">${f.label}</div>
        <input list="addrs" placeholder="Start typing…" @input=${e => this._set(f.name, e.target.value)}>
        <datalist id="addrs">
          <option value="235 Pine St, Brooklyn NY 11201">
          <option value="14 Clement St, San Francisco CA 94118">
          <option value="402 Mission St, Austin TX 78701">
        </datalist></div>`;
    }
    return html``;
  }
  _set(name, value) { this.values = { ...this.values, [name]: value }; }
  _submit() {
    window.AndroidBridge?.onAction(JSON.stringify({ component: "form", values: this.values }));
  }
}
customElements.define("a2ui-form", ConciergeForm);
```

- [ ] **Step 6: Implement `confirmation-card.js`**

`host-bundle/src/components/confirmation-card.js`:

```js
import { LitElement, html, css } from "lit";

export class ConfirmationCard extends LitElement {
  static properties = { order_id: {}, items: { type: Array }, total: { type: Number }, ship_date: {} };
  static styles = css`
    :host { display: block; font-family: var(--a2ui-font-sans); background: #fff; border: 1px solid #e5e7eb; border-radius: var(--a2ui-radius-md); padding: 12px; }
    .badge { background: #dcfce7; color: #166534; font-weight: 600; padding: 4px 10px; border-radius: 999px; display: inline-block; }
    .row { display: flex; justify-content: space-between; padding: 6px 0; }
    .total { border-top: 1px solid #e5e7eb; margin-top: 4px; padding-top: 6px; font-weight: 600; }
    .meta { color: #666; font-size: 12px; margin-top: 4px; }
  `;
  render() {
    return html`
      <div class="badge">✓ Order placed</div>
      ${this.items.map(li => html`<div class="row"><span>${li.label}</span><span>$${li.amount}</span></div>`)}
      <div class="row total"><span>Total</span><span>$${this.total}</span></div>
      <div class="meta">Arrives ${this.ship_date} · #${this.order_id}</div>
    `;
  }
}
customElements.define("a2ui-confirmation-card", ConfirmationCard);
```

- [ ] **Step 7: Update the shim to dispatch by component name**

Replace the body of `host-bundle/src/shim.js`:

```js
import "./theme.css";
import "./components/chip-group.js";
import "./components/card-grid.js";
import "./components/product-detail.js";
import "./components/concierge-form.js";
import "./components/confirmation-card.js";

const COMPONENT_TAG = {
  "chip-group": "a2ui-chip-group",
  "card-grid": "a2ui-card-grid",
  "product-detail": "a2ui-product-detail",
  "form": "a2ui-form",
  "confirmation-card": "a2ui-confirmation-card",
};

function root() { return document.getElementById("a2ui-root"); }

function render(json) {
  const r = root(); if (!r) return;
  r.innerHTML = "";
  const tag = COMPONENT_TAG[json.component];
  if (!tag) { r.textContent = `unknown component: ${json.component}`; reportSize(); return; }
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(json)) {
    if (k === "component") continue;
    el[k] = v;
  }
  r.appendChild(el);
  reportSize();
}

function applyTheme(tokens) {
  for (const [k, v] of Object.entries(tokens)) {
    document.documentElement.style.setProperty(`--a2ui-${k}`, v);
  }
}

let lastReported = -1;
function reportSize() {
  const h = Math.round(document.body.getBoundingClientRect().height);
  if (h === lastReported) return;
  lastReported = h;
  if (window.AndroidBridge?.onResize) window.AndroidBridge.onResize(h);
  window.parent?.postMessage({ type: "a2ui:resize", height: h }, "*");
}
new ResizeObserver(reportSize).observe(document.body);

window.a2ui = { render, applyTheme };
```

- [ ] **Step 8: Verify each surface in the playground**

```bash
cd host-bundle && npm run dev
```

In the dev page, edit the inline script to test each component shape (chip-group, card-grid with a few products, product-detail, form, confirmation-card). Each should render visibly and selecting/submitting should `console.log` an action (set `window.AndroidBridge = { onAction: console.log }` in DevTools first).

- [ ] **Step 9: Commit**

```bash
git add host-bundle/
git commit -m "Implement Lit components for the five A2UI surfaces"
```

---

### Task B3: Build for Android assets

- [ ] **Step 1: Pre-create the Android assets folder**

```bash
mkdir -p app/app/src/main/assets
```

- [ ] **Step 2: Build and copy artifacts**

```bash
cd host-bundle && npm run build:android
ls ../app/app/src/main/assets/
```

Expected: `host.html` and `a2ui-host.js` present.

- [ ] **Step 3: Open `host.html` directly in a browser to confirm self-contained**

```bash
open ../app/app/src/main/assets/host.html
```

In DevTools console, run:

```js
window.a2ui.render({ component: "chip-group", question: "Vibe?", options: [{ value: "j", label: "Jewelry" }] });
```

Expected: chip group renders.

- [ ] **Step 4: Commit (host bundle artifacts are tracked because Android needs them; this matches a typical asset workflow)**

```bash
git add app/app/src/main/assets/
git commit -m "Build host bundle into Android assets"
```

---

## Phase C — Android app

### Task C1: Android project scaffold

**Files:**
- Create: `app/settings.gradle.kts`
- Create: `app/build.gradle.kts`
- Create: `app/gradle.properties`
- Create: `app/app/build.gradle.kts`
- Create: `app/app/src/main/AndroidManifest.xml`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/MainActivity.kt`

- [ ] **Step 1: Initialize Gradle wrapper and Kotlin DSL skeleton**

The simplest path: open Android Studio, create a new "Empty Activity" Compose project at `app/`, package `com.diegoz.a2uiconcierge`, language Kotlin, min SDK 26, target SDK 34. Let Studio generate the wrapper and gradle files. Then prune the generated assets (`res/drawable`, default launcher icon) we don't need.

- [ ] **Step 2: Confirm `app/app/build.gradle.kts` declares Compose, Material 3, OkHttp, and `compose-markdown`**

Add to the dependencies block of `app/app/build.gradle.kts`:

```kotlin
dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.10.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.6")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("dev.jeziellago:compose-markdown:0.5.4")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}
```

Add the kotlin-serialization plugin to the same file's plugins block: `id("org.jetbrains.kotlin.plugin.serialization") version "2.0.21"`.

- [ ] **Step 3: Add internet + cleartext for tunnel/local server**

In `app/app/src/main/AndroidManifest.xml`, inside `<manifest>`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<application
    android:usesCleartextTraffic="true"
    android:label="A2UI Concierge"
    android:theme="@style/Theme.Material3.Light.NoActionBar">
    <activity android:name=".MainActivity" android:exported="true">
        <intent-filter>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent-filter>
    </activity>
</application>
```

Also in `app/app/build.gradle.kts` `defaultConfig`:

```kotlin
buildConfigField("String", "BACKEND_BASE_URL", "\"http://10.0.2.2:8000\"")
```

(`10.0.2.2` is the emulator's loopback to host. For a physical device, override per build flavor or rebuild with the tunnel URL.)

- [ ] **Step 4: Replace `MainActivity` with a Compose stub**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/MainActivity.kt`:

```kotlin
package com.diegoz.a2uiconcierge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import com.diegoz.a2uiconcierge.theme.AppTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AppTheme { Hello() } }
    }
}

@Composable private fun Hello() { Text("A2UI Concierge") }
```

- [ ] **Step 5: Build and install**

```bash
cd app && ./gradlew :app:installDebug
```

Expected: APK installs on the running emulator and launches showing "A2UI Concierge".

- [ ] **Step 6: Commit**

```bash
git add app/
git commit -m "Scaffold Android app with Compose and dependencies"
```

---

### Task C2: Theme module (Material 3 + tokens)

**Files:**
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Color.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Type.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Theme.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/ThemeTokens.kt`

- [ ] **Step 1: Define palette**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Color.kt`:

```kotlin
package com.diegoz.a2uiconcierge.theme
import androidx.compose.ui.graphics.Color

val Ivory = Color(0xFFF8F4ED)
val Ink = Color(0xFF1B1B1F)
val Indigo = Color(0xFF5B6CFF)
val Mist = Color(0xFFE5E7EB)
val SoftGreen = Color(0xFF7AB87A)
```

- [ ] **Step 2: Typography**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Type.kt`:

```kotlin
package com.diegoz.a2uiconcierge.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val AppTypography = Typography(
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 16.sp, fontWeight = FontWeight.Normal),
    titleMedium = TextStyle(fontFamily = FontFamily.Serif, fontSize = 18.sp, fontWeight = FontWeight.SemiBold),
    labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 11.sp, fontWeight = FontWeight.Medium),
)
```

- [ ] **Step 3: Theme wrapper**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme/Theme.kt`:

```kotlin
package com.diegoz.a2uiconcierge.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = Indigo, onPrimary = androidx.compose.ui.graphics.Color.White,
    background = Ivory, onBackground = Ink,
    surface = androidx.compose.ui.graphics.Color.White, onSurface = Ink,
    outline = Mist, tertiary = SoftGreen,
)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    val _ = isSystemInDarkTheme() // dynamic color disabled by design
    MaterialTheme(colorScheme = LightColors, typography = AppTypography, content = content)
}
```

- [ ] **Step 4: WebView token bridge**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/ThemeTokens.kt`:

```kotlin
package com.diegoz.a2uiconcierge.a2ui

import org.json.JSONObject

object ThemeTokens {
    fun asJson(): String = JSONObject(mapOf(
        "color-bg" to "#F8F4ED",
        "color-fg" to "#1B1B1F",
        "color-accent" to "#5B6CFF",
        "color-success" to "#7AB87A",
        "radius-md" to "14px",
        "font-sans" to "Inter, system-ui, sans-serif",
        "font-serif" to "Fraunces, 'Times New Roman', serif",
    )).toString()
}
```

- [ ] **Step 5: Build and confirm app still runs**

```bash
cd app && ./gradlew :app:installDebug
```

Expected: app launches with the (still placeholder) "A2UI Concierge" text on the ivory background.

- [ ] **Step 6: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/theme app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/ThemeTokens.kt
git commit -m "Add theme module and WebView token bridge"
```

---

### Task C3: Chat data models and ViewModel

**Files:**
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/Message.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/ChatRepository.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModel.kt`
- Create: `app/app/src/test/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModelTest.kt`

- [ ] **Step 1: Message sealed type**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/Message.kt`:

```kotlin
package com.diegoz.a2uiconcierge.chat

import kotlinx.serialization.json.JsonObject

sealed interface Message {
    val id: String
    data class User(override val id: String, val text: String) : Message
    data class AgentText(override val id: String, val markdown: String) : Message
    data class AgentA2ui(override val id: String, val fragments: List<JsonObject>) : Message
}
```

- [ ] **Step 2: Write the ViewModel test (fails)**

`app/app/src/test/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModelTest.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import com.diegoz.a2uiconcierge.chat.AgentEvent
import com.diegoz.a2uiconcierge.chat.ChatRepository
import com.diegoz.a2uiconcierge.chat.Message
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class ChatViewModelTest {
    @Test fun `appends user then agent messages`() = runTest {
        val repo = object : ChatRepository {
            override fun send(text: String) = flowOf(
                AgentEvent.Text("Three picks coming up."),
                AgentEvent.A2ui(buildJsonObject {}),
                AgentEvent.End,
            )
        }
        val vm = ChatViewModel(repo)
        vm.send("Need a gift")
        // allow flow to drain
        kotlinx.coroutines.test.advanceUntilIdle()
        val kinds = vm.messages.value.map { it::class.simpleName }
        assertEquals(listOf("User", "AgentText", "AgentA2ui"), kinds)
    }
}
```

- [ ] **Step 3: Repository interface and event type**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/ChatRepository.kt`:

```kotlin
package com.diegoz.a2uiconcierge.chat

import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.JsonObject

sealed interface AgentEvent {
    data class Text(val text: String) : AgentEvent
    data class A2ui(val payload: JsonObject) : AgentEvent
    data object End : AgentEvent
}

interface ChatRepository {
    fun send(text: String): Flow<AgentEvent>
}
```

- [ ] **Step 4: Implement the ViewModel**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModel.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.diegoz.a2uiconcierge.chat.AgentEvent
import com.diegoz.a2uiconcierge.chat.ChatRepository
import com.diegoz.a2uiconcierge.chat.Message
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

class ChatViewModel(private val repo: ChatRepository) : ViewModel() {
    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    fun send(text: String) {
        if (text.isBlank()) return
        _messages.update { it + Message.User(UUID.randomUUID().toString(), text) }

        viewModelScope.launch {
            var textBubbleId: String? = null
            var a2uiBubbleId: String? = null

            repo.send(text).collect { ev ->
                when (ev) {
                    is AgentEvent.Text -> {
                        if (textBubbleId == null) {
                            val id = UUID.randomUUID().toString()
                            textBubbleId = id
                            _messages.update { it + Message.AgentText(id, ev.text) }
                        } else {
                            _messages.update { list ->
                                list.map { m ->
                                    if (m is Message.AgentText && m.id == textBubbleId) m.copy(markdown = m.markdown + ev.text) else m
                                }
                            }
                        }
                    }
                    is AgentEvent.A2ui -> {
                        if (a2uiBubbleId == null) {
                            val id = UUID.randomUUID().toString()
                            a2uiBubbleId = id
                            _messages.update { it + Message.AgentA2ui(id, listOf(ev.payload)) }
                        } else {
                            _messages.update { list ->
                                list.map { m ->
                                    if (m is Message.AgentA2ui && m.id == a2uiBubbleId) m.copy(fragments = m.fragments + ev.payload) else m
                                }
                            }
                        }
                    }
                    AgentEvent.End -> Unit
                }
            }
        }
    }
}
```

- [ ] **Step 5: Run unit tests**

```bash
cd app && ./gradlew :app:testDebugUnitTest --tests "*ChatViewModelTest*"
```

Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModel.kt app/app/src/test
git commit -m "Add chat models, repository interface, and ChatViewModel"
```

---

### Task C4: SSE client (OkHttp)

**Files:**
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/SseClient.kt`
- Create: `app/app/src/test/kotlin/com/diegoz/a2uiconcierge/chat/SseParserTest.kt`

- [ ] **Step 1: Test the SSE line parser**

`app/app/src/test/kotlin/com/diegoz/a2uiconcierge/chat/SseParserTest.kt`:

```kotlin
package com.diegoz.a2uiconcierge.chat

import org.junit.Assert.assertEquals
import org.junit.Test

class SseParserTest {
    @Test fun `parses single event with data`() {
        val raw = "event: text\ndata: {\"text\":\"Hi\"}\n\n"
        val events = parseSseStream(raw.lineSequence())
        assertEquals(1, events.size)
        assertEquals("text", events[0].name)
        assertEquals("{\"text\":\"Hi\"}", events[0].data)
    }
    @Test fun `parses two events separated by blank line`() {
        val raw = "event: text\ndata: {\"text\":\"a\"}\n\nevent: end\ndata: {}\n\n"
        val events = parseSseStream(raw.lineSequence())
        assertEquals(2, events.size)
        assertEquals(listOf("text", "end"), events.map { it.name })
    }
}
```

- [ ] **Step 2: Implement parser + repository**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/SseClient.kt`:

```kotlin
package com.diegoz.a2uiconcierge.chat

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.UUID

data class SseEvent(val name: String, val data: String)

internal fun parseSseStream(lines: Sequence<String>): List<SseEvent> {
    val out = mutableListOf<SseEvent>()
    var name = "message"
    var data = StringBuilder()
    fun flush() {
        if (data.isNotEmpty()) { out.add(SseEvent(name, data.toString().trimEnd('\n'))); name = "message"; data = StringBuilder() }
    }
    for (line in lines) {
        when {
            line.isEmpty() -> flush()
            line.startsWith("event: ") -> name = line.substring(7)
            line.startsWith("data: ") -> data.append(line.substring(6)).append('\n')
        }
    }
    flush()
    return out
}

class HttpChatRepository(private val baseUrl: String) : ChatRepository {
    private val client = OkHttpClient()
    private val json = Json { ignoreUnknownKeys = true }
    private val sessionId = UUID.randomUUID().toString()

    override fun send(text: String): Flow<AgentEvent> = flow {
        val body = """{"sessionId":"$sessionId","userMessage":${Json.encodeToString(kotlinx.serialization.builtins.serializer<String>(), text)}}"""
            .toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url("$baseUrl/chat").post(body).build()
        client.newCall(req).execute().use { resp ->
            val source = resp.body!!.source()
            val buffer = StringBuilder()
            while (!source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                if (line.isEmpty()) {
                    val events = parseSseStream(buffer.toString().lineSequence())
                    buffer.clear()
                    for (ev in events) {
                        when (ev.name) {
                            "text" -> {
                                val obj = json.parseToJsonElement(ev.data).jsonObject
                                emit(AgentEvent.Text(obj["text"]!!.jsonPrimitive.content))
                            }
                            "a2ui" -> emit(AgentEvent.A2ui(json.parseToJsonElement(ev.data).jsonObject))
                            "end" -> { emit(AgentEvent.End); return@flow }
                        }
                    }
                } else {
                    buffer.append(line).append('\n')
                }
            }
        }
    }.flowOn(Dispatchers.IO)
}
```

(`jsonObject` accessor: add `import kotlinx.serialization.json.jsonObject` at top.)

- [ ] **Step 3: Run parser tests**

```bash
cd app && ./gradlew :app:testDebugUnitTest --tests "*SseParserTest*"
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/chat/SseClient.kt app/app/src/test/kotlin/com/diegoz/a2uiconcierge/chat/SseParserTest.kt
git commit -m "Add OkHttp-based SSE client and chat repository"
```

---

### Task C5: ChatScreen layout (text-only)

**Files:**
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/UserBubble.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentTextBubble.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/InputRow.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt`
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/MainActivity.kt`

- [ ] **Step 1: UserBubble**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/UserBubble.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp

@Composable
fun UserBubble(text: String) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), horizontalArrangement = Arrangement.End) {
        Text(
            text = text,
            color = MaterialTheme.colorScheme.onPrimary,
            modifier = Modifier
                .clip(RoundedCornerShape(topStart = 14.dp, topEnd = 14.dp, bottomStart = 14.dp, bottomEnd = 4.dp))
                .background(MaterialTheme.colorScheme.primary)
                .padding(horizontal = 12.dp, vertical = 8.dp)
        )
    }
}
```

- [ ] **Step 2: AgentTextBubble (Markdown)**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentTextBubble.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import dev.jeziellago.compose.markdowntext.MarkdownText

@Composable
fun AgentTextBubble(markdown: String) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
        Box(
            Modifier
                .clip(RoundedCornerShape(topStart = 14.dp, topEnd = 14.dp, bottomEnd = 14.dp, bottomStart = 4.dp))
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
                .padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            MarkdownText(markdown = markdown, color = MaterialTheme.colorScheme.onSurface)
        }
    }
}
```

- [ ] **Step 3: InputRow**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/InputRow.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun InputRow(onSend: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = text, onValueChange = { text = it },
            placeholder = { Text("Tell the concierge…") },
            modifier = Modifier.weight(1f),
            singleLine = true,
        )
        Spacer(Modifier.width(6.dp))
        FilledIconButton(onClick = { onSend(text); text = "" }, enabled = text.isNotBlank()) {
            Icon(Icons.Default.Send, contentDescription = "Send")
        }
    }
}
```

- [ ] **Step 4: ChatScreen**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.diegoz.a2uiconcierge.chat.Message

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel) {
    val messages by vm.messages.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Lumen Concierge") }) },
        bottomBar = { InputRow(onSend = vm::send) },
    ) { padding ->
        LazyColumn(state = listState, modifier = Modifier.padding(padding).fillMaxSize()) {
            items(messages, key = { it.id }) { m ->
                when (m) {
                    is Message.User -> UserBubble(m.text)
                    is Message.AgentText -> AgentTextBubble(m.markdown)
                    is Message.AgentA2ui -> Spacer(Modifier.height(8.dp)) // wired in C6
                }
            }
        }
    }
}
```

- [ ] **Step 5: Wire MainActivity**

Replace `MainActivity.kt`:

```kotlin
package com.diegoz.a2uiconcierge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.lifecycle.ViewModelProvider
import com.diegoz.a2uiconcierge.chat.HttpChatRepository
import com.diegoz.a2uiconcierge.theme.AppTheme
import com.diegoz.a2uiconcierge.ui.ChatScreen
import com.diegoz.a2uiconcierge.ui.ChatViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repo = HttpChatRepository(BuildConfig.BACKEND_BASE_URL)
        val vmFactory = object : ViewModelProvider.Factory {
            override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST") return ChatViewModel(repo) as T
            }
        }
        val vm: ChatViewModel by viewModels { vmFactory }
        setContent { AppTheme { ChatScreen(vm) } }
    }
}
```

Add `buildFeatures { buildConfig = true }` to the `android` block in `app/app/build.gradle.kts` if not already present.

- [ ] **Step 6: Run end-to-end with backend**

In two terminals:

```bash
# 1: backend
cd backend && uv run uvicorn concierge.app:app --host 0.0.0.0 --port 8000

# 2: install + log
cd app && ./gradlew :app:installDebug && adb logcat *:E
```

Type a message in the emulator. Expected: user bubble appears. If the agent emits text, an agent text bubble appears (A2UI bubbles still placeholder until C6).

- [ ] **Step 7: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui app/app/src/main/kotlin/com/diegoz/a2uiconcierge/MainActivity.kt app/app/build.gradle.kts
git commit -m "Implement ChatScreen with user and agent text bubbles"
```

---

### Task C6: AgentA2uiBubble (WebView host)

**Files:**
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentA2uiBubble.kt`
- Create: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/A2uiBridge.kt`
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt`

- [ ] **Step 1: Bridge interface**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/A2uiBridge.kt`:

```kotlin
package com.diegoz.a2uiconcierge.a2ui

import android.webkit.JavascriptInterface
import kotlinx.coroutines.channels.Channel

class A2uiBridge {
    val actions = Channel<String>(capacity = Channel.UNLIMITED)
    val resizes = Channel<Int>(capacity = Channel.CONFLATED)

    @JavascriptInterface
    fun onAction(json: String) { actions.trySend(json) }

    @JavascriptInterface
    fun onResize(heightPx: Int) { resizes.trySend(heightPx) }
}
```

- [ ] **Step 2: Bubble composable**

`app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentA2uiBubble.kt`:

```kotlin
package com.diegoz.a2uiconcierge.ui

import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.diegoz.a2uiconcierge.a2ui.A2uiBridge
import com.diegoz.a2uiconcierge.a2ui.ThemeTokens
import kotlinx.coroutines.flow.consumeAsFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AgentA2uiBubble(
    fragments: List<JsonObject>,
    onAction: (String) -> Unit,
) {
    val bridge = remember { A2uiBridge() }
    var measured by remember { mutableStateOf(120.dp) }
    val animated by animateDpAsState(targetValue = measured, label = "a2ui-height")
    val density = androidx.compose.ui.platform.LocalDensity.current

    LaunchedEffect(bridge) {
        launch {
            for (h in bridge.resizes.consumeAsFlow()) {
                measured = with(density) { h.toDp() }
            }
        }
        launch {
            for (json in bridge.actions.consumeAsFlow()) onAction(json)
        }
    }

    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
        AndroidView(
            modifier = Modifier.fillMaxWidth().height(animated),
            factory = { ctx ->
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    setBackgroundColor(0)
                    addJavascriptInterface(bridge, "AndroidBridge")
                    webViewClient = object : WebViewClient() {
                        override fun onPageFinished(view: WebView, url: String?) {
                            view.evaluateJavascript(
                                "window.a2ui.applyTheme(${ThemeTokens.asJson()});", null,
                            )
                            // Render initial fragment(s) once page is ready.
                            renderAll(view, fragments)
                        }
                    }
                    loadUrl("file:///android_asset/host.html")
                }
            },
            update = { wv -> renderAll(wv, fragments) },
        )
    }
}

private fun renderAll(wv: WebView, fragments: List<JsonObject>) {
    if (fragments.isEmpty()) return
    val payload = fragments.last().toString()  // demo: render the latest fragment
    wv.evaluateJavascript("window.a2ui.render($payload);", null)
}
```

- [ ] **Step 3: Wire into ChatScreen**

In `ChatScreen.kt`, replace the `is Message.AgentA2ui ->` branch:

```kotlin
is Message.AgentA2ui -> AgentA2uiBubble(
    fragments = m.fragments,
    onAction = { json -> /* hooked up in C7 */ },
)
```

- [ ] **Step 4: Manual verification**

Run backend + app. From the input, type something that the agent answers with `present_chips` (e.g., "Need a gift for my sister, minimalist, under $150"). Expected: the chip group renders inside an embedded WebView bubble; tapping a chip writes to logcat (action printed via JS — soon to be wired). The bubble height adapts to content (no scroll-within-scroll).

- [ ] **Step 5: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/a2ui/A2uiBridge.kt app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentA2uiBubble.kt app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt
git commit -m "Render A2UI bubbles in WebView with theme bridge and auto-height"
```

---

### Task C7: Action events round-trip

When the user selects a chip / picks a card / submits a form inside the WebView, the JSON payload must travel back to the agent as a fresh user turn (with the structured action embedded).

**Files:**
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModel.kt`
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt`

- [ ] **Step 1: Add an `onAction` API to ChatViewModel**

In `ChatViewModel`, add:

```kotlin
fun onA2uiAction(json: String) {
    // Convert structured payload to a short natural-language follow-up,
    // so the LLM has enough context. The raw JSON is included verbatim
    // so the model can also parse it directly.
    val summary = "[ui-action] $json"
    send(summary)
}
```

- [ ] **Step 2: Hook the bubble to it**

In `ChatScreen.kt`:

```kotlin
is Message.AgentA2ui -> AgentA2uiBubble(
    fragments = m.fragments,
    onAction = vm::onA2uiAction,
)
```

- [ ] **Step 3: Update the system prompt to recognize ui-actions**

Append to `backend/src/concierge/prompts.py`:

```python
SYSTEM_PROMPT += """\

When the user message starts with `[ui-action]`, the rest of the line is a
JSON payload describing the user's selection in the most recent A2UI bubble.
Treat it as an answer to the last question and continue the flow. Examples:

- `[ui-action] {"component":"chip-group","value":"jewelry"}` — proceed to search.
- `[ui-action] {"component":"card-grid","product_id":"lum-jewel-002"}` — call get_product / present_product_detail.
- `[ui-action] {"component":"product-detail","product_id":"...","variants":{...}}` — proceed to present_form.
- `[ui-action] {"component":"form","values":{...}}` — call place_order, then present_confirmation.
"""
```

- [ ] **Step 4: Manual end-to-end check**

Run backend + app. Drive the full Beat 1 → Beat 6 flow by tapping in the emulator. Expected: each tap advances the agent. The Confirmation bubble is the final agent message.

- [ ] **Step 5: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatViewModel.kt app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt backend/src/concierge/prompts.py
git commit -m "Wire A2UI actions back to the agent as ui-action messages"
```

---

## Phase D — End-to-end smoke + polish

### Task D1: End-to-end smoke and bug fixes

- [ ] **Step 1: Cold-start the system**

Backend:
```bash
cd backend && uv run uvicorn concierge.app:app --host 0.0.0.0 --port 8000
```

Android (emulator):
```bash
cd app && ./gradlew :app:installDebug && adb shell am start -n com.diegoz.a2uiconcierge/.MainActivity
```

- [ ] **Step 2: Walk all six beats**

Type "Need a gift for my sister — minimalist, under $150". Then tap each chip / card / variant / form field per the storyboard. Confirm each bubble matches the expectations in spec §4.

- [ ] **Step 3: Time the flow**

With a stopwatch from prompt-send to confirmation-rendered. Expected: ≤ 90 s total. If a single beat takes > 5 s on first byte, profile (most likely culprit: missing prompt-cache → first model call slow). Patch by ensuring `system` is sent as cached content (already in Task A5) and warming on app launch with a tiny `/health` ping.

- [ ] **Step 4: Capture screenshots**

Capture three screenshots: beat 3 (cards), beat 4 (variants), beat 6 (confirmation). Save to `docs/screenshots/`.

```bash
mkdir -p docs/screenshots
adb shell screencap -p /sdcard/s.png && adb pull /sdcard/s.png docs/screenshots/beat-3.png
# repeat after each beat
```

- [ ] **Step 5: File and fix any visible bugs**

Common likely fixes (apply only if hit):
- WebView height "snaps": set `android:hardwareAccelerated="true"` (default), and bump initial `measured = 120.dp` → 80.dp to reduce visual gap.
- Markdown bubble shows raw `\n`: ensure the text accumulates as we go, not a single un-streamed blob (already correct in `ChatViewModel`; double-check `Json.parseToJsonElement` for `text` event handles `\n`).
- Tunnel cert warnings on a real device: prefer Cloudflare Tunnel over ngrok.

- [ ] **Step 6: Commit fixes (if any) and screenshots**

```bash
git add docs/screenshots
git commit -m "Add demo screenshots and end-to-end smoke fixes"
```

---

### Task D2: Polish — motion, loading, haptic

**Files:**
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/ChatScreen.kt`
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentA2uiBubble.kt`
- Modify: `app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui/AgentTextBubble.kt`

- [ ] **Step 1: Bubble entrance animation**

Wrap each bubble's root in `Modifier.animateItemPlacement()` (LazyColumn) and a `AnimatedVisibility(...)` with a `fadeIn() + slideInVertically(...)` for the new bubble.

```kotlin
items(messages, key = { it.id }) { m ->
    androidx.compose.animation.AnimatedVisibility(
        visible = true,
        enter = androidx.compose.animation.fadeIn() +
                androidx.compose.animation.slideInVertically(initialOffsetY = { it / 4 }),
    ) {
        when (m) { /* same branches as before */ }
    }
}
```

- [ ] **Step 2: WebView fade-in once first measure resolves**

In `AgentA2uiBubble`, hold the WebView at `alpha = 0f` until the first `onResize` event, then animate to `1f` over 120 ms. Track via a `mutableStateOf(false)` that flips on first resize.

- [ ] **Step 3: Haptic on confirmation**

When a new `AgentA2ui` fragment with `component == "confirmation-card"` arrives, call `LocalHapticFeedback.current.performHapticFeedback(HapticFeedbackType.LongPress)` once.

- [ ] **Step 4: Loading shimmer for the first agent reply**

While `vm.isThinking` (add as `StateFlow<Boolean>` updated around `repo.send().collect`), show a small three-dot placeholder bubble at the bottom that disappears once the first event arrives.

- [ ] **Step 5: Re-record the demo**

Run the flow again on the emulator and capture a fresh 30-second screen recording:

```bash
adb shell screenrecord /sdcard/demo.mp4 --time-limit 30
adb pull /sdcard/demo.mp4 docs/screenshots/demo.mp4
```

- [ ] **Step 6: Commit**

```bash
git add app/app/src/main/kotlin/com/diegoz/a2uiconcierge/ui docs/screenshots
git commit -m "Add motion polish, WebView fade-in, haptic on confirmation"
```

---

## Phase E — Demo prep

### Task E1: README and runbook

**Files:**
- Create: `README.md`
- Create: `docs/runbook.md`

- [ ] **Step 1: Write `README.md`**

Cover: what the project is (one paragraph), architecture diagram (copy from spec §5.1), how to run backend, build host bundle, install Android app, and the link to the runbook. Keep it under one screen.

- [ ] **Step 2: Write `docs/runbook.md`**

A printable one-pager:
- Pre-demo checklist (servers up, tunnel up, phone connected, screen recording on).
- Demo script with the exact words to type at each beat.
- Recovery moves: if the model goes off-script, what to type to nudge it back.
- The two backup screenshots to fall back to if anything fails.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/runbook.md
git commit -m "Add README and printable demo runbook"
```

---

## Self-review

**Spec coverage check:**
- §4 (six storyboard beats) → A4 serializers, A5 tools, B2 components, C5–C7 rendering. ✓
- §5.1 (architecture shape) → entire layout. ✓
- §5.3 (A2UI bubble: bridge, theme, height, action) → C2 (tokens), C6 (bridge + height + render), C7 (action). ✓
- §5.4 (transport) → A6 (server), C4 (client). ✓
- §6 (agent backend + tools + system prompt + session state) → A1, A5, A6, C7 (prompt update). ✓
- §7 (mock data) → A3. ✓
- §8 (Android app structure) → C1, C2, C3, C5, C6. ✓
- §9 (theming + tokens delivered to WebView) → C2 (`ThemeTokens.asJson`) + B1 (CSS contract) + B2 (Lit reads tokens) + C6 (`applyTheme` invocation). ✓
- §10 (build, run, demo) → README and runbook in E1; per-task commands. ✓
- §12 (Definition of done: install on Pixel, all 6 beats, theme consistency, 30 s clip, README) → D1 + D2 + E1. ✓

**Placeholder scan:** No "TBD"/"TODO"/"implement later". A2 is a research task with concrete outputs (fixtures + shapes doc).

**Type consistency:**
- `AgentEvent` types match between Python (`AgentEvent` class) and Kotlin (`AgentEvent` sealed interface) — both use `Text` / `A2ui` / `End`.
- Tool names in `prompts.py`, `tools.py`, and `agent.py` match (`present_chips`, `present_products`, etc.).
- A2UI component names match across A4 serializers (`chip-group`, `card-grid`, `product-detail`, `form`, `confirmation-card`), B2 Lit `customElements.define`, and B2 shim `COMPONENT_TAG` map.
- `BACKEND_BASE_URL` consumed in `MainActivity` matches `BuildConfig` field name in C1.

No mismatches found.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-07-a2ui-android-shopping-demo.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
