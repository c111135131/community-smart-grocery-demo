import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchInventory } from "../api/client";
import type { Product } from "../api/types";
import LoadError from "./LoadError";
import Loading from "./Loading";
import ProductTable from "./ProductTable";

/** Demo admin screen: read-only inventory. No admin authentication on purpose (course demo). */
export default function AdminInventory() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProducts(await fetchInventory());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "載入庫存失敗");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel" aria-labelledby="admin-title">
      <div className="panel-head">
        <h2 id="admin-title">商品與庫存（管理）</h2>
        <button type="button" className="secondary" onClick={() => void load()}>重新整理</button>
      </div>
      <p className="muted">示範用管理畫面，未設定管理員驗證；僅提供唯讀檢視。</p>
      {error && <LoadError message={error} onRetry={() => void load()} />}
      {!error && products === null && <Loading />}
      {products && (
        <ProductTable products={products} showAdminColumns caption="商品庫存清單" />
      )}
    </section>
  );
}
