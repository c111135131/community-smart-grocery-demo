import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchDevices, fetchIotEvents } from "../api/client";
import type { Device, IotEvent } from "../api/types";
import LoadError from "./LoadError";
import Loading from "./Loading";

/** Demo admin view: gateway audit trail and per-device sequence state. */
export default function AdminAudit() {
  const [events, setEvents] = useState<IotEvent[] | null>(null);
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [e, d] = await Promise.all([fetchIotEvents(50), fetchDevices()]);
      setEvents(e);
      setDevices(d);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "載入稽核資料失敗");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel" aria-labelledby="audit-title">
      <div className="panel-head">
        <h2 id="audit-title">IoT Gateway 稽核（管理）</h2>
        <button type="button" className="secondary" onClick={() => void load()}>重新整理</button>
      </div>
      <p className="muted">每個到達 Gateway 的封包都會留下紀錄，包含被拒絕的封包。</p>
      {error && <LoadError message={error} onRetry={() => void load()} />}

      {devices && (
        <ul className="plain">
          {devices.map((d) => (
            <li key={d.id}>
              裝置 {d.id}（{d.device_code}）：最後接受序號{" "}
              <b>{d.last_sequence_number < 0 ? "尚無" : d.last_sequence_number}</b>
            </li>
          ))}
        </ul>
      )}

      {!error && events === null && <Loading />}
      {events && events.length === 0 && <p className="muted">尚無事件。請先到居民頁送出封包。</p>}
      {events && events.length > 0 && (
        <div className="table-wrap">
          <table className="compact">
            <caption className="sr-only">IoT 事件稽核紀錄</caption>
            <thead>
              <tr>
                <th scope="col">事件</th><th scope="col">時間</th><th scope="col">序號</th>
                <th scope="col">指令</th><th scope="col">商品</th><th scope="col" className="num">重量(g)</th>
                <th scope="col">結果</th><th scope="col">原因</th><th scope="col">封包</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <th scope="row">{e.event_id}</th>
                  <td>{new Date(e.created_at).toLocaleTimeString("zh-TW")}</td>
                  <td>{e.sequence_number ?? "—"}</td>
                  <td>{e.command ?? "—"}</td>
                  <td>{e.product_code ?? "—"}</td>
                  <td className="num">{e.weight_grams ?? "—"}</td>
                  <td className={e.validation_status === "ACCEPTED" ? "ok" : "bad"}>
                    {e.validation_status === "ACCEPTED" ? "✓ 接受" : "✗ 拒絕"}
                  </td>
                  <td>{e.rejection_reason ?? ""}</td>
                  <td className="mono small">{e.packet_hex}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
