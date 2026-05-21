import { LitElement, html, css } from "lit";

// v0.8 custom-catalog component "ConfirmationCard". Props are camelCased
// per spec convention (orderId, txHash, explorerUrl, shipDate).
export class ConfirmationCard extends LitElement {
  static properties = {
    orderId: {},
    items: { type: Array },
    total: { type: Number },
    shipDate: {},
    txHash: {},
    explorerUrl: {},
  };
  static styles = css`
    :host { display: block; margin: 0 12px; font-family: var(--a2ui-font-sans); background: #fff; border: 1px solid #ece8e0; border-radius: var(--a2ui-radius-md); padding: 16px; box-shadow: 0 1px 2px rgba(20, 18, 14, 0.04), 0 6px 16px -10px rgba(20, 18, 14, 0.08); }
    .badge { background: #e7f6e7; color: #2d6a2d; font-weight: 600; font-size: 13px; padding: 5px 12px; border-radius: 999px; display: inline-block; margin-bottom: 10px; }
    .row { display: flex; justify-content: space-between; padding: 7px 0; font-size: 14px; color: #1B1B1F; }
    .row span:last-child { font-family: var(--a2ui-font-serif); font-weight: 600; }
    .total { border-top: 1px solid #ece8e0; margin-top: 6px; padding-top: 10px; font-weight: 600; font-size: 15px; }
    .total span:last-child { font-size: 16px; }
    .meta { color: #8a8790; font-size: 12px; margin-top: 8px; letter-spacing: .2px; }
    .tx { margin-top: 10px; padding: 9px 12px; background: #faf7f1; border-radius: 10px; font-size: 12px; cursor: pointer; transition: background .12s, transform .08s; border: 0; width: 100%; text-align: left; font: inherit; }
    .tx:hover { background: #f4efe6; }
    .tx:active { transform: scale(0.99); background: #efe9dc; }
    .tx .hash { color: #4a3aa0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; word-break: break-all; }
    .tx .lbl { display: flex; justify-content: space-between; color: #6b6973; font-weight: 600; letter-spacing: .3px; text-transform: uppercase; font-size: 10px; margin-bottom: 3px; }
    .tx .chev { color: #8a8790; font-weight: 600; }
    .dpc-badge { margin-top: 10px; padding: 9px 12px; background: #f0f1ff; border-radius: 10px; display: flex; align-items: center; gap: 8px; }
    .dpc-badge .icon { font-size: 18px; flex-shrink: 0; }
    .dpc-badge .info { display: flex; flex-direction: column; }
    .dpc-badge .lbl { color: #4a3aa0; font-weight: 600; letter-spacing: .3px; text-transform: uppercase; font-size: 10px; }
    .dpc-badge .sub { color: #6b6973; font-size: 11.5px; margin-top: 2px; }
  `;
  constructor() {
    super();
    this.items = [];
  }
  render() {
    const isDpc = this.txHash?.startsWith("dpc-");
    const txShort = this.txHash ? `${this.txHash.slice(0, 10)}…${this.txHash.slice(-8)}` : null;
    return html`
      <div class="badge">✓ Order placed</div>
      ${this.items.map(li => html`<div class="row"><span>${li.label}</span><span>$${li.amount}</span></div>`)}
      <div class="row total"><span>Total</span><span>$${this.total}</span></div>
      <div class="meta">Arrives ${this.shipDate} · #${this.orderId}</div>
      ${isDpc ? html`
        <div class="dpc-badge">
          <div class="icon">💳</div>
          <div class="info">
            <div class="lbl">Card payment</div>
            <div class="sub">Paid with digital payment credential</div>
          </div>
        </div>
      ` : this.txHash ? html`
        <button class="tx" type="button" @click=${this._openTxDetail}>
          <div class="lbl"><span>On-chain payment</span><span class="chev">View ›</span></div>
          <div class="hash">${txShort}</div>
        </button>
      ` : null}
    `;
  }

  // Surface a v0.8 userAction the host can intercept:
  //  - Android: ChatViewModel pops an in-app TxDetail modal sheet
  //  - Web:     the index.html shim opens the explorer URL in a new tab
  _openTxDetail() {
    this.dispatchEvent(new CustomEvent("a2ui-action", {
      bubbles: true, composed: true,
      detail: {
        name: "tx-detail-open",
        context: {
          order_id: this.orderId,
          tx_hash: this.txHash,
          explorer_url: this.explorerUrl,
          items: this.items,
          total: this.total,
          ship_date: this.shipDate,
        },
      },
    }));
  }
}
customElements.define("a2ui-confirmation-card", ConfirmationCard);
