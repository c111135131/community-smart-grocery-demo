import type { CartEventResult } from "../api/types";
import { PACKET_FIELDS, VALIDATION_STEPS, rejectionLabel } from "../labels";

function stepState(v: boolean | null | undefined) {
  if (v === true) return { text: "✓ 通過", cls: "step-pass" };
  if (v === false) return { text: "✗ 失敗", cls: "step-fail" };
  return { text: "— 未執行", cls: "step-skip" };
}

/** Packet hex, field breakdown and per-step validation of one gateway result. */
export default function PacketResult({ result }: { result: CartEventResult }) {
  const hex = result.packet_hex;
  const wellFormed = hex.length === 32;
  const p = result.packet;
  const fieldValue: Record<string, string> = p
    ? {
        "裝置 ID": String(p.device_id),
        "序號": String(p.sequence_number),
        "指令": p.command,
        "商品代碼": String(p.product_code),
        "重量（公克）": String(p.weight_grams),
        Flags: String(p.flags),
      }
    : {};

  return (
    <div className="result" role="status" aria-live="polite">
      <div className={result.accepted ? "banner banner-ok" : "banner banner-bad"}>
        <strong>{result.accepted ? "✓ 封包已接受，購物車已更新" : "✗ 封包被拒絕，購物車未變更"}</strong>
        {!result.accepted && result.rejection_code && (
          <span>
            {rejectionLabel(result.rejection_code)}
            {result.rejection_reason && (
              <span className="muted small">（{result.rejection_reason}）</span>
            )}
          </span>
        )}
        <span className="muted small">事件 {result.event_id} · {result.transport}</span>
      </div>

      <h3>封包（十六進位，{hex.length / 2} bytes）</h3>
      <p className="hex" aria-label="封包十六進位內容">
        {wellFormed
          ? PACKET_FIELDS.map((f, i) => (
              <span key={f.name} className={`hexseg seg-${i % 3}`} title={f.name}>
                {hex.slice(f.from * 2, f.to * 2)}
              </span>
            ))
          : hex}
      </p>

      {wellFormed && (
        <div className="table-wrap">
          <table className="compact">
            <caption className="sr-only">封包欄位拆解</caption>
            <thead>
              <tr><th scope="col">欄位</th><th scope="col">位元組</th><th scope="col">十六進位</th><th scope="col">數值</th></tr>
            </thead>
            <tbody>
              {PACKET_FIELDS.map((f) => (
                <tr key={f.name}>
                  <th scope="row">{f.name}</th>
                  <td>{f.from}–{f.to - 1}</td>
                  <td className="mono">{hex.slice(f.from * 2, f.to * 2)}</td>
                  <td>{fieldValue[f.name] ?? (p ? "—" : "未解析")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!wellFormed && <p className="muted small">長度不是 16 bytes，無法拆解欄位。</p>}

      <h3>驗證結果</h3>
      <ol className="steps">
        {VALIDATION_STEPS.map((s) => {
          const st = stepState(result.validation[s.key as keyof typeof result.validation]);
          return (
            <li key={s.key}>
              <span className={st.cls}>{st.text}</span> {s.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
