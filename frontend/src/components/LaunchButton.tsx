import { Play, Square, Loader2 } from "lucide-react";
import { useState } from "react";

interface LaunchButtonProps {
  status: "running" | "stopped";
  onLaunch: () => Promise<void>;
  onStop: () => Promise<void>;
}

export function LaunchButton({ status, onLaunch, onStop }: LaunchButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setLoading(true);
    setError(null);
    try {
      if (status === "running") {
        await onStop();
      } else {
        await onLaunch();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Action failed";
      setError(msg);
      console.error("Action failed:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <button disabled className="btn-secondary opacity-60 cursor-not-allowed flex items-center gap-1.5" aria-live="polite">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>{status === "running" ? "Stopping…" : "Launching…"}</span>
      </button>
    );
  }

  if (status === "running") {
    return (
      <button
        onClick={handleClick}
        className="btn-danger flex items-center gap-1.5"
        aria-label={`Stop profile (currently running)`}
      >
        <Square className="h-3.5 w-3.5" />
        <span>Stop</span>
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={handleClick}
        className="btn-primary flex items-center gap-1.5"
        aria-label="Launch profile"
      >
        <Play className="h-3.5 w-3.5" />
        <span>Launch</span>
      </button>
      {error && <p className="text-red-400 text-xs mt-1 text-right" role="alert">{error}</p>}
    </div>
  );
}
