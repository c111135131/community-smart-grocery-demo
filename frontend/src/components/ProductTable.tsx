import type { Product } from "../api/types";
import { categoryLabel, formatPrice, formatWeight } from "../labels";

interface Props {
  products: Product[];
  /** Admin view also shows weight bounds and active status. */
  showAdminColumns?: boolean;
  caption: string;
}

export default function ProductTable({ products, showAdminColumns = false, caption }: Props) {
  if (products.length === 0) {
    return <p className="muted">目前沒有商品。請先執行 python -m app.seed 建立示範資料。</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">代碼</th>
            <th scope="col">商品</th>
            <th scope="col">分類</th>
            <th scope="col" className="num">每公斤單價</th>
            <th scope="col" className="num">庫存</th>
            {showAdminColumns ? (
              <>
                <th scope="col" className="num">單次重量範圍</th>
                <th scope="col">狀態</th>
              </>
            ) : (
              <th scope="col">營養摘要</th>
            )}
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <tr key={p.id}>
              <td>{p.product_code}</td>
              <th scope="row">{p.name}</th>
              <td>{categoryLabel(p.category)}</td>
              <td className="num">{formatPrice(p.price_per_kg)}</td>
              <td className="num">{formatWeight(p.stock_grams)}</td>
              {showAdminColumns ? (
                <>
                  <td className="num">
                    {p.min_weight_grams}–{p.max_weight_grams} 公克
                  </td>
                  <td>{p.is_active ? "上架中" : "已下架"}</td>
                </>
              ) : (
                <td>
                  {p.nutrition.summary ?? "—"}
                  {p.nutrition.per_100g?.sodium_mg !== undefined && (
                    <span className="muted small">
                      {" "}
                      （每 100 公克鈉 {p.nutrition.per_100g.sodium_mg} 毫克）
                    </span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
