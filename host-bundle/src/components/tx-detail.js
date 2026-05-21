import { LitElement, html, css } from "lit";

/**
 * v0.8 custom-catalog component "TxDetail". Transaction-detail sheet
 * content, rendered inside a modal bottom sheet on Android (and as a
 * fallback on the web). Props camelCased per spec convention. All fields
 * are passed in from the confirmation-card click — no network lookup
 * needed since we already have the data client-side at confirmation time.
 */
export class TxDetail extends LitElement {
  static properties = {
    orderId: {},
    txHash: {},
    explorerUrl: {},
    network: {},
    amountDisplay: {},
    total: { type: Number },
    items: { type: Array },
    shipDate: {},
    payTo: {},
  };

  static styles = css`
    :host {
      display: block;
      position: relative;
      font-family: var(--a2ui-font-sans);
      background: #fff;
      border-radius: var(--a2ui-radius-md);
      padding: 4px 18px 24px;
      color: #1B1B1F;
    }
    .close {
      position: absolute;
      top: 10px; right: 10px;
      width: 32px; height: 32px;
      border-radius: 999px; border: 0;
      background: #f4efe6; color: #1B1B1F;
      font: inherit; font-size: 15px; line-height: 1;
      display: grid; place-items: center;
      cursor: pointer; z-index: 2;
      transition: transform .08s, background .15s;
    }
    .close:active { transform: scale(0.94); background: #ece8e0; }
    .header {
      display: flex; flex-direction: column; align-items: center;
      padding: 12px 0 18px; gap: 8px;
    }
    .status-mark {
      width: 56px; height: 56px;
      border-radius: 999px;
      background: #e7f6e7;
      display: grid; place-items: center;
      color: #2d6a2d; font-size: 28px; font-weight: 600;
    }
    .status { font-family: var(--a2ui-font-serif); font-weight: 600; font-size: 18px; }
    .amount { font-family: var(--a2ui-font-serif); font-weight: 700; font-size: 28px; letter-spacing: -0.01em; }
    .amount-sub { font-size: 12px; color: #8a8790; letter-spacing: .3px; text-transform: uppercase; font-weight: 600; }

    .group {
      background: #faf7f1;
      border-radius: 14px;
      padding: 4px 14px;
      margin-bottom: 12px;
    }
    .row {
      display: flex; justify-content: space-between; align-items: flex-start;
      gap: 14px;
      padding: 12px 0;
      border-bottom: 1px solid #ece8e0;
      font-size: 13.5px;
    }
    .row:last-child { border-bottom: 0; }
    .row .k { color: #6b6973; font-weight: 500; flex: 0 0 auto; }
    .row .v { text-align: right; color: #1B1B1F; font-family: var(--a2ui-font-serif); font-weight: 600; word-break: break-all; }
    .row .v.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; font-weight: 500; color: #1B1B1F; }
    .copy {
      margin-left: 6px; font: inherit; font-size: 11px;
      background: transparent; border: 0;
      color: #5B6CFF; cursor: pointer; font-weight: 600;
      padding: 0; letter-spacing: .3px;
    }
    .copy.copied { color: #2d6a2d; }

    .lines { margin-top: 4px; }
    .lines .row .k { font-family: var(--a2ui-font-sans); font-weight: 500; color: #1B1B1F; }
    .lines .row .v { font-family: var(--a2ui-font-serif); }
    .lines .total .k { font-weight: 700; }
    .lines .total .v { font-size: 15px; }

    .basescan {
      display: block; width: 100%;
      padding: 14px 18px;
      border-radius: 14px;
      border: 1px solid #d8d2c5;
      background: #fff;
      color: #1B1B1F;
      font: inherit; font-weight: 600; font-size: 14px;
      cursor: pointer;
      text-align: center;
      transition: transform .08s, background .15s;
      text-decoration: none;
    }
    .basescan:active { transform: scale(0.98); background: #faf7f1; }
    .meta { font-size: 11px; color: #8a8790; margin-top: 14px; text-align: center; line-height: 1.5; }
  `;

  constructor() {
    super();
    this.items = [];
    this.network = "base-sepolia";
    this._copied = false;
  }

  render() {
    const txShort = this.txHash ? `${this.txHash.slice(0, 10)}…${this.txHash.slice(-8)}` : "—";
    const networkLabel = this.network === "base-sepolia" ? "Base Sepolia (testnet)" : this.network;
    const totalLabel = this.amountDisplay || (this.total != null ? `$${this.total}` : "—");

    return html`
      <button class="close" aria-label="Close" @click=${this._close}>✕</button>
      <div class="header">
        <div class="status-mark">✓</div>
        <div class="status">Payment confirmed</div>
        <div class="amount">${totalLabel}</div>
        <div class="amount-sub">on-chain payment · USDC</div>
      </div>

      <div class="group">
        <div class="row">
          <span class="k">Status</span>
          <span class="v" style="color:#2d6a2d">Confirmed</span>
        </div>
        <div class="row">
          <span class="k">Network</span>
          <span class="v">${networkLabel}</span>
        </div>
        <div class="row">
          <span class="k">Tx hash</span>
          <span class="v mono">
            ${txShort}
            <button class="copy ${this._copied ? "copied" : ""}" @click=${this._copy}>${this._copied ? "Copied" : "Copy"}</button>
          </span>
        </div>
        ${this.payTo ? html`
          <div class="row">
            <span class="k">Paid to</span>
            <span class="v mono">${this.payTo.slice(0, 10)}…${this.payTo.slice(-6)}</span>
          </div>
        ` : null}
      </div>

      <div class="group lines">
        ${(this.items || []).map(li => html`
          <div class="row"><span class="k">${li.label}</span><span class="v">$${li.amount}</span></div>
        `)}
        <div class="row total"><span class="k">Order total</span><span class="v">${totalLabel}</span></div>
        ${this.shipDate ? html`
          <div class="row"><span class="k">Arrives</span><span class="v">${this.shipDate}</span></div>
        ` : null}
        <div class="row"><span class="k">Order ID</span><span class="v">#${this.orderId || "—"}</span></div>
      </div>

      ${this.explorerUrl ? html`
        <a class="basescan" href=${this.explorerUrl} target="_blank" rel="noreferrer">View on BaseScan ↗</a>
      ` : null}

      <div class="meta">Settled via x402 ${this.network === "base-sepolia" ? "on Base Sepolia testnet" : ""}.
        Hardware-signed authorizations are bound to a single nonce and deadline.</div>
    `;
  }

  _close() {
    this.dispatchEvent(new CustomEvent("a2ui-action", {
      bubbles: true, composed: true,
      detail: { name: "tx-detail-close", context: {} },
    }));
  }

  async _copy() {
    if (!this.txHash) return;
    try {
      await navigator.clipboard?.writeText(this.txHash);
      this._copied = true;
      this.requestUpdate();
      setTimeout(() => { this._copied = false; this.requestUpdate(); }, 1400);
    } catch { /* clipboard blocked in some webviews — silent no-op */ }
  }
}
customElements.define("a2ui-tx-detail", TxDetail);
