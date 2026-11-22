import { useEffect, useState } from "react";
import { fetchResident } from "./api/client";
import type { Resident } from "./api/types";
import AdminAudit from "./components/AdminAudit";
import AdminOrders from "./components/AdminOrders";
import AdminInventory from "./components/AdminInventory";
import ConnectionStatus from "./components/ConnectionStatus";
import Loading from "./components/Loading";
import LoginForm from "./components/LoginForm";
import ResidentView from "./components/ResidentView";

type Tab = "resident" | "admin";
const SESSION_KEY = "csg.residentId";

export default function App() {
  const [tab, setTab] = useState<Tab>("resident");
  const [resident, setResident] = useState<Resident | null>(null);
  const [restoring, setRestoring] = useState(true);

  // Restore the demo session after a page refresh (id only; no credentials stored).
  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (!saved) {
      setRestoring(false);
      return;
    }
    fetchResident(Number(saved))
      .then(setResident)
      .catch(() => sessionStorage.removeItem(SESSION_KEY))
      .finally(() => setRestoring(false));
  }, []);

  function handleLogin(r: Resident) {
    sessionStorage.setItem(SESSION_KEY, String(r.resident_id));
    setResident(r);
  }

  function handleLogout() {
    sessionStorage.removeItem(SESSION_KEY);
    setResident(null);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <h1>社區智慧生鮮超市</h1>
          <span className="tagline">課堂展示</span>
        </div>
        <nav aria-label="主要功能" className="tabs">
          <button
            type="button"
            aria-current={tab === "resident" ? "page" : undefined}
            onClick={() => setTab("resident")}
          >
            居民
          </button>
          <button
            type="button"
            aria-current={tab === "admin" ? "page" : undefined}
            onClick={() => setTab("admin")}
          >
            管理
          </button>
        </nav>
      </header>

      <main className="content">
        {tab === "admin" ? (
          <>
            <AdminInventory />
            <AdminOrders />
            <AdminAudit />
          </>
        ) : restoring ? (
          <Loading />
        ) : resident ? (
          <ResidentView resident={resident} onLogout={handleLogout} />
        ) : (
          <LoginForm onLogin={handleLogin} />
        )}
      </main>

      <ConnectionStatus />
    </div>
  );
}
