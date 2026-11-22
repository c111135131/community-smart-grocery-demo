/** A load failure with a retry button, so the user is never stuck on a dead end. */
export default function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="field-error load-error">
      <span>{message}</span>
      <button type="button" className="secondary" onClick={onRetry}>
        重試
      </button>
    </div>
  );
}
