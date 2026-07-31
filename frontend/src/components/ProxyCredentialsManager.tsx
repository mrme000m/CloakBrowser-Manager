import { useState } from "react";
import { X, Plus, Pencil, Trash2, Shield } from "lucide-react";
import { useProxyCredentials } from "../hooks/useProxyCredentials";
import type { ProxyCredential } from "../lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ProxyCredentialsManager({ open, onClose }: Props) {
  const { credentials, create, update, remove, error } = useProxyCredentials();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    scheme: "socks5",
    host: "",
    port: "1080",
    username: "",
    password: "",
  });
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const resetForm = () => {
    setForm({ name: "", scheme: "socks5", host: "", port: "1080", username: "", password: "" });
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
    });
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.host.trim()) return;
    setSaving(true);
    try {
      const data = {
        name: form.name.trim(),
        scheme: form.scheme,
        host: form.host.trim(),
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
    if (!confirm("Delete this proxy credential? Profiles using it will lose their proxy.")) return;
    try {
      await remove(id);
    } catch {
      // error is shown via hook
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
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Error */}
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
          {credentials.map((cred) => (
            <div
              key={cred.id}
              className={`flex items-center justify-between px-4 py-2.5 border-b border-border/50 ${
                editingId === cred.id ? "bg-surface-3" : "hover:bg-surface-2"
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{cred.name}</div>
                <div className="text-xs text-gray-500 font-mono truncate">
                  {cred.scheme}://{cred.username ? `${cred.username}@` : ""}{cred.host}:{cred.port}
                </div>
              </div>
              <div className="flex items-center gap-1 ml-2">
                <button
                  onClick={() => handleEdit(cred)}
                  className="p-1 text-gray-500 hover:text-gray-300"
                  title="Edit"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => handleDelete(cred.id)}
                  className="p-1 text-gray-500 hover:text-red-400"
                  title="Delete"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Form */}
        <div className="p-4 border-t border-border">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            {editingId ? "Edit Credential" : "Add Credential"}
          </h3>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-3">
                <label className="label">Name</label>
                <input
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. IPVanish NYC"
                />
              </div>
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
                  placeholder={editingId ? "(leave blank to keep)" : "password"}
                />
              </div>
            </div>
            <div className="flex items-center gap-2 justify-end">
              {editingId && (
                <button onClick={resetForm} className="btn-secondary text-xs">
                  Cancel
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={saving || !form.name.trim() || !form.host.trim()}
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
