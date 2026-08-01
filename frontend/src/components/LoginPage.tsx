import { useState, type FormEvent } from "react";
import { Lock, Monitor } from "lucide-react";
import { api } from "../lib/api";

interface LoginPageProps {
  onSuccess: () => void;
}

export function LoginPage({ onSuccess }: LoginPageProps) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(token);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-surface-0 px-4">
      <div className="w-80">
        <div className="flex flex-col items-center mb-6">
          <div className="h-11 w-11 rounded-xl bg-accent/10 flex items-center justify-center mb-3 ring-1 ring-accent/20">
            <Monitor className="h-5 w-5 text-accent" />
          </div>
          <h1 className="text-lg font-semibold text-gray-100">
            CloakBrowser Manager
          </h1>
          <p className="text-xs text-gray-500 mt-1">Enter your access token</p>
        </div>
        <form onSubmit={handleSubmit}>
          <label htmlFor="access-token" className="sr-only">Access token</label>
          <input
            id="access-token"
            type="password"
            className="input mb-3"
            placeholder="Access token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            aria-invalid={!!error}
            aria-describedby={error ? "login-error" : undefined}
            autoFocus
          />
          {error && (
            <p id="login-error" role="alert" aria-live="assertive" className="text-red-400 text-xs mb-3">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !token}
            className="btn-primary w-full flex items-center justify-center gap-1.5"
          >
            {loading ? (
              <>
                <Lock className="h-3.5 w-3.5 animate-pulse" />
                <span>Authenticating…</span>
              </>
            ) : (
              <span>Unlock</span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
