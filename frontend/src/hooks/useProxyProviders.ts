import { useCallback, useEffect, useState } from "react";
import { api, type ProxyProvider, type ProxyProviderData, type ProxyLocations } from "../lib/api";

export function useProxyProviders() {
  const [providers, setProviders] = useState<ProxyProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listProxyProviders();
      setProviders(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch providers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async (data: ProxyProviderData) => {
    try {
      const provider = await api.createProxyProvider(data);
      setProviders((prev) => [provider, ...prev]);
      return provider;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create provider");
    }
  }, []);

  const update = useCallback(async (id: string, data: Partial<ProxyProviderData>) => {
    try {
      const provider = await api.updateProxyProvider(id, data);
      setProviders((prev) => prev.map((p) => (p.id === id ? provider : p)));
      return provider;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update provider");
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await api.deleteProxyProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete provider");
    }
  }, []);

  return { providers, loading, error, refresh, create, update, remove };
}

/** One-time fetch of the provider location catalog (IPVanish city codes, etc.). */
export function useProxyLocations() {
  const [locations, setLocations] = useState<ProxyLocations>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getProxyLocations()
      .then((data) => setLocations(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { locations, loading };
}
