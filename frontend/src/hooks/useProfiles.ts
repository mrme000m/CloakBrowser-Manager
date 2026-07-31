import { useCallback, useEffect, useState } from "react";
import { api, type Profile, type ProfileCreateData, type BulkResultResponse } from "../lib/api";

export function useProfiles() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listProfiles();
      setProfiles(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch profiles");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Poll for status changes every 3 seconds
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
  }, [refresh]);

  const create = useCallback(
    async (data: ProfileCreateData): Promise<Profile | undefined> => {
      try {
        const profile = await api.createProfile(data);
        setProfiles((prev) => [profile, ...prev]);
        return profile;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create profile");
      }
    },
    [],
  );

  const update = useCallback(
    async (id: string, data: Partial<ProfileCreateData>) => {
      try {
        const profile = await api.updateProfile(id, data);
        setProfiles((prev) => prev.map((p) => (p.id === id ? profile : p)));
        return profile;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update profile");
      }
    },
    [],
  );

  const remove = useCallback(
    async (id: string) => {
      try {
        await api.deleteProfile(id);
        setProfiles((prev) => prev.filter((p) => p.id !== id));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete profile");
      }
    },
    [],
  );

  const launch = useCallback(
    async (id: string) => {
      try {
        const result = await api.launchProfile(id);
        await refresh();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to launch profile");
      }
    },
    [refresh],
  );

  const stop = useCallback(
    async (id: string) => {
      try {
        await api.stopProfile(id);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to stop profile");
      }
    },
    [refresh],
  );

  /** Duplicate a profile (new random device identity). Returns the clone. */
  const clone = useCallback(
    async (id: string, name?: string): Promise<Profile | undefined> => {
      try {
        const profile = await api.cloneProfile(id, name);
        setProfiles((prev) => [profile, ...prev]);
        return profile;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to duplicate profile");
      }
    },
    [],
  );

  /** Bulk launch by ids or by tag ("launch all tagged X"). */
  const bulkLaunch = useCallback(
    async (body: { ids?: string[]; tag?: string }): Promise<BulkResultResponse | undefined> => {
      try {
        const res = await api.bulkLaunch(body);
        await refresh();
        return res;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Bulk launch failed");
      }
    },
    [refresh],
  );

  const bulkStop = useCallback(
    async (body: { ids?: string[]; tag?: string }): Promise<BulkResultResponse | undefined> => {
      try {
        const res = await api.bulkStop(body);
        await refresh();
        return res;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Bulk stop failed");
      }
    },
    [refresh],
  );

  const bulkDelete = useCallback(
    async (body: { ids?: string[]; tag?: string }): Promise<BulkResultResponse | undefined> => {
      try {
        const res = await api.bulkDelete(body);
        await refresh();
        return res;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Bulk delete failed");
      }
    },
    [refresh],
  );

  return {
    profiles, loading, error, refresh,
    create, update, remove, launch, stop,
    clone, bulkLaunch, bulkStop, bulkDelete,
  };
}
