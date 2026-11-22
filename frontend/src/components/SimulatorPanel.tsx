import { useEffect, useState, type FormEvent } from "react";
import { ApiError, sendRawPacket, sendSimulatedEvent } from "../api/client";
import type { CartEventResult, CommandName, Product } from "../api/types";
import { COMMAND_LABELS, tamperHex } from "../labels";
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
  const [rawHex, setRawHex] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (productCode === null && products.length > 0) setProductCode(products[0].product_code);
  }, [products, productCode]);

  async function run(action: () => Promise<CartEventResult>) {
    setBusy(true);
    setError(null);
    try {
      const r = await action();
      setResult(r);
      setRawHex(r.packet_hex);
      onResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "送出失敗，請稍後再試");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (productCode === null) return;
    const grams = Number(weight);
    if (!Number.isInteger(grams) || grams < 0) {
      setError("重量必須是 0 以上的整數（公克）");
      return;
    }
    void run(() =>
      sendSimulatedEvent(residentId, {
        device_id: DEMO_DEVICE_ID,
        command,
        product_code: productCode,
        weight_grams: grams,
      }),
    );
  }

  return (
    <section className="panel" aria-labelledby="sim-title">
      <h2 id="sim-title">IoT 智慧秤模擬器</h2>
      <p className="muted">
        模擬智慧秤產生 16-byte 封包，經<strong>軟體模擬</strong>的 Matter-over-Thread 傳輸送到 Gateway
        驗證後才會更新購物車。本專案沒有真實 Thread 網路或硬體；檢查碼為教學用途，非密碼學安全。
      </p>

      <form onSubmit={submit} className="sim-form">
        <div className="field">
          <label htmlFor="sim-command">指令</label>
          <select id="sim-command" value={command} onChange={(e) => setCommand(e.target.value as CommandName)}>
            {COMMANDS.map((c) => <option key={c} value={c}>{COMMAND_LABELS[c]}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sim-product">商品</label>
          <select
            id="sim-product"
            value={productCode ?? ""}
            onChange={(e) => setProductCode(Number(e.target.value))}
          >
            {products.map((p) => (
              <option key={p.id} value={p.product_code}>{p.name}（{p.product_code}）</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sim-weight">重量（公克）</label>
          <input
            id="sim-weight"
            inputMode="numeric"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
          />
        </div>
        <button type="submit" disabled={busy || productCode === null}>
          {busy ? "送出中…" : "送出封包"}
        </button>
      </form>

      {error && <p role="alert" className="field-error">{error}</p>}

      {result && (
        <>
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
        </>
      )}
    </section>
  );
}
