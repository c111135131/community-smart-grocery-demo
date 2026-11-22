import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchAdminOrders } from "../api/client";
import type { AdminOrder } from "../api/types";
import { formatPrice, formatWeight, paymentLabel } from "../labels";
import LoadError from "./LoadError";
import Loading from "./Loading";

/** Demo admin view of recent orders, including failed payment attempts. */
export default function AdminOrders() {
  const [orders, setOrders] = useState<AdminOrder[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setOrders(await fetchAdminOrders(20));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "載入訂單失敗");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel" aria-labelledby="orders-title">
      <div className="panel-head">
        <h2 id="orders-title">最近訂單（管理）</h2>
        <button type="button" className="secondary" onClick={() => void load()}>重新整理</button>
      </div>
      <p className="muted">付款失敗的嘗試也會留下紀錄（狀態 FAILED），但不會扣庫存。</p>
      {error && <LoadError message={error} onRetry={() => void load()} />}
      {!error && orders === null && <Loading />}
      {orders && orders.length === 0 && <p className="muted">尚無訂單。</p>}
      {orders && orders.length > 0 && (
        <div className="table-wrap">
          <table className="compact">
            <caption className="sr-only">最近訂單</caption>
            <thead>
              <tr>
                <th scope="col">訂單</th><th scope="col">時間</th><th scope="col">居民</th>
                <th scope="col">狀態</th><th scope="col">明細</th><th scope="col" className="num">總額</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.order_id}>
                  <th scope="row">#{o.order_id}</th>
                  <td>{new Date(o.created_at).toLocaleString("zh-TW")}</td>
                  <td>{o.resident_name}</td>
                  <td className={o.payment_status === "PAID" ? "ok" : "bad"}>
                    {o.payment_status === "PAID" ? "✓" : "✗"} {paymentLabel(o.payment_status)}
                  </td>
                  <td>
                    {o.items.map((i) => `${i.product_name} ${formatWeight(i.weight_grams)}`).join("、")}
                  </td>
                  <td className="num">{formatPrice(o.total_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
