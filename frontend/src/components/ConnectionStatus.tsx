import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { HealthResponse } from "../api/types";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

/** Small footer indicator kept from Phase 0: backend + PostgreSQL connectivity. */
export default function ConnectionStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const check = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ok", data: await fetchHealth() });
    } catch (e) {
      setState({ kind: "error", message: e instanceof Error ? e.message : "無法連線" });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <footer className="conn">
      {state.kind === "loading" && <span role="status">檢查連線中…</span>}
      {state.kind === "error" && (
        <span role="alert" className="bad">
          後端離線：{state.message}。請確認服務已啟動（docker compose up，或 uvicorn app.main:app --port 8000）。
        </span>
      )}
      {state.kind === "ok" && (
        <span>
          後端 <b className="ok">正常</b> · 資料庫{" "}
          {state.data.database === "ok" ? (
            <b className="ok">已連線</b>
          ) : (
            <b className="bad">未連線（請執行 docker compose up -d db）</b>
          )}
        </span>
      )}
      <button type="button" className="link" onClick={() => void check()}>
        重新檢查
      </button>
    </footer>
  );
}
