"""A2UI v0.8 message builders for the Lumen Concierge custom catalog.

Each builder returns a list of v0.8 protocol messages — typically a
``surfaceUpdate`` followed by a ``beginRendering`` — so each agent bubble
is a self-contained surface with a fresh ``surfaceId`` and a single root
component drawn from the custom catalog ``lumen.com:concierge/v1``.

Wire shape (v0.8, server-to-client):

    {"surfaceUpdate": {
        "surfaceId": "s-...",
        "components": [
            {"id": "c-root", "component": {
                "ChipGroup": {
                    "question": {"literalString": "..."},
                    "options":  [{"value": "...", "label": {"literalString": "..."}}],
                    "selections": {"literalArray": []},
                    "maxAllowedSelections": 1,
                    "variant": "chips",
                    "action": {"name": "chip-group"}
                }
            }}
        ]
    }}
    {"beginRendering": {"surfaceId": "s-...", "root": "c-root",
                         "catalogId": "lumen.com:concierge/v1"}}

The standard-catalog component shapes are mirrored where applicable
(``MultipleChoice``/``CheckBox``/``TextField``); higher-level commerce
components (``CardGrid``, ``ProductDetail``, ``ConciergeForm``,
``ConfirmationCard``, ``PaymentChallenge``, ``TxDetail``) live in the
custom catalog. Custom-catalog property schemas are free-form per v0.8
``catalog_description_schema.json``.
"""
from __future__ import annotations
from typing import Any, Iterable
import uuid

CATALOG_ID = "lumen.com:concierge/v1"

A2uiMessage = dict[str, Any]


def _bind_str(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"literalString": value}


def _bind_bool(value: bool | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"literalBoolean": value}


def _bind_num(value: float | int | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"literalNumber": value}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _wrap_surface(component_type: str, props: dict[str, Any]) -> list[A2uiMessage]:
    """Bundle a single custom-catalog component as the root of a fresh surface."""
    surface_id = _new_id("s")
    root_id = _new_id("c")
    cleaned = {k: v for k, v in props.items() if v is not None}
    return [
        {"surfaceUpdate": {
            "surfaceId": surface_id,
            "components": [
                {"id": root_id, "component": {component_type: cleaned}}
            ],
        }},
        {"beginRendering": {
            "surfaceId": surface_id,
            "root": root_id,
            "catalogId": CATALOG_ID,
        }},
    ]


# ── builders ─────────────────────────────────────────────────────────────


def chips(*, question: str, options: Iterable[tuple[str, str]]) -> list[A2uiMessage]:
    return _wrap_surface("ChipGroup", {
        "question": _bind_str(question),
        "options": [
            {"value": v, "label": _bind_str(l)} for v, l in options
        ],
        "selections": {"literalArray": []},
        "maxAllowedSelections": 1,
        "variant": "chips",
        "action": {"name": "chip-group"},
    })


def products(
    *, reasoning: str, items: list[dict[str, Any]], section: str | None = None,
) -> list[A2uiMessage]:
    return _wrap_surface("CardGrid", {
        "section": _bind_str(section),
        "reasoning": _bind_str(reasoning),
        "items": [
            {
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "salePrice": p.get("sale_price"),
                "vendor": p.get("vendor"),
                "imageUrl": p["image_url"],
                "why": p.get("why", ""),
            }
            for p in items
        ],
        "action": {"name": "card-grid"},
    })


def product_detail(
    *, product: dict[str, Any], variants: dict[str, list[str]],
) -> list[A2uiMessage]:
    requires_age = "age_verification" in product.get("required_credentials", [])
    return _wrap_surface("ProductDetail", {
        "requiresAgeVerification": _bind_bool(requires_age),
        "product": {
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "salePrice": product.get("sale_price"),
            "vendor": product.get("vendor"),
            "inStock": product.get("in_stock", True),
            "imageUrl": product["image_url"],
            "images": product.get("images") or [product["image_url"]],
            "description": product.get("description", ""),
        },
        "variantGroups": [
            {"name": name, "options": values, "select": "single"}
            for name, values in variants.items()
        ],
        "action": {"name": "product-detail"},
    })


def form(*, fields: list[dict[str, Any]]) -> list[A2uiMessage]:
    return _wrap_surface("ConciergeForm", {
        "fields": [
            {
                "type": f["type"],
                "name": f["name"],
                "label": _bind_str(f["label"]),
                **({"maxLength": f["max_length"]} if "max_length" in f else {}),
            }
            for f in fields
        ],
        "action": {"name": "form"},
    })


def confirmation(
    *,
    order_id: str,
    line_items: Iterable[tuple[str, float]],
    total: float,
    ship_date: str,
    tx_hash: str | None = None,
    explorer_url: str | None = None,
) -> list[A2uiMessage]:
    return _wrap_surface("ConfirmationCard", {
        "orderId": order_id,
        "items": [{"label": label, "amount": amount} for label, amount in line_items],
        "total": total,
        "shipDate": _bind_str(ship_date),
        "txHash": _bind_str(tx_hash),
        "explorerUrl": _bind_str(explorer_url),
        "action": {"name": "confirmation-card"},
    })


def payment_challenge(
    *,
    challenge: dict[str, Any],
    line_items: Iterable[tuple[str, float]],
    requires_age_verification: bool = False,
    age_dcql_query_json: str | None = None,
    dpc_dcql_query_json: str | None = None,
    loyalty_discount_pct: int = 0,
    loyalty_dcql_query_json: str | None = None,
) -> list[A2uiMessage]:
    """x402 payment sheet. ``challenge`` carries the EIP-3009 fields the
    Android client uses to build a signed envelope; ``line_items`` is the
    order summary."""
    props: dict[str, Any] = {
        "orderId": challenge["order_id"],
        "label": _bind_str(challenge["label"]),
        "amountDisplay": _bind_str(challenge["amount_display"]),
        "items": [{"label": label, "amount": amount} for label, amount in line_items],
        "challenge": challenge,
        "dpcDcqlQueryJson": _bind_str(dpc_dcql_query_json or ""),
        "action": {"name": "payment-challenge"},
    }
    if requires_age_verification:
        props["requiresAgeVerification"] = _bind_bool(True)
        props["ageDcqlQueryJson"] = _bind_str(age_dcql_query_json or "")
    if loyalty_discount_pct:
        props["loyaltyDiscountPct"] = loyalty_discount_pct
        props["loyaltyDcqlQueryJson"] = _bind_str(loyalty_dcql_query_json or "")
    return _wrap_surface("PaymentChallenge", props)


def tx_detail(
    *,
    order_id: str,
    tx_hash: str | None,
    explorer_url: str | None,
    network: str | None,
    items: Iterable[tuple[str, float]],
    total: float | None,
    ship_date: str | None,
    pay_to: str | None = None,
    amount_display: str | None = None,
) -> list[A2uiMessage]:
    return _wrap_surface("TxDetail", {
        "orderId": order_id,
        "txHash": _bind_str(tx_hash),
        "explorerUrl": _bind_str(explorer_url),
        "network": _bind_str(network),
        "amountDisplay": _bind_str(amount_display),
        "total": _bind_num(total),
        "items": [{"label": label, "amount": amount} for label, amount in items],
        "shipDate": _bind_str(ship_date),
        "payTo": _bind_str(pay_to),
    })
