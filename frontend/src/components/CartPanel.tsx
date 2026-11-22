import type { Cart } from "../api/types";
import { formatPrice, formatWeight } from "../labels";
import Loading from "./Loading";

interface Props {
  cart: Cart | null;
  /** Product id currently being removed (disables its button). */
  removingId: number | null;
  onRemove: (productId: number) => void;
  note: string | null;
  error: string | null;
}

export default function CartPanel({ cart, removingId, onRemove, note, error }: Props) {
  return (
    <section className="panel" aria-labelledby="cart-title">
      <h2 id="cart-title">購物籃</h2>
      {error && <p role="alert" className="field-error">{error}</p>}
      {note && <p role="status" className="note">{note}</p>}
      {cart === null ? (
        <Loading />
      ) : cart.items.length === 0 ? (
        <p className="muted">購物籃是空的。從今日生鮮選擇商品加入。</p>
      ) : (
        <>
          <ul className="plain basket-list" aria-label="購物籃內容">
            {cart.items.map((i) => (
              <li key={i.product_id}>
                <div>
                  <strong>{i.name}</strong>
                  <div className="muted small">{formatWeight(i.weight_grams)} · {formatPrice(i.price_per_kg)}／公斤</div>
                </div>
                <div className="basket-item-actions">
                  <span>{formatPrice(i.subtotal)}</span>
                  <button
                    type="button"
                    className="link"
                    disabled={removingId !== null}
                    onClick={() => onRemove(i.product_id)}
                    aria-label={`移除 ${i.name}`}
                  >
                    {removingId === i.product_id ? "移除中…" : "移除"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="basket-total"><span>總計</span><strong className="total">{formatPrice(cart.total_amount)}</strong></div>
        </>
      )}
    </section>
  );
}
