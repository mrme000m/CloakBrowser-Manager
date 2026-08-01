import { Plus, Search, Monitor, Check, Code2, Files, LayoutTemplate } from "lucide-react";
import { useMemo, useState } from "react";
import type { Profile } from "../lib/api";
import { StatusIndicator } from "./StatusIndicator";

/** Compact "1d 2h 3m" / "3m 12s" formatter for uptime seconds. */
function formatUptime(s: number | null | undefined): string | null {
  if (s == null) return null;
  const sec = Math.floor(s);
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const ss = sec % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${ss}s`;
  return `${ss}s`;
}

interface ProfileListProps {
  profiles: Profile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDuplicate?: (id: string) => void;
  onBulkLaunch?: (ids: string[]) => void;
  onBulkStop?: (ids: string[]) => void;
  onBulkDelete?: (ids: string[]) => void;
  maxRunning?: number | null;
}

type Filter = "all" | "profiles" | "templates";

export function ProfileList({
  profiles, selectedId, onSelect, onNew,
  onDuplicate, onBulkLaunch, onBulkStop, onBulkDelete, maxRunning,
}: ProfileListProps) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [cdpCopiedId, setCdpCopiedId] = useState<string | null>(null);

  const runningCount = profiles.filter((p) => p.status === "running").length;

  const filtered = useMemo(() => profiles.filter((p) => {
    if (filter === "profiles" && p.is_template) return false;
    if (filter === "templates" && !p.is_template) return false;
    return p.name.toLowerCase().includes(search.toLowerCase());
  }), [profiles, filter, search]);

  const allSelected = filtered.length > 0 && filtered.every((p) => selectedIds.has(p.id));
  const someSelected = selectedIds.size > 0;
  const selectedArr = Array.from(selectedIds);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      if (filtered.every((p) => prev.has(p.id))) {
        const next = new Set(prev);
        filtered.forEach((p) => next.delete(p.id));
        return next;
      }
      const next = new Set(prev);
      filtered.forEach((p) => next.add(p.id));
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  const copyCdp = (e: React.MouseEvent, profile: Profile) => {
    e.stopPropagation();
    const url = profile.cdp_endpoint;
    if (!url) return;
    navigator.clipboard?.writeText(url).then(() => {
      setCdpCopiedId(profile.id);
      setTimeout(() => setCdpCopiedId(null), 2000);
    });
  };

  const duplicate = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    onDuplicate?.(id);
  };

  // Keyboard activation for the row (which is role="button"); the inner
  // checkbox + action buttons handle their own keys.
  const onRowKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    }
  };

  return (
    <div className="flex flex-col min-h-0 flex-1">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-6 w-6 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0">
            <Monitor className="h-3.5 w-3.5 text-accent" />
          </div>
          <h1 className="text-sm font-semibold tracking-tight">CloakBrowser Manager</h1>
        </div>
        {runningCount > 0 && (
          <div className="text-[11px] text-gray-400 mb-3 flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {runningCount} running{maxRunning ? ` / ${maxRunning}` : ""}
            </span>
          </div>
        )}
        {/* Search */}
        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search profiles…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-8 py-1.5 text-xs"
            aria-label="Search profiles"
          />
        </div>
        {/* Filter tabs */}
        <div className="flex gap-1.5" role="tablist" aria-label="Filter profiles">
          {(["all", "profiles", "templates"] as const).map((f) => (
            <button
              key={f}
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className={`tab ${filter === f ? "tab-active" : ""}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Bulk action bar */}
      {someSelected && (
        <div className="flex items-center gap-1 px-5 py-2 border-b border-border bg-surface-2 text-xs flex-shrink-0">
          <span className="text-gray-400 mr-1 tabular-nums">{selectedIds.size} selected</span>
          <button
            onClick={() => { onBulkLaunch?.(selectedArr); clearSelection(); }}
            className="px-2 py-0.5 rounded bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30"
          >
            Launch
          </button>
          <button
            onClick={() => { onBulkStop?.(selectedArr); clearSelection(); }}
            className="px-2 py-0.5 rounded bg-surface-3 text-gray-300 hover:text-gray-100"
          >
            Stop
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete ${selectedIds.size} profile(s)? Browser data will be removed.`)) {
                onBulkDelete?.(selectedArr);
                clearSelection();
              }
            }}
            className="px-2 py-0.5 rounded bg-red-600/20 text-red-300 hover:bg-red-600/30"
          >
            Delete
          </button>
          <button onClick={clearSelection} className="ml-auto text-gray-500 hover:text-gray-300">
            Clear
          </button>
        </div>
      )}

      {/* Profile list */}
      <div className="flex-1 overflow-y-auto p-2 min-h-0">
        {filtered.length === 0 && (
          <div className="text-center text-gray-500 text-xs py-8">
            {profiles.length === 0 ? "No profiles yet" : "No matches"}
          </div>
        )}
        {/* Select-all row */}
        {filtered.length > 0 && (
          <label className="flex items-center gap-2 px-3 py-1 mb-1 text-[11px] text-gray-500 cursor-pointer hover:text-gray-400">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleSelectAll}
              aria-label="Select all filtered profiles"
            />
            <span>Select all ({filtered.length})</span>
          </label>
        )}
        {filtered.map((profile) => (
          <div
            key={profile.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(profile.id)}
            onKeyDown={(e) => onRowKeyDown(e, profile.id)}
            aria-pressed={selectedId === profile.id}
            className={`w-full text-left px-3 py-2.5 rounded-md mb-1 transition-colors cursor-pointer outline-none
              ${selectedId === profile.id
                ? "bg-surface-3 border border-border-hover focus-visible:ring-2 focus-visible:ring-accent/40"
                : "hover:bg-surface-2 border border-transparent focus-visible:ring-2 focus-visible:ring-accent/30"}`}
          >
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedIds.has(profile.id)}
                onChange={(e) => { e.stopPropagation(); toggleSelect(profile.id); }}
                onClick={(e) => e.stopPropagation()}
                className="flex-shrink-0"
                aria-label={`Select ${profile.name}`}
              />
              <StatusIndicator status={profile.status} />
              <span className="text-sm font-medium truncate flex-1">{profile.name}</span>
              {profile.is_template && (
                <span className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 flex-shrink-0">
                  <LayoutTemplate className="h-2.5 w-2.5" />
                  TPL
                </span>
              )}
              {onDuplicate && (
                <button
                  onClick={(e) => duplicate(e, profile.id)}
                  className="icon-btn icon-btn-sm text-gray-500 hover:text-accent flex-shrink-0"
                  aria-label={profile.is_template ? `New profile from template ${profile.name}` : `Duplicate ${profile.name}`}
                  title={profile.is_template ? "New profile from template" : "Duplicate profile"}
                >
                  <Files className="h-3 w-3" />
                </button>
              )}
              {profile.cdp_endpoint && (
                <button
                  onClick={(e) => copyCdp(e, profile)}
                  className={`icon-btn icon-btn-sm flex-shrink-0 ${
                    cdpCopiedId === profile.id ? "text-emerald-400" : "text-gray-500 hover:text-accent"
                  }`}
                  aria-label={cdpCopiedId === profile.id ? "Copied CDP endpoint" : `Copy CDP endpoint for ${profile.name}`}
                  title={cdpCopiedId === profile.id ? "Copied!" : `Copy CDP: ${profile.cdp_endpoint}`}
                >
                  {cdpCopiedId === profile.id ? <Check className="h-3 w-3" /> : <Code2 className="h-3 w-3" />}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 ml-10">
              <span className="text-xs text-gray-500 capitalize">{profile.platform}</span>
              {(profile.proxy || profile.proxy_credential || profile.proxy_group) && (
                <>
                  <span className="text-xs text-gray-600">·</span>
                  <span className="text-xs text-gray-500 flex items-center gap-1">
                    Proxy
                    {/* health dot from last proxy check */}
                    {profile.proxy_credential?.last_status && (
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          profile.proxy_credential.last_status === "ok" ? "bg-emerald-400" : "bg-red-400"
                        }`}
                        title={
                          profile.proxy_credential.last_status === "ok"
                            ? `Reachable${profile.proxy_credential.last_exit_ip ? ` · ${profile.proxy_credential.last_exit_ip}` : ""}`
                            : "Failed last check"
                        }
                      />
                    )}
                  </span>
                </>
              )}
              {profile.cdp_endpoint && (
                <>
                  <span className="text-xs text-gray-600">·</span>
                  <span className={`text-xs ${profile.status === "running" ? "text-emerald-500" : "text-gray-500"}`}>
                    CDP {profile.status === "running" ? "ready" : ""}
                  </span>
                </>
              )}
              {profile.status === "running" && profile.resources && (profile.resources.cpu_percent != null || profile.resources.mem_mb != null) && (
                <>
                  <span className="text-xs text-gray-600">·</span>
                  <span
                    className="text-xs text-gray-500 font-mono tabular-nums"
                    title={`CPU ${profile.resources.cpu_percent ?? "—"}% · ${(profile.resources.mem_mb ?? 0).toFixed(0)} MB RSS · up ${formatUptime(profile.resources.uptime_s) ?? "—"} · ${profile.resources.proc_count ?? "—"} proc`}
                  >
                    CPU {profile.resources.cpu_percent ?? "—"}% · {(profile.resources.mem_mb ?? 0).toFixed(0)}MB
                  </span>
                </>
              )}
            </div>
            {profile.tags.length > 0 && (
              <div className="flex gap-1 mt-1.5 ml-10 flex-wrap">
                {profile.tags.map((t) => (
                  <span
                    key={t.tag}
                    className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-4 text-gray-400"
                    style={t.color ? { backgroundColor: `${t.color}20`, color: t.color } : undefined}
                  >
                    {t.tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* New profile button */}
      <div className="px-5 py-3 border-t border-border flex-shrink-0">
        <button onClick={onNew} className="btn-primary w-full flex items-center justify-center gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          <span>New Profile</span>
        </button>
      </div>
    </div>
  );
}
