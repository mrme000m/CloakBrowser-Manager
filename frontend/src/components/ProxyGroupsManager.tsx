import { useState } from "react";
import { Plus, Pencil, Trash2, Shuffle, RotateCw, Anchor } from "lucide-react";
import { useProxyGroups } from "../hooks/useProxyGroups";
import { useProxyCredentials } from "../hooks/useProxyCredentials";
import type { ProxyGroup } from "../lib/api";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
}

const ROTATION_MODES: { value: string; label: string; icon: typeof RotateCw; hint: string }[] = [
  { value: "round_robin", label: "Round-robin", icon: RotateCw, hint: "Cycle to the next member each launch" },
  { value: "sticky_session", label: "Sticky", icon: Anchor, hint: "Same member per profile (hash of profile id)" },
  { value: "random", label: "Random", icon: Shuffle, hint: "Random member each launch" },
];

export function ProxyGroupsManager({ open, onClose }: Props) {
  const { groups, create, update, remove, setMembers, error } = useProxyGroups();
  const { credentials } = useProxyCredentials();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [rotationMode, setRotationMode] = useState("round_robin");
  const [saving, setSaving] = useState(false);

  const resetForm = () => {
    setName("");
    setRotationMode("round_robin");
    setEditingId(null);
  };

  const handleEdit = (g: ProxyGroup) => {
    setEditingId(g.id);
    setName(g.name);
    setRotationMode(g.rotation_mode);
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      if (editingId) {
        await update(editingId, { name: name.trim(), rotation_mode: rotationMode });
      } else {
        await create({ name: name.trim(), rotation_mode: rotationMode });
      }
      resetForm();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this proxy group? Profiles using it will fall back to no proxy.")) return;
    try {
      await remove(id);
    } catch {
      // error shown via hook
    }
  };

  const toggleMember = async (groupId: string, credentialId: string, isMember: boolean) => {
    const group = groups.find((g) => g.id === groupId);
    if (!group) return;
    const ids = group.members.map((m) => m.credential_id);
    const next = isMember ? ids.filter((id) => id !== credentialId) : [...ids, credentialId];
    await setMembers(groupId, next);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Proxy Groups"
      icon={<Shuffle className="h-4 w-4 text-accent" />}
    >
      {error && (
        <div role="alert" className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Groups list with member toggles */}
      <div className="max-h-72 overflow-y-auto">
        {groups.length === 0 && (
          <div className="text-center text-gray-500 text-xs py-8">
            No proxy groups yet. Create a rotation pool and add credentials to it.
          </div>
        )}
        {groups.map((g) => (
          <div key={g.id} className="px-4 py-3 border-b border-border/50">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">{g.name}</span>
                  <span className="text-[10px] uppercase text-gray-500">
                    {g.rotation_mode.replace("_", " ")}
                  </span>
                  <span className="text-[10px] text-gray-500">{g.member_count} members</span>
                </div>
              </div>
              <div className="flex items-center gap-1 ml-2">
                <button onClick={() => handleEdit(g)} className="icon-btn text-gray-500 hover:text-gray-300" aria-label={`Edit ${g.name}`} title="Edit">
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => handleDelete(g.id)} className="icon-btn text-gray-500 hover:text-red-400" aria-label={`Delete ${g.name}`} title="Delete">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Member toggles */}
            {credentials.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {credentials.map((c) => {
                  const isMember = g.members.some((m) => m.credential_id === c.id);
                  return (
                    <button
                      key={c.id}
                      onClick={() => toggleMember(g.id, c.id, isMember)}
                      className={`text-xs px-2 py-1 rounded-full transition-colors ${
                        isMember
                          ? "bg-accent text-white"
                          : "bg-surface-3 text-gray-400 hover:text-gray-200"
                      }`}
                      aria-pressed={isMember}
                      title={isMember ? "Remove from group" : "Add to group"}
                    >
                      {c.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Form */}
      <div className="p-4 border-t border-border">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          {editingId ? "Edit Group" : "Add Group"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="label">Name</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. US residential pool"
            />
          </div>
          <div>
            <label className="label">Rotation Mode</label>
            <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Rotation mode">
              {ROTATION_MODES.map((m) => {
                const Icon = m.icon;
                const selected = rotationMode === m.value;
                return (
                  <button
                    key={m.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setRotationMode(m.value)}
                    title={m.hint}
                    className={`flex flex-col items-center gap-1 px-2 py-2 rounded-md text-xs transition-colors ${
                      selected
                        ? "bg-accent text-white"
                        : "bg-surface-3 text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{m.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="text-[10px] text-gray-500 mt-1">
              {ROTATION_MODES.find((m) => m.value === rotationMode)?.hint}
            </p>
          </div>
          <div className="flex items-center gap-2 justify-end">
            {editingId && (
              <button onClick={resetForm} className="btn-secondary text-xs">Cancel</button>
            )}
            <button
              onClick={handleSave}
              disabled={saving || !name.trim()}
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
