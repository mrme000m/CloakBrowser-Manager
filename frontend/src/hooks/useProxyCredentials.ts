import { useCallback, useEffect, useState } from "react";
import { api, type ProxyCredential, type ProxyCredentialData, type ProxyTestResult } from "../lib/api";

export function useProxyCredentials() {
  const [credentials, setCredentials] = useState<ProxyCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listProxyCredentials();
      setCredentials(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch credentials");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async (data: ProxyCredentialData) => {
    try {
      const cred = await api.createProxyCredential(data);
      setCredentials((prev) => [cred, ...prev]);
      return cred;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create credential");
    }
  }, []);

  const update = useCallback(async (id: string, data: Partial<ProxyCredentialData>) => {
    try {
      const cred = await api.updateProxyCredential(id, data);
      setCredentials((prev) => prev.map((c) => (c.id === id ? cred : c)));
      return cred;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update credential");
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await api.deleteProxyCredential(id);
      setCredentials((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete credential");
    }
  }, []);

  /** Test one credential through its proxy; updates that row in-place. */
  const test = useCallback(async (id: string): Promise<ProxyTestResult | undefined> => {
    try {
      const result = await api.testProxyCredential(id);
      setCredentials((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                last_status: result.ok ? "ok" : "failed",
                last_exit_ip: result.exit_ip,
                last_country: result.country,
                last_checked_at: new Date().toISOString(),
              }
            : c,
        ),
      );
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Proxy test failed");
    }
  }, []);

  /** Test every credential; refreshes all rows. */
  const testAll = useCallback(async () => {
    try {
      await api.testAllProxyCredentials();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk proxy test failed");
    }
  }, [refresh]);

  return { credentials, loading, error, refresh, create, update, remove, test, testAll };
}
