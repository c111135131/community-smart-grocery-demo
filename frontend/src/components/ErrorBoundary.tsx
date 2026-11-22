import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

/** Last line of defence: an unexpected rendering error shows a recoverable message, not a blank page. */
export default class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="boundary" role="alert">
        <h1>畫面發生未預期的錯誤</h1>
        <p>請重新整理頁面。如果問題持續發生，請確認後端仍在運作，並查看瀏覽器的主控台訊息。</p>
        <button type="button" onClick={() => window.location.reload()}>
          重新整理頁面
        </button>
      </div>
    );
  }
}
