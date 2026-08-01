import { useState } from "react";
import { Plus, Pencil, Trash2, Server } from "lucide-react";
import { useProxyProviders } from "../hooks/useProxyProviders";
import type { ProxyProvider } from "../lib/api";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
}

const PROVIDER_TYPES: { value: string; label: string; hint: string }[] = [
  { value: "ipvanish", label: "IPVanish", hint: "Built-in city catalog (host per location)" },
  { value: "brightdata", label: "Bright Data", hint: "host_template, e.g. brd.superproxy.io:22225" },
  { value: "smartproxy", label: "Smartproxy", hint: "host_template, e.g. gate.smartproxy.com:7000" },
  { value: "custom", label: "Custom", hint: "host_template host:port" },
];

export function ProxyProvidersManager({ open, onClose }: Props) {
  const { providers, create, update, remove, error } = useProxyProviders();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    type: "ipvanish",
    scheme: "socks5",
    host_template: "",
    port: "1080",
    username: "",
    password: "",
  });
  const [saving, setSaving] = useState(false);

  const resetForm = () => {
    setForm({ name: "", type: "ipvanish", scheme: "socks5", host_template: "", port: "1080", username: "", password: "" });
    setEditingId(null);
  };

  const handleEdit = (p: ProxyProvider) => {
    setEditingId(p.id);
    setForm({
      name: p.name,
      type: p.type,
      scheme: p.scheme,
      host_template: p.host_template,
      port: String(p.port),
      username: p.username,
      password: "",
    });
  };

  const handleSave = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const data = {
        name: form.name.trim(),
        type: form.type,
        scheme: form.scheme,
        host_template: form.host_template.trim(),
        port: parseInt(form.port, 10) || 1080,
        username: form.username.trim(),
        password: form.password,
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
    if (!confirm("Delete this provider? Credentials created from it keep their last materialized host.")) return;
    try {
      await remove(id);
    } catch {
      // error shown via hook
    }
  };

  const typeHint = PROVIDER_TYPES.find((t) => t.value === form.type)?.hint ?? "";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Proxy Providers"
      icon={<Server className="h-4 w-4 text-accent" />}
    >
      {error && (
        <div role="alert" className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      <div className="max-h-64 overflow-y-auto">
        {providers.length === 0 && (
          <div className="text-center text-gray-500 text-xs py-8">
            No proxy providers yet. Add an IPVanish account to generate per-location credentials.
          </div>
        )}
        {providers.map((p) => (
          <div
            key={p.id}
            className={`flex items-center justify-between px-4 py-2.5 border-b border-border/50 ${
              editingId === p.id ? "bg-surface-3" : "hover:bg-surface-2"
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">
                {p.name}
                <span className="ml-2 text-[10px] uppercase text-gray-500">{p.type}</span>
              </div>
              <div className="text-xs text-gray-500 font-mono truncate">
                {p.scheme}://{p.username ? `${p.username}@` : ""}{p.host_template || "(host from location)"}:{p.port}
              </div>
            </div>
            <div className="flex items-center gap-1 ml-2">
              <button onClick={() => handleEdit(p)} className="icon-btn text-gray-500 hover:text-gray-300" aria-label={`Edit ${p.name}`} title="Edit">
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => handleDelete(p.id)} className="icon-btn text-gray-500 hover:text-red-400" aria-label={`Delete ${p.name}`} title="Delete">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-border">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          {editingId ? "Edit Provider" : "Add Provider"}
        </h3>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Name</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. IPVanish"
              />
            </div>
            <div>
              <label className="label">Type</label>
              <select
                className="input"
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
              >
                {PROVIDER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-[10px] text-gray-500 -mt-1">{typeHint}</p>

          {form.type !== "ipvanish" && (
            <div>
              <label className="label">Host Template</label>
              <input
                className="input font-mono"
                value={form.host_template}
                onChange={(e) => setForm((f) => ({ ...f, host_template: e.target.value }))}
                placeholder="brd.superproxy.io:22225"
              />
            </div>
          )}

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
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder={editingId ? "(leave blank to keep)" : "password"}
            />
          </div>

          <div className="flex items-center gap-2 justify-end">
            {editingId && (
              <button onClick={resetForm} className="btn-secondary text-xs">Cancel</button>
            )}
            <button
              onClick={handleSave}
              disabled={saving || !form.name.trim()}
              className="btn-primary flex items-center gap-1.5 text-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>{saving ? "Saving…" : editingId ? "Update" : "Add"}</span>
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
