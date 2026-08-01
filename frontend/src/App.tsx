import { useState, useCallback, useEffect } from "react";
import { Lock, PanelLeftClose, PanelLeft, Monitor, Plus, Shield, Server, Shuffle } from "lucide-react";
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

function FullScreenLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="h-screen flex flex-col items-center justify-center gap-3 bg-surface-0">
      <div className="spinner spinner-lg" role="status" aria-label={label} />
      <span className="text-gray-500 text-xs">{label}</span>
    </div>
  );
}

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

  if (authState === "checking") return <FullScreenLoader label="Connecting…" />;

  if (authState === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-0">
        <div className="text-center max-w-sm px-4">
          <div className="mx-auto mb-3 h-10 w-10 rounded-lg bg-red-500/10 flex items-center justify-center">
            <Monitor className="h-5 w-5 text-red-400" />
          </div>
          <p className="text-red-400 text-sm mb-1">Unable to reach the server</p>
          <p className="text-gray-500 text-xs mb-4">The manager backend isn't responding.</p>
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
            className="btn-secondary text-xs"
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
  const [agg, setAgg] = useState<{ cpu: number | null; mem: number | null }>({ cpu: null, mem: null });

  const selected = profiles.find((p) => p.id === selectedId) ?? null;

  // Poll system status: running-cap (MAX_RUNNING_PROFILES) + aggregate resource use.
  useEffect(() => {
    let active = true;
    const poll = () =>
      api.getStatus().then((s) => {
        if (!active) return;
        setMaxRunning(s.max_running ?? null);
        setAgg({ cpu: s.total_cpu_percent ?? null, mem: s.total_mem_mb ?? null });
      }).catch(() => {});
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

  if (loading) return <FullScreenLoader label="Loading profiles…" />;

  const runningCount = profiles.filter((p) => p.status === "running").length;

  return (
    <div className="h-screen flex bg-surface-0 text-gray-100">
      {/* Sidebar */}
      {sidebarOpen && (
        <aside className="w-72 border-r border-border bg-surface-1 flex-shrink-0 flex flex-col min-h-0">
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
          <div className="px-5 py-3 border-t border-border space-y-2 flex-shrink-0">
            <button
              onClick={() => setProxyManagerOpen(true)}
              className="btn-secondary w-full flex items-center justify-center gap-1.5 text-xs"
            >
              <Shield className="h-3.5 w-3.5" />
              <span>Proxy Credentials</span>
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setProxyProviderManagerOpen(true)}
                className="btn-secondary flex items-center justify-center gap-1.5 text-xs"
                title="Manage proxy providers (IPVanish, …)"
              >
                <Server className="h-3.5 w-3.5" />
                <span>Providers</span>
              </button>
              <button
                onClick={() => setProxyGroupManagerOpen(true)}
                className="btn-secondary flex items-center justify-center gap-1.5 text-xs"
                title="Manage proxy rotation groups"
              >
                <Shuffle className="h-3.5 w-3.5" />
                <span>Groups</span>
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Top bar */}
        <header className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface-1">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="icon-btn"
              aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
              aria-expanded={sidebarOpen}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </button>

            {!sidebarOpen && (
              <div className="flex items-center gap-1.5 pr-2 mr-1 border-r border-border">
                <Monitor className="h-4 w-4 text-accent" />
                <span className="text-sm font-semibold tracking-tight whitespace-nowrap">CloakBrowser Manager</span>
              </div>
            )}

            {selected && (
              <div className="flex items-center gap-2 min-w-0">
                <StatusIndicator status={selected.status} size="md" />
                <span className="text-sm font-medium truncate">{selected.name}</span>
                <span className="text-xs text-gray-500 capitalize flex-shrink-0">{selected.platform}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2.5 flex-shrink-0">
            {maxRunning !== null && (
              <span
                className="text-xs text-gray-400 tabular-nums"
                title="Running profiles / max allowed"
              >
                {runningCount}<span className="text-gray-600">/</span>{maxRunning}
              </span>
            )}
            {agg.cpu != null && agg.mem != null && (
              <span className="text-xs text-gray-400 font-mono tabular-nums hidden sm:inline" title="Aggregate CPU · memory across running profiles">
                CPU {agg.cpu.toFixed(0)}% · {agg.mem.toFixed(0)}MB
              </span>
            )}
            {selected && (
              <>
                <span className="h-5 w-px bg-border" aria-hidden="true" />
                <LaunchButton
                  status={selected.status}
                  onLaunch={handleLaunch}
                  onStop={handleStop}
                />
              </>
            )}
            {authRequired && (
              <button
                onClick={onLogout}
                className="icon-btn"
                aria-label="Log out"
                title="Log out"
              >
                <Lock className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div role="alert" className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain min-h-0">
          {view === "empty" && (
            <div className="flex items-center justify-center h-full px-4 py-16">
              <div className="text-center max-w-sm">
                <div className="mx-auto mb-5 h-12 w-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center">
                  <Monitor className="h-6 w-6 text-gray-500" />
                </div>
                <p className="text-gray-300 text-sm font-medium mb-1">No profile selected</p>
                <p className="text-gray-500 text-xs mb-5">
                  Select a profile from the sidebar, or create a new one to get started.
                </p>
                <button onClick={handleNew} className="btn-primary inline-flex items-center gap-1.5">
                  <Plus className="h-3.5 w-3.5" />
                  <span>New Profile</span>
                </button>
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
