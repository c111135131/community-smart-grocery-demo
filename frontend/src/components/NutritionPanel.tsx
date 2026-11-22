import { useState, type FormEvent } from "react";
import { ApiError, askNutritionAssistant } from "../api/client";
import type { NutritionResponse } from "../api/types";
import { EXAMPLE_QUESTIONS, providerLabel, toolLabel } from "../labels";

const MAX_QUESTION = 500;

/**
 * Nutrition assistant. The backend decides which products to recommend (from database
 * nutrition numbers and the resident's preferences); the AI only phrases the answer.
 * It is read-only and works without any API key (mock provider by default).
 */
export default function NutritionPanel({ residentId }: { residentId: number }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<NutritionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await askNutritionAssistant(residentId, q));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "助理暫時無法回答，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="nutrition-title">
      <h2 id="nutrition-title">營養助理</h2>
      <p className="muted">
        依據您的飲食偏好、商品營養資料與知識庫回答。預設使用本地 mock，不需要任何 API key。
        助理只能提供資訊，價格、庫存與結帳都由後端系統決定，AI 無法修改。
      </p>

      <form onSubmit={(e) => void submit(e)} className="ask-form">
        <label htmlFor="nutrition-q">您的問題</label>
        <div className="ask-row">
          <input
            id="nutrition-q"
            value={question}
            maxLength={MAX_QUESTION}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="例如：請推薦適合我的低鈉食材"
            autoComplete="off"
          />
          <button type="submit" disabled={busy || question.trim() === ""}>
            {busy ? "思考中…" : "詢問助理"}
          </button>
        </div>
      </form>
      <p className="muted small">
        範例：
        {EXAMPLE_QUESTIONS.map((q) => (
          <button key={q} type="button" className="link chip" onClick={() => setQuestion(q)}>
            {q}
          </button>
        ))}
      </p>

      {error && <p role="alert" className="field-error">{error}</p>}

      {result && (
        <div className="result" role="status" aria-live="polite">
          <p className="provider-line">
            回答提供者：<span className={`badge badge-${result.provider}`}>{providerLabel(result.provider)}</span>
          </p>
          {result.notice && <p className="note">{result.notice}</p>}
          {result.provider === "anthropic" && (
            <p className="note">
              已將您的飲食偏好、過敏原、最近購買的商品名稱與營養事實送至外部 LLM；
              不含姓名、卡號、價格與庫存數量。
            </p>
          )}

          <div className="answer">{result.answer}</div>

          {result.recommended_products.length > 0 && (
            <>
              <h3>推薦商品（由後端依營養數據決定）</h3>
              <ul className="rec-list">
                {result.recommended_products.map((p) => (
                  <li key={p.product_code}>
                    <strong>{p.name}</strong>
                    <span className="muted small"> {p.reasons.join("；")}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h3>參考來源</h3>
          {result.source_details.length === 0 ? (
            <p className="muted small">這次回答沒有引用知識庫片段。</p>
          ) : (
            <ul className="plain sources">
              {result.source_details.map((s) => (
                <li key={s.id}>
                  <details>
                    <summary>
                      <span className="mono">{s.id}</span> · {s.title}
                    </summary>
                    <p className="small">{s.text}</p>
                  </details>
                </li>
              ))}
            </ul>
          )}

          {result.tool_calls.length > 0 && (
            <details className="attack">
              <summary>助理使用的唯讀工具（{result.tool_calls.length} 次呼叫）</summary>
              <ul className="plain small">
                {result.tool_calls.map((t, i) => (
                  <li key={i}>
                    {toolLabel(t.name)} → {t.result_count} 筆
                    <span className="mono muted"> {JSON.stringify(t.arguments)}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
