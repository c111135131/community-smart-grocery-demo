import { useRef, useState, type FormEvent } from "react";
import { ApiError, askNutritionAssistant } from "../api/client";
import type { NutritionResponse } from "../api/types";
import { EXAMPLE_QUESTIONS, providerLabel, toolLabel } from "../labels";

const MAX_QUESTION = 500;
const BASKET_QUESTION = "依照我目前的購物籃和飲食偏好，推薦店內適合搭配補買的商品。";

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
  const sourcesPanel = useRef<HTMLDetailsElement>(null);

  async function ask(q: string) {
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askNutritionAssistant(residentId, q));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "助理暫時無法回答，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(question.trim());
  }

  return (
    <section className="panel" aria-labelledby="nutrition-title">
      <h2 id="nutrition-title">營養助理</h2>
      <p className="muted">
        可依飲食偏好查詢商品營養，也可以根據目前購物籃推薦店內適合搭配的食材。
      </p>

      <form onSubmit={submit} className="ask-form">
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
      <div className="assistant-actions">
        <button
          type="button"
          className="secondary"
          disabled={busy}
          onClick={() => {
            setQuestion(BASKET_QUESTION);
            void ask(BASKET_QUESTION);
          }}
        >
          購物籃推薦
        </button>
        <details className="assistant-examples">
          <summary>提問範例</summary>
          <div>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button key={q} type="button" className="link chip" onClick={() => setQuestion(q)}>
                {q}
              </button>
            ))}
          </div>
        </details>
      </div>

      {error && <p role="alert" className="field-error">{error}</p>}

      {result && (
        <div className="result" role="status" aria-live="polite">
          {result.notice && <p className="note">{result.notice}</p>}

          {result.basket_items && (
            <p className="note">
              本次使用的購物籃：
              {result.basket_items.map((item) => `${item.name} ${item.weight_grams} 公克`).join("、") || "空籃"}
            </p>
          )}
          <div className="answer">
            {result.answer.split(/(\*\*[^*\n]+\*\*|\[[\w-]+\])/g).map((part, index) => {
              if (part.startsWith("**") && part.endsWith("**")) {
                return <strong key={index}>{part.slice(2, -2)}</strong>;
              }
              const sourceIndex = part.startsWith("[")
                ? result.source_details.findIndex((source) => source.id === part.slice(1, -1))
                : -1;
              if (sourceIndex < 0) return part;
              const sourceId = `nutrition-source-${sourceIndex}`;
              return (
                <a
                  key={index}
                  className="source-link"
                  href={`#${sourceId}`}
                  aria-label={`參考來源 ${sourceIndex + 1}`}
                  onClick={() => {
                    if (sourcesPanel.current) sourcesPanel.current.open = true;
                    const source = document.getElementById(sourceId);
                    if (source instanceof HTMLDetailsElement) source.open = true;
                  }}
                >
                  [{sourceIndex + 1}]
                </a>
              );
            })}
          </div>

          {result.recommended_products.length > 0 && (
            <>
              <h3>{result.basket_items ? "推薦補買商品" : "推薦商品（由後端依營養數據決定）"}</h3>
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

          <details className="disclosure" ref={sourcesPanel}>
            <summary>參考來源（{result.source_details.length}）</summary>
            {result.source_details.length === 0 ? (
              <p className="muted small">這次回答沒有引用知識庫片段。</p>
            ) : (
              <ol className="sources">
                {result.source_details.map((source, index) => (
                  <li key={source.id}>
                    <details id={`nutrition-source-${index}`}>
                      <summary>{source.title}</summary>
                      <p className="small">{source.text}</p>
                    </details>
                  </li>
                ))}
              </ol>
            )}
          </details>

          <details className="disclosure">
            <summary>回答與資料使用資訊</summary>
            <p className="provider-line">
              回答提供者：<span className={`badge badge-${result.provider}`}>{providerLabel(result.provider)}</span>
            </p>
            {(result.provider === "anthropic" || result.provider === "gemini") && (
              <p className="muted small">
                外部 LLM 會收到問題、飲食偏好、過敏原、最近購買的商品名稱與營養事實。
                {result.basket_items && "購物籃推薦也會傳送籃中商品名稱與重量。"}
                傳送資料不含姓名、卡號、價格與庫存數量。
              </p>
            )}
            {result.tool_calls.length > 0 && <>
              <p className="small">助理使用的唯讀工具（{result.tool_calls.length} 次呼叫）</p>
              <ul className="plain small">
                {result.tool_calls.map((t, i) => (
                  <li key={i}>
                    {toolLabel(t.name)} → {t.result_count} 筆
                    <span className="mono muted"> {JSON.stringify(t.arguments)}</span>
                  </li>
                ))}
              </ul>
            </>}
          </details>
        </div>
      )}
    </section>
  );
}
