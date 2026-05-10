"""x402 payment challenge construction + settlement.

The agent's `place_order` tool produces an x402 challenge that the Android
client signs with its StrongBox-backed wallet. The signed envelope comes
back to /x402/settle, which forwards it to a facilitator and returns the
on-chain tx hash. For the demo, settlement is mocked out by default —
flip ``X402_SETTLE_REAL=1`` to forward to a real facilitator.
"""

from __future__ import annotations

import os
import secrets
import time
import uuid
from typing import Any

# Base Sepolia (testnet) USDC + chain config. Pulled from env so the demo can
# point at a different network without touching code.
NETWORK = os.getenv("X402_NETWORK", "base-sepolia")
CHAIN_ID = int(os.getenv("X402_CHAIN_ID", "84532"))
USDC_ADDRESS = os.getenv(
    "X402_USDC_ADDRESS",
    # Base Sepolia USDC.
    "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
)
PAY_TO_ADDRESS = os.getenv(
    "X402_PAY_TO_ADDRESS",
    # Demo recipient — override in backend/.env for a real run.
    "0x0000000000000000000000000000000000000000",
)
FACILITATOR_URL = os.getenv(
    "X402_FACILITATOR_URL",
    "https://x402.org/facilitator/settle",
)
SETTLE_REAL = os.getenv("X402_SETTLE_REAL", "0") == "1"

# USDC has 6 decimals. ``amount_units`` in the challenge is base units, so
# $1.00 == 1_000_000.
USDC_DECIMALS = 6
# Hold the challenge open for 5 minutes after issue.
CHALLENGE_VALIDITY_SECONDS = 5 * 60

# In-memory order store — keyed by order_id. Keeps challenge ↔ tx_hash so the
# settle endpoint can validate and the agent's later present_confirmation call
# can include the tx hash.
_ORDERS: dict[str, dict[str, Any]] = {}


def _to_base_units(amount_dollars: float) -> int:
    return int(round(amount_dollars * (10 ** USDC_DECIMALS)))


def _basescan_url(tx_hash: str) -> str:
    base = "https://sepolia.basescan.org" if NETWORK == "base-sepolia" else "https://basescan.org"
    return f"{base}/tx/{tx_hash}"


def build_challenge(*, total_dollars: float, label: str) -> dict[str, Any]:
    """Return an x402 challenge ready to embed in an A2UI fragment.

    ``label`` is the human-readable line shown in the payment sheet
    (e.g. "Lumen — Gift order #A2UI-AB12").
    """
    order_id = f"A2UI-{str(uuid.uuid4())[:4].upper()}"
    nonce = "0x" + secrets.token_hex(32)
    now = int(time.time())
    challenge = {
        "scheme": "exact",
        "network": NETWORK,
        "chain_id": CHAIN_ID,
        "asset": USDC_ADDRESS,
        "asset_decimals": USDC_DECIMALS,
        "pay_to": PAY_TO_ADDRESS,
        "amount_units": _to_base_units(total_dollars),
        "amount_display": f"{total_dollars:.2f} USDC",
        "valid_after": now,
        "valid_before": now + CHALLENGE_VALIDITY_SECONDS,
        "nonce": nonce,
        "label": label,
        "order_id": order_id,
    }
    _ORDERS[order_id] = {"challenge": challenge, "settled": False, "tx_hash": None}
    print(f"[x402] built challenge order_id={order_id} total=${total_dollars:.2f} | _ORDERS keys={list(_ORDERS.keys())}", flush=True)
    return challenge


async def settle(*, order_id: str, signed_envelope: dict[str, Any]) -> dict[str, Any]:
    """Submit the signed envelope to the facilitator (or mock-settle).

    Returns ``{"tx_hash": str, "explorer_url": str}`` on success.
    Raises ``ValueError`` if the order is unknown or already settled.
    """
    print(f"[x402] settle request order_id={order_id!r} | _ORDERS keys={list(_ORDERS.keys())}", flush=True)
    record = _ORDERS.get(order_id)
    if record is None:
        raise ValueError(f"Unknown order_id: {order_id}")
    if record["settled"]:
        return {"tx_hash": record["tx_hash"], "explorer_url": _basescan_url(record["tx_hash"])}

    if SETTLE_REAL:
        tx_hash = await _settle_with_facilitator(record["challenge"], signed_envelope)
    else:
        # Mock settlement for the demo path. Yields a realistic-looking 32-byte
        # tx hash so UI flows can render the confirmation card with a link.
        tx_hash = "0x" + secrets.token_hex(32)

    record["settled"] = True
    record["tx_hash"] = tx_hash
    return {"tx_hash": tx_hash, "explorer_url": _basescan_url(tx_hash)}


async def _settle_with_facilitator(challenge: dict[str, Any], signed: dict[str, Any]) -> str:
    """Forward the signed EIP-3009 envelope to an x402 facilitator and
    return the on-chain tx hash. Imported lazily so the demo path doesn't
    require httpx in a cold start."""
    import httpx
    payload = {"challenge": challenge, "envelope": signed}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(FACILITATOR_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    tx = data.get("tx_hash") or data.get("transaction_hash")
    if not tx:
        raise RuntimeError(f"Facilitator did not return tx_hash: {data}")
    return tx


def get_order(order_id: str) -> dict[str, Any] | None:
    return _ORDERS.get(order_id)
