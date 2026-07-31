import { useState, useCallback, useEffect } from "react";
import { Lock, PanelLeftClose, PanelLeft, Shield, Server, Shuffle } from "lucide-react";
import { useProfiles } from "./hooks/useProfiles";
import { useProxyCredentials } from "./hooks/useProxyCredentials";
import { useProxyGroups } from "./hooks/useProxyGroups";
import { api, setOnUnauthorized, type ProfileCreateData } from "./lib/api";
import { ProfileList } from "./components/ProfileList";
import { ProfileForm } from "./components/ProfileForm";
import { ProfileViewer } from "./components/ProfileViewer";
import { LaunchButton } from "./components/LaunchButton";
import { StatusIndicator } from "./components/StatusIndicator";
import { LoginPage } from "./components/LoginPage";
import { ProxyCredentialsManager } from "./components/ProxyCredentialsManager";
import { ProxyProvidersManager } from "./components/ProxyProvidersManager";
import { ProxyGroupsManager } from "./components/ProxyGroupsManager";

type AuthState = "checking" | "required" | "ok" | "error";
type View = "empty" | "create" | "edit" | "view";

export default function App() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [authRequired, setAuthRequired] = useState(false);

  useEffect(() => {
    setOnUnauthorized(() => setAuthState("required"));

    api.authStatus()
      .then(({ auth_required, authenticated }) => {
        setAuthRequired(auth_required);
        if (!auth_required || authenticated) {
          setAuthState("ok");
        } else {
          setAuthState("required");
        }
      })
      .catch((err) => {
        console.warn("[auth] status check failed:", err);
        setAuthState("error");
      });

    return () => setOnUnauthorized(null);
  }, []);

  if (authState === "checking") {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  if (authState === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-0">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Unable to reach the server</p>
          <button
            onClick={() => {
              setAuthState("checking");
              api.authStatus()
                .then(({ auth_required, authenticated }) => {
                  setAuthRequired(auth_required);
                  setAuthState(!auth_required || authenticated ? "ok" : "required");
                })
                .catch(() => setAuthState("error"));
            }}
            className="text-xs text-gray-400 hover:text-gray-200 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (authState === "required") {
    return <LoginPage onSuccess={() => setAuthState("ok")} />;
  }

  return (
    <AppContent
      authRequired={authRequired}
      onLogout={async () => {
        await api.logout();
        setAuthState("required");
      }}
    />
  );
}

interface AppContentProps {
  authRequired: boolean;
  onLogout: () => void;
}

