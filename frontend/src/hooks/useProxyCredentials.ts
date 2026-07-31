import { useCallback, useEffect, useState } from "react";
import { api, type ProxyCredential, type ProxyCredentialData } from "../lib/api";

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

  return { credentials, loading, error, refresh, create, update, remove };
}
