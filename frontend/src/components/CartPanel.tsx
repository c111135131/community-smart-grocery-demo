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
      <h2 id="cart-title">購物車</h2>
      <p className="muted">
        購物車只會被通過 Gateway 驗證的事件修改；單價、小計與總額全部由後端計算。
      </p>
      {error && <p role="alert" className="field-error">{error}</p>}
      {note && <p role="status" className="note">{note}</p>}
      {cart === null ? (
        <Loading />
      ) : cart.items.length === 0 ? (
        <p className="muted">購物車是空的。請用下方模擬器送出 ADD_ITEM 事件。</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">購物車內容</caption>
            <thead>
              <tr>
                <th scope="col">商品</th>
                <th scope="col" className="num">重量</th>
                <th scope="col" className="num">每公斤單價</th>
                <th scope="col" className="num">小計</th>
                <th scope="col"><span className="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              {cart.items.map((i) => (
                <tr key={i.product_id}>
                  <th scope="row">{i.name}（{i.product_code}）</th>
                  <td className="num">{formatWeight(i.weight_grams)}</td>
                  <td className="num">{formatPrice(i.price_per_kg)}</td>
                  <td className="num">{formatPrice(i.subtotal)}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      disabled={removingId !== null}
                      onClick={() => onRemove(i.product_id)}
                      aria-label={`移除 ${i.name}`}
                    >
                      {removingId === i.product_id ? "移除中…" : "移除"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">總計</th>
                <td className="num">{formatWeight(cart.total_weight_grams)}</td>
                <td></td>
                <td className="num total">{formatPrice(cart.total_amount)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}
