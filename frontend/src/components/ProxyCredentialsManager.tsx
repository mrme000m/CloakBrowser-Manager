import { useState } from "react";
import { X, Plus, Pencil, Trash2, Shield, Activity, Zap } from "lucide-react";
import { useProxyCredentials } from "../hooks/useProxyCredentials";
import { useProxyProviders, useProxyLocations } from "../hooks/useProxyProviders";
import type { ProxyCredential, ProxyCredentialData, ProxyProvider } from "../lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

function relativeTime(iso: string | null): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diff = Date.now() - then;
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function ProxyCredentialsManager({ open, onClose }: Props) {
  const { credentials, create, update, remove, error, test, testAll } = useProxyCredentials();
  const { providers } = useProxyProviders();
  const { locations } = useProxyLocations();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    scheme: "socks5",
    host: "",
    port: "1080",
    username: "",
    password: "",
    provider_id: "",
    provider_location: "",
  });
  const [saving, setSaving] = useState(false);
  const [testingAll, setTestingAll] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  if (!open) return null;

  const providerMode = form.provider_id !== "";
  const selectedProvider = providers.find((p) => p.id === form.provider_id) ?? null;
  const providerLocations = selectedProvider ? locations[selectedProvider.type] ?? {} : {};

  const resetForm = () => {
    setForm({ name: "", scheme: "socks5", host: "", port: "1080", username: "", password: "", provider_id: "", provider_location: "" });
    setEditingId(null);
  };

  const handleEdit = (cred: ProxyCredential) => {
    setEditingId(cred.id);
    setForm({
      name: cred.name,
      scheme: cred.scheme,
      host: cred.host,
      port: String(cred.port),
      username: cred.username,
      password: "",
      provider_id: cred.provider_id ?? "",
      provider_location: cred.provider_location ?? "",
    });
  };

  const handleSave = async () => {
    if (!form.name.trim()) return;
    if (!providerMode && !form.host.trim()) return;
    setSaving(true);
    try {
      const data: ProxyCredentialData = {
        name: form.name.trim(),
        scheme: form.scheme,
        host: form.host.trim(),
        port: parseInt(form.port, 10) || 1080,
        username: form.username.trim(),
        password: form.password,
        // Provider-linked credentials materialize host/auth from the provider;
        // standalone ones carry their own host/user/pass.
        provider_id: providerMode ? form.provider_id : null,
        provider_location: providerMode ? (form.provider_location || null) : null,
      };
      if (editingId) {
        await update(editingId, data);
      } else {
        await create(data);
      }
      resetForm();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this proxy credential? Profiles using it will lose their proxy.")) return;
    try {
      await remove(id);
    } catch {
      // error is shown via hook
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      await test(id);
    } finally {
      setTestingId(null);
    }
  };

  const handleTestAll = async () => {
    setTestingAll(true);
    try {
      await testAll();
    } finally {
      setTestingAll(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/50">
      <div className="bg-surface-1 border border-border rounded-lg w-full max-w-lg shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold">Proxy Credentials</h2>
          </div>
          <div className="flex items-center gap-2">
            {credentials.length > 0 && (
              <button
                onClick={handleTestAll}
                disabled={testingAll}
                className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-surface-3 text-gray-300 hover:text-gray-100"
                title="Test all credentials"
              >
                {testingAll ? <Activity className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
                <span>{testingAll ? "Testing..." : "Test All"}</span>
              </button>
            )}
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {error && (
          <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-xs">
            {error}
          </div>
        )}

        {/* List */}
        <div className="max-h-64 overflow-y-auto">
          {credentials.length === 0 && (
            <div className="text-center text-gray-500 text-xs py-8">
              No proxy credentials saved yet
            </div>
          )}
          {credentials.map((cred) => {
            const last = relativeTime(cred.last_checked_at);
            return (
              <div
                key={cred.id}
                className={`flex items-center justify-between px-4 py-2.5 border-b border-border/50 ${
                  editingId === cred.id ? "bg-surface-3" : "hover:bg-surface-2"
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{cred.name}</span>
                    {/* health dot */}
                    {cred.last_status && (
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${cred.last_status === "ok" ? "bg-emerald-400" : "bg-red-400"}`}
                        title={cred.last_status === "ok" ? "Reachable" : "Failed last check"}
                      />
                    )}
                    {cred.last_status === "ok" && cred.last_exit_ip && (
                      <span className="text-[10px] text-gray-500 font-mono truncate">
                        {cred.last_exit_ip}{cred.last_country ? ` · ${cred.last_country}` : ""}
                      </span>
                    )}
                    {last && <span className="text-[10px] text-gray-600">{last}</span>}
                  </div>
                  <div className="text-xs text-gray-500 font-mono truncate">
                    {cred.scheme}://{cred.username ? `${cred.username}@` : ""}{cred.host}:{cred.port}
                  </div>
                </div>
                <div className="flex items-center gap-1 ml-2">
                  <button
                    onClick={() => handleTest(cred.id)}
                    disabled={testingId === cred.id}
                    className="p-1 text-gray-500 hover:text-accent disabled:opacity-50"
                    title="Test this proxy"
                  >
                    {testingId === cred.id ? <Activity className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                  </button>
                  <button onClick={() => handleEdit(cred)} className="p-1 text-gray-500 hover:text-gray-300" title="Edit">
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => handleDelete(cred.id)} className="p-1 text-gray-500 hover:text-red-400" title="Delete">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Form */}
        <div className="p-4 border-t border-border">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            {editingId ? "Edit Credential" : "Add Credential"}
          </h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Name</label>
                <input
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. IPVanish NYC"
                />
              </div>
              <div>
                <label className="label">Provider</label>
                <select
                  className="input"
                  value={form.provider_id}
                  onChange={(e) => setForm((f) => ({ ...f, provider_id: e.target.value, provider_location: "" }))}
                >
                  <option value="">None (standalone)</option>
                  {providers.map((p: ProxyProvider) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.type})</option>
                  ))}
                </select>
              </div>
            </div>

            {providerMode && (
              <div>
                <label className="label">Location</label>
                <select
                  className="input"
                  value={form.provider_location}
                  onChange={(e) => setForm((f) => ({ ...f, provider_location: e.target.value }))}
                >
                  <option value="">Select location...</option>
                  {Object.entries(providerLocations).map(([code, meta]) => (
                    <option key={code} value={code}>
                      {code} — {meta.city}, {meta.country}
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-gray-500 mt-1">
                  Host &amp; auth are materialized from the provider for the chosen location.
                </p>
              </div>
            )}

            {!providerMode && (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="label">Scheme</label>
                    <select
                      className="input"
                      value={form.scheme}
                      onChange={(e) => setForm((f) => ({ ...f, scheme: e.target.value }))}
                    >
                      <option value="socks5">SOCKS5</option>
                      <option value="http">HTTP</option>
                      <option value="https">HTTPS</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="label">Host</label>
                    <input
                      className="input"
                      value={form.host}
                      onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
                      placeholder="proxy.example.com"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="label">Port</label>
                    <input
                      className="input"
                      type="number"
                      value={form.port}
                      onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="label">Username</label>
                    <input
                      className="input"
                      value={form.username}
                      onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                      placeholder="user"
                    />
                  </div>
                  <div>
                    <label className="label">Password</label>
                    <input
                      className="input"
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                      placeholder={editingId ? "(blank to keep)" : "password"}
                    />
                  </div>
                </div>
              </>
            )}

            <div className="flex items-center gap-2 justify-end">
              {editingId && (
                <button onClick={resetForm} className="btn-secondary text-xs">Cancel</button>
              )}
              <button
                onClick={handleSave}
                disabled={saving || !form.name.trim() || (!providerMode && !form.host.trim())}
                className="btn-primary flex items-center gap-1.5 text-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>{saving ? "Saving..." : editingId ? "Update" : "Add"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
