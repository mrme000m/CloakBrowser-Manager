import { useCallback, useEffect, useState } from "react";
import { api, type ProxyGroup, type ProxyGroupData } from "../lib/api";

export function useProxyGroups() {
  const [groups, setGroups] = useState<ProxyGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listProxyGroups();
      setGroups(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch groups");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async (data: ProxyGroupData) => {
    try {
      const group = await api.createProxyGroup(data);
      setGroups((prev) => [group, ...prev]);
      return group;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create group");
    }
  }, []);

  const update = useCallback(async (id: string, data: Partial<ProxyGroupData>) => {
    try {
      const group = await api.updateProxyGroup(id, data);
      setGroups((prev) => prev.map((g) => (g.id === id ? group : g)));
      return group;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update group");
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await api.deleteProxyGroup(id);
      setGroups((prev) => prev.filter((g) => g.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete group");
    }
  }, []);

  /** Replace all members of a group; updates the local group object. */
  const setMembers = useCallback(async (id: string, credentialIds: string[]) => {
    try {
      const group = await api.setProxyGroupMembers(id, credentialIds);
      setGroups((prev) => prev.map((g) => (g.id === id ? group : g)));
      return group;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update group members");
    }
  }, []);

  const addMember = useCallback(async (groupId: string, credentialId: string) => {
    try {
      const group = await api.addProxyGroupMember(groupId, credentialId);
      setGroups((prev) => prev.map((g) => (g.id === groupId ? group : g)));
      return group;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add group member");
    }
  }, []);

  const removeMember = useCallback(async (groupId: string, credentialId: string) => {
    try {
      const group = await api.removeProxyGroupMember(groupId, credentialId);
      setGroups((prev) => prev.map((g) => (g.id === groupId ? group : g)));
      return group;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove group member");
    }
  }, []);

  return {
    groups, loading, error, refresh,
    create, update, remove,
    setMembers, addMember, removeMember,
  };
}
