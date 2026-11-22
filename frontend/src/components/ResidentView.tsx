import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchCart, fetchProducts, removeCartItem } from "../api/client";
import type { Cart, CartEventResult, CheckoutResult, Product, Resident } from "../api/types";
import { rejectionLabel } from "../labels";
import CartPanel from "./CartPanel";
import CheckoutPanel from "./CheckoutPanel";
import LoadError from "./LoadError";
import Loading from "./Loading";
import NutritionPanel from "./NutritionPanel";
import ProductTable from "./ProductTable";
import ResidentProfile from "./ResidentProfile";
import SimulatorPanel from "./SimulatorPanel";

interface Props {
  resident: Resident;
  onLogout: () => void;
}

export default function ResidentView({ resident, onLogout }: Props) {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [cart, setCart] = useState<Cart | null>(null);
  // Tracked separately: a successful cart load must never hide a failed product load.
  const [productsError, setProductsError] = useState<string | null>(null);
  const [cartLoadError, setCartLoadError] = useState<string | null>(null);
  const loadError = productsError ?? cartLoadError;
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [cartNote, setCartNote] = useState<string | null>(null);
  const [cartError, setCartError] = useState<string | null>(null);

  const message = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

  const loadProducts = useCallback(async () => {
    try {
      setProducts(await fetchProducts());
      setProductsError(null);
    } catch (e) {
      setProductsError(message(e, "載入商品失敗"));
    }
  }, []);

  const loadCart = useCallback(async () => {
    try {
      setCart(await fetchCart(resident.resident_id));
      setCartLoadError(null);
    } catch (e) {
      setCartLoadError(message(e, "載入購物車失敗"));
    }
  }, [resident.resident_id]);

  const reload = useCallback(() => {
    setProductsError(null);
    setCartLoadError(null);
    void loadProducts();
    void loadCart();
  }, [loadProducts, loadCart]);

  useEffect(reload, [reload]);

  // The result always carries the authoritative cart (unchanged when rejected).
  const handleEventResult = useCallback((r: CartEventResult) => {
    setCart(r.cart);
    setCartNote(null);
    setCartError(null);
  }, []);

  async function handleRemove(productId: number) {
    setRemovingId(productId);
    setCartNote(null);
    setCartError(null);
    try {
      const r = await removeCartItem(resident.resident_id, productId);
      setCart(r.cart);
      const last = r.events[r.events.length - 1];
      if (r.accepted) {
        setCartNote(
          `已透過 Gateway 送出 ${r.events.length} 個 REMOVE_ITEM 封包（最後一個：${last.packet_hex}）`,
        );
      } else {
        setCartError(
          `移除被拒絕：${rejectionLabel(last.rejection_code ?? "")}${
            last.rejection_reason ? `（${last.rejection_reason}）` : ""
          }`,
        );
      }
    } catch (e) {
      setCartError(message(e, "移除失敗，請稍後再試"));
    } finally {
      setRemovingId(null);
    }
  }

  const handleCheckout = useCallback(
    (r: CheckoutResult) => {
      setCart(r.cart);
      setCartNote(null);
      setCartError(null);
      if (r.payment_status === "PAID") void loadProducts(); // stock changed
    },
    [loadProducts],
  );

  return (
    <>
      <ResidentProfile resident={resident} onLogout={onLogout} />
      {loadError && <LoadError message={loadError} onRetry={reload} />}
      <NutritionPanel residentId={resident.resident_id} />
      <CartPanel
        cart={cart}
        removingId={removingId}
        onRemove={(id) => void handleRemove(id)}
        note={cartNote}
        error={cartError}
      />
      <CheckoutPanel residentId={resident.resident_id} cart={cart} onDone={handleCheckout} />
      {products && (
        <SimulatorPanel
          residentId={resident.resident_id}
          products={products}
          onResult={handleEventResult}
        />
      )}
      <section className="panel" aria-labelledby="products-title">
        <h2 id="products-title">今日生鮮</h2>
        <p className="muted">價格與庫存由後端資料庫提供；付款成功後庫存會更新。</p>
        {!loadError && products === null && <Loading />}
        {products && <ProductTable products={products} caption="可購買的生鮮商品" />}
      </section>
    </>
  );
}
