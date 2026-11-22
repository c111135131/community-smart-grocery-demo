import { useState } from "react";
import { ApiError, checkout } from "../api/client";
import type { Cart, CheckoutResult, PaymentSimulation } from "../api/types";
import { formatPrice, formatWeight } from "../labels";

interface Props {
  residentId: number;
  cart: Cart | null;
  onDone: (result: CheckoutResult) => void;
}

/** Simulated checkout. There is no real payment provider: the outcome is chosen here. */
export default function CheckoutPanel({ residentId, cart, onDone }: Props) {
  const [payment, setPayment] = useState<PaymentSimulation>("SUCCESS");
  const [result, setResult] = useState<CheckoutResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const empty = cart === null || cart.items.length === 0;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const r = await checkout(residentId, payment);
      setResult(r);
      onDone(r);
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "結帳失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="checkout-title">
      <h2 id="checkout-title">結帳（模擬付款）</h2>
      <p className="muted">
        不串接任何真實金流。付款成功才會建立訂單並扣庫存；付款失敗則保留購物車、不扣庫存，可重試。
      </p>
      <fieldset className="radio-row" disabled={busy}>
        <legend>模擬付款結果</legend>
        <label>
          <input type="radio" name="pay" checked={payment === "SUCCESS"} onChange={() => setPayment("SUCCESS")} />
          付款成功
        </label>
        <label>
          <input type="radio" name="pay" checked={payment === "FAILURE"} onChange={() => setPayment("FAILURE")} />
          付款失敗
        </label>
      </fieldset>
      <button type="button" disabled={busy || empty} onClick={() => void submit()}>
        {busy ? "結帳中…" : cart && !empty ? `結帳 ${formatPrice(cart.total_amount)}` : "結帳"}
      </button>
      {empty && !result && <span className="muted small"> 購物車是空的</span>}

      {error && <p role="alert" className="field-error">{error}</p>}

      {result && (
        <div role="status" aria-live="polite" className="receipt">
          <div className={result.payment_status === "PAID" ? "banner banner-ok" : "banner banner-bad"}>
            <strong>
              {result.payment_status === "PAID"
                ? `✓ 付款成功，訂單 #${result.order_id}`
                : `✗ 付款失敗（紀錄為訂單 #${result.order_id}，狀態 FAILED）`}
            </strong>
            <span>{result.message}</span>
          </div>
          <h3>{result.payment_status === "PAID" ? "收據" : "本次結帳明細（未成立）"}</h3>
          <div className="table-wrap">
            <table className="compact">
              <caption className="sr-only">結帳明細</caption>
              <thead>
                <tr>
                  <th scope="col">商品</th>
                  <th scope="col" className="num">重量</th>
                  <th scope="col" className="num">單價/公斤</th>
                  <th scope="col" className="num">小計</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((i) => (
                  <tr key={i.product_id}>
                    <th scope="row">{i.product_name}</th>
                    <td className="num">{formatWeight(i.weight_grams)}</td>
                    <td className="num">{formatPrice(i.price_per_kg)}</td>
                    <td className="num">{formatPrice(i.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colSpan={3}>總額</th>
                  <td className="num total">{formatPrice(result.total_amount)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
