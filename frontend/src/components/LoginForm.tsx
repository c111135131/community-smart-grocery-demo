import { useState, type FormEvent } from "react";
import { ApiError, loginWithCard } from "../api/client";
import type { Resident } from "../api/types";

interface Props {
  onLogin: (resident: Resident) => void;
}

const DEMO_CARDS = ["CARD-1001", "CARD-1002"];

/** Demo card login: typing a card ID simulates tapping an NFC card (not real authentication). */
export default function LoginForm({ onLogin }: Props) {
  const [cardId, setCardId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await loginWithCard(cardId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登入失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel login-panel" aria-labelledby="login-title">
      <h2 id="login-title">居民登入</h2>
      <p className="muted">請輸入社區識別卡號（模擬感應刷卡）。</p>
      <form onSubmit={(e) => void submit(e)} className="login-form">
        <label htmlFor="card-id">識別卡號</label>
        <input
          id="card-id"
          value={cardId}
          onChange={(e) => setCardId(e.target.value)}
          placeholder="例如 CARD-1001"
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "login-error" : undefined}
        />
        <button type="submit" disabled={busy || cardId.trim() === ""}>
          {busy ? "登入中…" : "登入"}
        </button>
      </form>
      {error && (
        <p id="login-error" role="alert" className="field-error">
          {error}
        </p>
      )}
      <p className="muted small">
        示範卡號：
        {DEMO_CARDS.map((c) => (
          <button key={c} type="button" className="link chip" onClick={() => setCardId(c)}>
            {c}
          </button>
        ))}
      </p>
    </section>
  );
}