function AppContent({ authRequired, onLogout }: AppContentProps) {
  const { profiles, loading, error, create, update, remove, launch, stop, clone, bulkLaunch, bulkStop, bulkDelete } = useProfiles();
  const { credentials: proxyCredentials } = useProxyCredentials();
  const { groups: proxyGroups } = useProxyGroups();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("empty");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [proxyManagerOpen, setProxyManagerOpen] = useState(false);
  const [proxyProviderManagerOpen, setProxyProviderManagerOpen] = useState(false);
  const [proxyGroupManagerOpen, setProxyGroupManagerOpen] = useState(false);
  const [maxRunning, setMaxRunning] = useState<number | null>(null);

  const selected = profiles.find((p) => p.id === selectedId) ?? null;

  // Poll system status for the running-cap (MAX_RUNNING_PROFILES), if configured.
  useEffect(() => {
    let active = true;
    const poll = () => api.getStatus().then((s) => { if (active) setMaxRunning(s.max_running ?? null); }).catch(() => {});
    poll();
    const interval = setInterval(poll, 5000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    const profile = profiles.find((p) => p.id === id);
    setView(profile?.status === "running" ? "view" : "edit");
  }, [profiles]);

  const handleNew = useCallback(() => {
    setSelectedId(null);
    setView("create");
  }, []);

  const handleCreate = useCallback(async (data: ProfileCreateData) => {
    const profile = await create(data);
    if (profile) {
      setSelectedId(profile.id);
      setView("edit");
    }
  }, [create]);

  const handleUpdate = useCallback(async (data: ProfileCreateData) => {
    if (!selectedId) return;
    await update(selectedId, data);
  }, [selectedId, update]);

  const handleDelete = useCallback(async () => {
    if (!selectedId) return;
    await remove(selectedId);
    setSelectedId(null);
    setView("empty");
  }, [selectedId, remove]);

  const handleLaunch = useCallback(async () => {
    if (!selectedId) return;
    const result = await launch(selectedId);
    if (result) setView("view");
  }, [selectedId, launch]);

  const handleStop = useCallback(async () => {
    if (!selectedId) return;
    await stop(selectedId);
    setView("edit");
  }, [selectedId, stop]);

  const handleDuplicate = useCallback(async (id: string) => {
    const profile = await clone(id);
    if (profile) {
      setSelectedId(profile.id);
      setView("edit");
    }
  }, [clone]);

  const handleBulkLaunch = useCallback(async (ids: string[]) => {
    await bulkLaunch({ ids });
  }, [bulkLaunch]);

  const handleBulkStop = useCallback(async (ids: string[]) => {
    await bulkStop({ ids });
  }, [bulkStop]);

  const handleBulkDelete = useCallback(async (ids: string[]) => {
    await bulkDelete({ ids });
    // Clear selection if the deleted set included the selected profile.
    if (selectedId && ids.includes(selectedId)) {
      setSelectedId(null);
      setView("empty");
    }
  }, [bulkDelete, selectedId]);

  const handleVncDisconnect = useCallback(() => {
    setView("edit");
  }, []);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r border-border bg-surface-1 flex-shrink-0 flex flex-col">
          <ProfileList
            profiles={profiles}
            selectedId={selectedId}
            onSelect={handleSelect}
            onNew={handleNew}
            onDuplicate={handleDuplicate}
            onBulkLaunch={handleBulkLaunch}
            onBulkStop={handleBulkStop}
            onBulkDelete={handleBulkDelete}
            maxRunning={maxRunning}
          />
          {/* Proxy management buttons */}
          <div className="p-3 border-t border-border space-y-2">
            <button
              onClick={() => setProxyManagerOpen(true)}
              className="btn-secondary w-full flex items-center justify-center gap-1.5 text-xs"
              title="Manage proxy credentials"
            >
              <Shield className="h-3 w-3" />
              <span>Proxy Credentials</span>
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => setProxyProviderManagerOpen(true)}
                className="btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs"
                title="Manage proxy providers (IPVanish, ...)"
              >
                <Server className="h-3 w-3" />
                <span>Providers</span>
              </button>
              <button
                onClick={() => setProxyGroupManagerOpen(true)}
                className="btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs"
                title="Manage proxy rotation groups"
              >
                <Shuffle className="h-3 w-3" />
                <span>Groups</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-500 hover:text-gray-300 p-1"
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </button>
            {selected && (
              <div className="flex items-center gap-2">
                <StatusIndicator status={selected.status} size="md" />
                <span className="text-sm font-medium">{selected.name}</span>
                <span className="text-xs text-gray-500 capitalize">{selected.platform}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {maxRunning !== null && (
              <span className="text-xs text-gray-500" title="Running profiles / max allowed">
                {profiles.filter((p) => p.status === "running").length}/{maxRunning}
              </span>
            )}
            {selected && (
              <LaunchButton
                status={selected.status}
                onLaunch={handleLaunch}
                onStop={handleStop}
              />
            )}
            {authRequired && (
              <button
                onClick={onLogout}
                className="text-gray-500 hover:text-gray-300 p-1"
                title="Log out"
              >
                <Lock className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {view === "empty" && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-gray-500 text-sm">Select a profile or create a new one</p>
              </div>
            </div>
          )}

          {view === "create" && (
            <ProfileForm
              profile={null}
              proxyCredentials={proxyCredentials}
              proxyGroups={proxyGroups}
              onSave={handleCreate}
              onCancel={() => setView("empty")}
            />
          )}

          {view === "edit" && selected && (
            <ProfileForm
              profile={selected}
              proxyCredentials={proxyCredentials}
              proxyGroups={proxyGroups}
              onSave={handleUpdate}
              onDelete={handleDelete}
              onCancel={() => {
                setSelectedId(null);
                setView("empty");
              }}
            />
          )}

          {view === "view" && selected && selected.status === "running" && (
            <ProfileViewer
              key={selected.id}
              profileId={selected.id}
              cdpUrl={selected.cdp_url}
              cdpEndpoint={selected.cdp_endpoint}
              clipboardSync={selected.clipboard_sync}
              authRequired={authRequired}
              onDisconnect={handleVncDisconnect}
            />
          )}
        </div>
      </div>

      {/* Proxy Credentials Manager Modal */}
      <ProxyCredentialsManager
        open={proxyManagerOpen}
        onClose={() => setProxyManagerOpen(false)}
      />

      {/* Proxy Providers Manager Modal */}
      <ProxyProvidersManager
        open={proxyProviderManagerOpen}
        onClose={() => setProxyProviderManagerOpen(false)}
      />

      {/* Proxy Groups Manager Modal */}
      <ProxyGroupsManager
        open={proxyGroupManagerOpen}
        onClose={() => setProxyGroupManagerOpen(false)}
      />
    </div>
  );
}
