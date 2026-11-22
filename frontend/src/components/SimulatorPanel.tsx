import { useState, type FormEvent } from "react";
import { ApiError, sendRawPacket, sendSimulatedEvent } from "../api/client";
import type { CartEventResult, CommandName, Product } from "../api/types";
import { categoryLabel, COMMAND_LABELS, formatPrice, formatWeight, rejectionLabel, tamperHex } from "../labels";
import PacketResult from "./PacketResult";

// The single seeded demo device (DEV-001). Its id is 1 on a freshly seeded database.
const DEMO_DEVICE_ID = 1;
const COMMANDS: CommandName[] = ["ADD_ITEM", "REMOVE_ITEM", "BIND_CARD", "CHECKOUT", "ALERT"];

interface Props {
  residentId: number;
  products: Product[];
  onResult: (result: CartEventResult) => void;
}

export default function SimulatorPanel({ residentId, products, onResult }: Props) {
  const [command, setCommand] = useState<CommandName>("ADD_ITEM");
  const [productCode, setProductCode] = useState<number | null>(null);
  const [weight, setWeight] = useState("300");
  const [result, setResult] = useState<CartEventResult | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [rawHex, setRawHex] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = products.find((p) => p.product_code === productCode)
    ?? products.find((p) => p.stock_grams > 0)
    ?? products[0];

  async function run(action: () => Promise<CartEventResult>, message = "") {
    setBusy(true);
    setError(null);
    setConfirmation("");
    try {
      const r = await action();
      setResult(r);
      setRawHex(r.packet_hex);
      onResult(r);
      if (r.accepted) setConfirmation(message || "購物籃已更新。");
      else setError(r.rejection_code ? rejectionLabel(r.rejection_code) : "購物籃更新失敗，請再試一次。");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "送出失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  function send(eventCommand: CommandName) {
    if (!selected || busy) return;
    const grams = Number(weight);
    if (!weight.trim() || !Number.isInteger(grams) || grams < 0) {
      setConfirmation("");
      setError("重量必須是 0 以上的整數（公克）");
      return;
    }
    void run(() =>
      sendSimulatedEvent(residentId, {
        device_id: DEMO_DEVICE_ID,
        command: eventCommand,
        product_code: selected.product_code,
        weight_grams: grams,
      }),
      eventCommand === "ADD_ITEM" ? `已加入${selected.name} ${formatWeight(grams)}` : "",
    );
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    send("ADD_ITEM");
  }

  return (
    <section className="panel" aria-labelledby="sim-title">
      <h2 id="sim-title">今日生鮮</h2>
      <p className="muted">選擇商品和重量，加入購物籃。</p>
      {products.length === 0 && <p className="muted">目前沒有上架商品。</p>}
      <form onSubmit={submit}>
        {selected && (
          <>
            <fieldset className="produce-grid" aria-label="可購買的生鮮商品">
              {products.map((p) => {
                const available = p.stock_grams > 0;
                return (
                  <label key={p.id} className="produce-option">
                    <input
                      type="radio"
                      name="produce"
                      checked={selected.product_code === p.product_code}
                      disabled={!available}
                      onChange={() => setProductCode(p.product_code)}
                    />
                    <span className="produce-card">
                      <span className="produce-meta">{categoryLabel(p.category)}</span>
                      <strong>{p.name}</strong>
                      <span>{available ? `${formatPrice(p.price_per_kg)}／公斤` : "暫時缺貨"}</span>
                    </span>
                  </label>
                );
              })}
            </fieldset>
            <div className="purchase-row">
              <div className="field">
                <label htmlFor="sim-weight">重量（公克）</label>
                <input id="sim-weight" inputMode="numeric" value={weight} onChange={(e) => setWeight(e.target.value)} />
              </div>
              <button type="submit" disabled={busy || selected.stock_grams <= 0}>
                {busy ? "處理中…" : "加入購物籃"}
              </button>
            </div>
          </>
        )}
      </form>

      {error && <p role="alert" className="field-error">{error}</p>}
      {confirmation && <p role="status" className="purchase-confirmation">{confirmation}</p>}

      <details className="disclosure">
        <summary>IoT 技術展示</summary>
        <p className="muted small">智慧秤與 Matter over Thread 傳輸以軟體模擬。驗證結果由 Gateway 提供。</p>
        {selected && (
          <div className="sim-form">
            <div className="field">
              <label htmlFor="sim-command">指令</label>
              <select id="sim-command" value={command} onChange={(e) => setCommand(e.target.value as CommandName)}>
                {COMMANDS.map((c) => <option key={c} value={c}>{COMMAND_LABELS[c]}</option>)}
              </select>
            </div>
            <button type="button" className="secondary" disabled={busy} onClick={() => send(command)}>
              執行展示指令
            </button>
          </div>
        )}
        {result && <>
          <PacketResult result={result} />
          <details className="attack">
            <summary>進階：重放與竄改封包演示</summary>
            <p className="muted small">
              直接把位元組送給 Gateway，觀察防重放序號與檢查碼如何拒絕不合法封包。
            </p>
            <div className="btn-row">
              <button type="button" className="secondary" disabled={busy}
                onClick={() => void run(() => sendRawPacket(residentId, result.packet_hex))}>
                重送相同封包（重放）
              </button>
              <button type="button" className="secondary" disabled={busy}
                onClick={() => void run(() => sendRawPacket(residentId, tamperHex(result.packet_hex)))}>
                竄改重量後送出
              </button>
            </div>
            <div className="field">
              <label htmlFor="raw-hex">自訂十六進位封包</label>
              <input id="raw-hex" className="mono" value={rawHex} onChange={(e) => setRawHex(e.target.value)} />
            </div>
            <button type="button" className="secondary" disabled={busy || rawHex.trim() === ""}
              onClick={() => void run(() => sendRawPacket(residentId, rawHex))}>
              送出此封包
            </button>
          </details>
        </>}
      </details>
    </section>
  );
}
