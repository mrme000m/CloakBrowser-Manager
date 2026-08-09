import { Save, Trash2, X, Copy, Check, Code2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { Profile, ProfileCreateData, ProxyCredential, ProxyGroup } from "../lib/api";

interface ProfileFormProps {
  profile: Profile | null; // null = create mode
  proxyCredentials: ProxyCredential[];
  proxyGroups: ProxyGroup[];
  onSave: (data: ProfileCreateData) => Promise<void>;
  onDelete?: () => Promise<void>;
  onCancel: () => void;
}

const RESOLUTION_PRESETS: Record<string, { width: number; height: number }> = {
  "1920 × 1080 (Full HD)": { width: 1920, height: 1080 },
  "2560 × 1440 (QHD)": { width: 2560, height: 1440 },
  "1366 × 768 (HD)": { width: 1366, height: 768 },
  "1440 × 900": { width: 1440, height: 900 },
  "1536 × 864": { width: 1536, height: 864 },
  "1280 × 720 (720p)": { width: 1280, height: 720 },
};

const TAG_COLORS = [
  "#6366f1", // indigo
  "#22c55e", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#06b6d4", // cyan
  "#a855f7", // purple
  "#f97316", // orange
  "#ec4899", // pink
];

const GPU_PRESETS: Record<string, { vendor: string; renderer: string }> = {
  "NVIDIA RTX 3070": {
    vendor: "Google Inc. (NVIDIA)",
    renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 (0x00002484) Direct3D11 vs_5_0 ps_5_0, D3D11)",
  },
  "NVIDIA RTX 4070": {
    vendor: "Google Inc. (NVIDIA)",
    renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 (0x00002786) Direct3D11 vs_5_0 ps_5_0, D3D11)",
  },
  "AMD RX 6800 XT": {
    vendor: "Google Inc. (AMD)",
    renderer: "ANGLE (AMD, AMD Radeon RX 6800 XT (0x000073BF) Direct3D11 vs_5_0 ps_5_0, D3D11)",
  },
  "Intel UHD 770": {
    vendor: "Google Inc. (Intel)",
    renderer: "ANGLE (Intel, Intel(R) UHD Graphics 770 (0x00004680) Direct3D11 vs_5_0 ps_5_0, D3D11)",
  },
  "Apple M3 (macOS)": {
    vendor: "Google Inc. (Apple)",
    renderer: "ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)",
  },
};

export function ProfileForm({ profile, proxyCredentials, proxyGroups, onSave, onDelete, onCancel }: ProfileFormProps) {
  const isEdit = profile !== null;

  const [form, setForm] = useState<ProfileCreateData>({
    name: "",
    platform: "windows",
    screen_width: 1920,
    screen_height: 1080,
    humanize: false,
    human_preset: "default",
    headless: false,
    geoip: false,
    clipboard_sync: true,
    auto_launch: false,
    launch_args: [],
    tags: [],
    is_template: false,
    restart_on_crash: false,
    max_restarts: 5,
    noise_enabled: true,
    clear_on_launch: false,
    is_mobile: false,
    has_touch: false,
  });

  const [proxyMode, setProxyMode] = useState<"none" | "credential" | "group" | "custom">("none");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [tagColor, setTagColor] = useState<string | null>("#6366f1");
  const [launchArgInput, setLaunchArgInput] = useState("");
  const [cdpCopied, setCdpCopied] = useState(false);

  useEffect(() => {
    if (profile) {
      setForm({
        name: profile.name,
        fingerprint_seed: profile.fingerprint_seed,
        proxy: profile.proxy,
        proxy_credential_id: profile.proxy_credential_id,
        proxy_group_id: profile.proxy_group_id,
        timezone: profile.timezone,
        locale: profile.locale,
        platform: profile.platform,
        user_agent: profile.user_agent,
        screen_width: profile.screen_width,
        screen_height: profile.screen_height,
        gpu_vendor: profile.gpu_vendor,
        gpu_renderer: profile.gpu_renderer,
        hardware_concurrency: profile.hardware_concurrency,
        device_memory: profile.device_memory,
        brand: profile.brand,
        brand_version: profile.brand_version,
        platform_version: profile.platform_version,
        fonts_dir: profile.fonts_dir,
        storage_quota_mb: profile.storage_quota_mb,
        taskbar_height: profile.taskbar_height,
        geolocation_lat: profile.geolocation_lat,
        geolocation_lon: profile.geolocation_lon,
        webrtc_ip: profile.webrtc_ip,
        noise_enabled: profile.noise_enabled,
        humanize: profile.humanize,
        human_preset: profile.human_preset,
        human_config: profile.human_config,
        headless: profile.headless,
        geoip: profile.geoip,
        clipboard_sync: profile.clipboard_sync,
        auto_launch: profile.auto_launch,
        clear_on_launch: profile.clear_on_launch,
        storage_state: profile.storage_state,
        permissions: profile.permissions,
        device_scale_factor: profile.device_scale_factor,
        is_mobile: profile.is_mobile,
        has_touch: profile.has_touch,
        extension_paths: profile.extension_paths,
        color_scheme: profile.color_scheme,
        launch_args: profile.launch_args ?? [],
        notes: profile.notes,
        tags: profile.tags ?? [],
        is_template: profile.is_template,
        restart_on_crash: profile.restart_on_crash,
        max_restarts: profile.max_restarts,
      });
      if (profile.proxy_group_id) {
        setProxyMode("group");
      } else if (profile.proxy_credential_id) {
        setProxyMode("credential");
      } else if (profile.proxy) {
        setProxyMode("custom");
      } else {
        setProxyMode("none");
      }
    }
  }, [profile?.id]);

  const set = <K extends keyof ProfileCreateData>(key: K, value: ProfileCreateData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    if (!confirm("Delete this profile? Browser data will be permanently removed.")) return;
    setDeleting(true);
    try {
      await onDelete();
    } finally {
      setDeleting(false);
    }
  };

  const applyGpuPreset = (name: string) => {
    const preset = GPU_PRESETS[name];
    if (preset) {
      set("gpu_vendor", preset.vendor);
      set("gpu_renderer", preset.renderer);
    }
  };

  const filteredGpuPresets = Object.entries(GPU_PRESETS).filter(([, preset]) => {
    const r = preset.renderer.toLowerCase();
    const p = (form.platform || "windows").toLowerCase();
    if (p === "macos" && r.includes("metal")) return true;
    if (p === "windows" && r.includes("d3d11")) return true;
    if (p === "linux" && (r.includes("vulkan") || r.includes("opengl"))) return true;
    return false;
  });

  const randomizeSeed = () => {
    set("fingerprint_seed", Math.floor(Math.random() * 90000) + 10000);
  };

  const currentResolution = Object.entries(RESOLUTION_PRESETS).find(
    ([, v]) => v.width === form.screen_width && v.height === form.screen_height,
  )?.[0] ?? "custom";

  const addTag = () => {
    const tag = tagInput.trim();
    if (!tag) return;
    if (form.tags?.some((t) => t.tag === tag)) return;
    set("tags", [...(form.tags ?? []), { tag, color: tagColor }]);
    setTagInput("");
  };

  const removeTag = (tag: string) => {
    set("tags", (form.tags ?? []).filter((t) => t.tag !== tag));
  };

  const addLaunchArg = () => {
    const arg = launchArgInput.trim();
    if (!arg) return;
    if ((form.launch_args ?? []).includes(arg)) return;
    set("launch_args", [...(form.launch_args ?? []), arg]);
    setLaunchArgInput("");
  };

  const removeLaunchArg = (idx: number) => {
    set("launch_args", (form.launch_args ?? []).filter((_, i) => i !== idx));
  };

  const handleProxyMode = (mode: "none" | "credential" | "group" | "custom") => {
    setProxyMode(mode);
    if (mode === "none") {
      set("proxy", null);
      set("proxy_credential_id", null);
      set("proxy_group_id", null);
    } else if (mode === "credential") {
      set("proxy", null);
      set("proxy_group_id", null);
    } else if (mode === "group") {
      set("proxy", null);
      set("proxy_credential_id", null);
    } else {
      set("proxy_credential_id", null);
      set("proxy_group_id", null);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">
            {isEdit ? "Edit Profile" : "New Profile"}
          </h2>
          {isEdit && onDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="btn-danger flex items-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>{deleting ? "Deleting..." : "Delete"}</span>
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onCancel} className="btn-secondary">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-1.5">
            <Save className="h-3.5 w-3.5" />
            <span>{saving ? "Saving..." : isEdit ? "Save" : "Create"}</span>
          </button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Basic */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Basic</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="label">Profile Name</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="e.g. Amazon Seller #1"
                required
              />
            </div>
            <div>
              <label className="label">Platform</label>
              <select
                className="input"
                value={form.platform}
                onChange={(e) => set("platform", e.target.value)}
              >
                <option value="windows">Windows</option>
                <option value="macos">macOS</option>
                <option value="linux">Linux</option>
              </select>
            </div>
            <div>
              <label className="label">Fingerprint Seed</label>
              <div className="flex gap-2">
                <input
                  className="input flex-1 no-spin"
                  type="number"
                  value={form.fingerprint_seed ?? ""}
                  onChange={(e) => set("fingerprint_seed", e.target.value ? Number(e.target.value) : null)}
                  placeholder="Auto (random)"
                />
                <button
                  type="button"
                  onClick={randomizeSeed}
                  className="btn-secondary px-2.5"
                  title="Randomize seed"
                  aria-label="Randomize fingerprint seed"
                >
                  <svg className="h-5 w-5" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round">
                    <polygon points="28,10 16,16 16,28 28,22" fill="currentColor" opacity="0.06" />
                    <polygon points="28,10 16,16 16,28 28,22" />
                    <polygon points="4,10 16,16 16,28 4,22" fill="currentColor" opacity="0.2" />
                    <polygon points="4,10 16,16 16,28 4,22" />
                    <polygon points="16,3 28,10 16,16 4,10" fill="currentColor" opacity="0.1" />
                    <polygon points="16,3 28,10 16,16 4,10" />
                    <circle cx="11.5" cy="8.5" r="1" fill="currentColor" opacity="0.7" />
                    <circle cx="16" cy="9.5" r="1" fill="currentColor" opacity="0.7" />
                    <circle cx="20.5" cy="10.5" r="1" fill="currentColor" opacity="0.7" />
                    <circle cx="7.5" cy="14" r="0.9" fill="currentColor" opacity="0.6" />
                    <circle cx="12.5" cy="16.5" r="0.9" fill="currentColor" opacity="0.6" />
                    <circle cx="10" cy="19" r="0.9" fill="currentColor" opacity="0.6" />
                    <circle cx="7.5" cy="22" r="0.9" fill="currentColor" opacity="0.6" />
                    <circle cx="12.5" cy="24.5" r="0.9" fill="currentColor" opacity="0.6" />
                    <circle cx="20" cy="15" r="0.9" fill="currentColor" opacity="0.5" />
                    <circle cx="24" cy="20" r="0.9" fill="currentColor" opacity="0.5" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mt-4">
            <input
              type="checkbox"
              checked={form.is_template ?? false}
              onChange={(e) => set("is_template", e.target.checked)}
              className="rounded border-border bg-surface-2"
            />
            This is a template (cannot be launched; used as a starting point for duplication)
          </label>
        </section>

        {/* Network */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Network</h3>
          <div className="space-y-3">
            {/* Proxy mode selector */}
            <div>
              <label className="label">Proxy</label>
              <div className="flex gap-1 mb-2">
                {(["none", "credential", "group", "custom"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => handleProxyMode(mode)}
                    className={`text-xs px-3 py-1 rounded-md transition-colors ${
                      proxyMode === mode
                        ? "bg-accent text-white"
                        : "bg-surface-3 text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {mode === "none" ? "None" : mode === "credential" ? "Credential" : mode === "group" ? "Group" : "Custom URL"}
                  </button>
                ))}
              </div>

              {proxyMode === "credential" && (
                <select
                  className="input"
                  value={form.proxy_credential_id ?? ""}
                  onChange={(e) => set("proxy_credential_id", e.target.value || null)}
                >
                  <option value="">Select saved credential...</option>
                  {proxyCredentials.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.scheme}://{c.host}:{c.port})
                    </option>
                  ))}
                </select>
              )}

              {proxyMode === "group" && (
                <select
                  className="input"
                  value={form.proxy_group_id ?? ""}
                  onChange={(e) => set("proxy_group_id", e.target.value || null)}
                >
                  <option value="">Select proxy group...</option>
                  {proxyGroups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name} ({g.rotation_mode.replace("_", " ")}, {g.member_count} members)
                    </option>
                  ))}
                </select>
              )}

              {proxyMode === "custom" && (
                <input
                  className="input"
                  value={form.proxy ?? ""}
                  onChange={(e) => set("proxy", e.target.value || null)}
                  placeholder="socks5://user:pass@host:1080"
                />
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Timezone</label>
                <input
                  className="input"
                  value={form.timezone ?? ""}
                  onChange={(e) => set("timezone", e.target.value || null)}
                  placeholder="America/New_York"
                />
              </div>
              <div>
                <label className="label">Locale</label>
                <input
                  className="input"
                  value={form.locale ?? ""}
                  onChange={(e) => set("locale", e.target.value || null)}
                  placeholder="en-US"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.geoip ?? false}
                onChange={(e) => set("geoip", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Auto-detect timezone/locale from proxy IP (GeoIP)
            </label>
          </div>
        </section>

        {/* Hardware */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Hardware</h3>
          <div className="space-y-3">
            <div>
              <label className="label">Screen Resolution</label>
              <select
                className="input"
                value={currentResolution}
                onChange={(e) => {
                  const preset = RESOLUTION_PRESETS[e.target.value];
                  if (preset) {
                    set("screen_width", preset.width);
                    set("screen_height", preset.height);
                  }
                }}
              >
                {Object.keys(RESOLUTION_PRESETS).map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
                <option value="custom">Custom</option>
              </select>
            </div>
            {currentResolution === "custom" && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Width</label>
                  <input
                    className="input"
                    type="number"
                    value={form.screen_width ?? 1920}
                    onChange={(e) => set("screen_width", Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="label">Height</label>
                  <input
                    className="input"
                    type="number"
                    value={form.screen_height ?? 1080}
                    onChange={(e) => set("screen_height", Number(e.target.value))}
                  />
                </div>
              </div>
            )}
            <div>
              <label className="label">Hardware Concurrency</label>
              <input
                className="input"
                type="number"
                value={form.hardware_concurrency ?? ""}
                onChange={(e) => set("hardware_concurrency", e.target.value ? Number(e.target.value) : null)}
                placeholder="Auto (from seed)"
              />
            </div>
            <div>
              <label className="label">GPU Preset</label>
                <select
                  className="input"
                  value=""
                  onChange={(e) => {
                    if (e.target.value) applyGpuPreset(e.target.value);
                  }}
                >
                  <option value="">Select preset...</option>
                  {filteredGpuPresets.length > 0
                    ? filteredGpuPresets.map(([name]) => (
                        <option key={name} value={name}>{name}</option>
                      ))
                    : Object.keys(GPU_PRESETS).map((name) => (
                        <option key={name} value={name}>{name}</option>
                      ))
                  }
                </select>
            </div>
            <div>
              <label className="label">GPU Vendor</label>
              <input
                className="input"
                value={form.gpu_vendor ?? ""}
                onChange={(e) => set("gpu_vendor", e.target.value || null)}
                placeholder="Auto (from seed)"
              />
            </div>
            <div>
              <label className="label">GPU Renderer</label>
              <input
                className="input"
                value={form.gpu_renderer ?? ""}
                onChange={(e) => set("gpu_renderer", e.target.value || null)}
                placeholder="Auto (from seed)"
              />
            </div>
          </div>
        </section>

        {/* Organic Fingerprint */}
        <section>
          <h3 className="text-xs font-semibold text-accent uppercase tracking-wider mb-4">Organic Fingerprint</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Device Memory (GB)</label>
                <select
                  className="input"
                  value={form.device_memory ?? ""}
                  onChange={(e) => set("device_memory", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Auto (from seed)</option>
                  {[0.25, 0.5, 1, 2, 4, 8, 16, 32].map((v) => (
                    <option key={v} value={v}>{v} GB</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Storage Quota (MB)</label>
                <input
                  className="input"
                  type="number"
                  value={form.storage_quota_mb ?? ""}
                  onChange={(e) => set("storage_quota_mb", e.target.value ? Number(e.target.value) : null)}
                  placeholder="Auto"
                />
              </div>
            </div>
            <div>
              <label className="label">Fonts Directory</label>
              <input
                className="input"
                value={form.fonts_dir ?? ""}
                onChange={(e) => set("fonts_dir", e.target.value || null)}
                placeholder="/data/fonts/win10"
              />
              <p className="text-[10px] text-gray-500 mt-1">
                Required for Windows-spoofing on Linux. Install Windows fonts with <code>ttf-mscorefonts-installer</code>.
              </p>
            </div>
            <div>
              <label className="label">Taskbar Height (px)</label>
              <input
                className="input no-spin"
                type="number"
                value={form.taskbar_height ?? ""}
                onChange={(e) => set("taskbar_height", e.target.value ? Number(e.target.value) : null)}
                placeholder="Platform default (Windows 40, macOS 23)"
              />
            </div>
          </div>
        </section>

        {/* Client Hints */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Client Hints (Sec-CH-UA)</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Brand</label>
                <select
                  className="input"
                  value={form.brand ?? ""}
                  onChange={(e) => set("brand", e.target.value || null)}
                >
                  <option value="">Auto</option>
                  <option value="chrome">Chrome</option>
                  <option value="edge">Edge</option>
                  <option value="opera">Opera</option>
                  <option value="vivaldi">Vivaldi</option>
                </select>
              </div>
              <div>
                <label className="label">Brand Version</label>
                <input
                  className="input"
                  value={form.brand_version ?? ""}
                  onChange={(e) => set("brand_version", e.target.value || null)}
                  placeholder="e.g. 120.0.6099.109"
                />
              </div>
            </div>
            <div>
              <label className="label">Platform Version</label>
              <input
                className="input"
                value={form.platform_version ?? ""}
                onChange={(e) => set("platform_version", e.target.value || null)}
                placeholder={form.platform === "macos" ? "e.g. 13_5_1" : "e.g. 10.0.19045"}
              />
            </div>
          </div>
        </section>

        {/* WebRTC & Geolocation */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">WebRTC &amp; Geolocation</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">WebRTC IP Override</label>
                <select
                  className="input"
                  value={form.webrtc_ip ?? ""}
                  onChange={(e) => set("webrtc_ip", e.target.value || null)}
                >
                  <option value="">Auto (from proxy if geoip)</option>
                  <option value="auto">Auto (always match proxy)</option>
                  <option value="disabled">Disable WebRTC completely</option>
                </select>
              </div>
              <div>
                <label className="label">Fingerprint Noise</label>
                <select
                  className="input"
                  value={form.noise_enabled ? "on" : "off"}
                  onChange={(e) => set("noise_enabled", e.target.value === "on")}
                >
                  <option value="on">Enabled (unique per seed)</option>
                  <option value="off">Disabled (stable returning-user identity)</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Latitude</label>
                <input
                  className="input"
                  type="number"
                  step="any"
                  value={form.geolocation_lat ?? ""}
                  onChange={(e) => set("geolocation_lat", e.target.value ? Number(e.target.value) : null)}
                  placeholder="e.g. 40.7128"
                />
              </div>
              <div>
                <label className="label">Longitude</label>
                <input
                  className="input"
                  type="number"
                  step="any"
                  value={form.geolocation_lon ?? ""}
                  onChange={(e) => set("geolocation_lon", e.target.value ? Number(e.target.value) : null)}
                  placeholder="e.g. -74.0060"
                />
              </div>
            </div>
          </div>
        </section>

        {/* CDP Endpoint */}
        {isEdit && profile.cdp_endpoint && (
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">CDP Endpoint</h3>
            <div className="bg-surface-2 border border-border rounded-md p-3">
              <div className="flex items-center gap-2 mb-2">
                <Code2 className="h-3.5 w-3.5 text-accent" />
                <span className="text-xs font-medium text-gray-300">
                  {profile.status === "running" ? "Browser CDP (running)" : "CDP URL (launch to connect)"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs text-gray-400 font-mono break-all bg-surface-3 rounded px-2 py-1.5 select-all">
                  {profile.cdp_endpoint}
                </code>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard?.writeText(profile.cdp_endpoint ?? "").then(() => {
                      setCdpCopied(true);
                      setTimeout(() => setCdpCopied(false), 2000);
                    });
                  }}
                  className={`icon-btn flex-shrink-0 ${cdpCopied ? "text-emerald-400" : "text-gray-500 hover:text-gray-300"}`}
                  aria-label={cdpCopied ? "Copied CDP URL" : "Copy CDP URL"}
                  title={cdpCopied ? "Copied!" : "Copy CDP URL"}
                >
                  {cdpCopied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="text-[10px] text-gray-500 mt-1.5">
                Use with chrome-devtools-mcp: <code className="text-accent">--wsEndpoint={profile.cdp_endpoint}</code>
              </p>
            </div>
          </section>
        )}

        {/* Behavior */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Behavior</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.humanize ?? false}
                onChange={(e) => set("humanize", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Human-like mouse, keyboard, and scroll behavior
            </label>
            {form.humanize && (
              <div>
                <label className="label">Human Preset</label>
                <select
                  className="input"
                  value={form.human_preset}
                  onChange={(e) => set("human_preset", e.target.value)}
                >
                  <option value="default">Default (normal speed)</option>
                  <option value="careful">Careful (slower, deliberate)</option>
                </select>
              </div>
            )}
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.clipboard_sync ?? true}
                onChange={(e) => set("clipboard_sync", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Enable clipboard sync by default in VNC viewer
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.auto_launch ?? false}
                onChange={(e) => set("auto_launch", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Launch automatically when container starts
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.restart_on_crash ?? false}
                onChange={(e) => set("restart_on_crash", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Restart automatically on unexpected crash
            </label>
            {form.restart_on_crash && (
              <div>
                <label className="label">Max Restarts</label>
                <input
                  className="input no-spin"
                  type="number"
                  min={1}
                  max={100}
                  value={form.max_restarts ?? 5}
                  onChange={(e) => set("max_restarts", e.target.value ? Number(e.target.value) : 5)}
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Backoff is exponential (2^n, capped at 60s) between attempts.
                </p>
              </div>
            )}
            <div>
              <label className="label">Color Scheme</label>
              <select
                className="input"
                value={form.color_scheme ?? ""}
                onChange={(e) => set("color_scheme", e.target.value || null)}
              >
                <option value="">System default</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="no-preference">No preference</option>
              </select>
            </div>
            <div>
              <label className="label">User Agent</label>
              <input
                className="input"
                value={form.user_agent ?? ""}
                onChange={(e) => set("user_agent", e.target.value || null)}
                placeholder="Auto (from binary)"
              />
            </div>
          </div>
        </section>

        {/* Session Hygiene */}
        <section>
          <h3 className="text-xs font-semibold text-accent uppercase tracking-wider mb-4">Session Hygiene</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.clear_on_launch ?? false}
                onChange={(e) => set("clear_on_launch", e.target.checked)}
                className="rounded border-border bg-surface-2"
              />
              Clear cookies, cache, and storage on every launch
            </label>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="label">Device Scale Factor</label>
                <input
                  className="input"
                  type="number"
                  step="0.25"
                  min={0.5}
                  max={3}
                  value={form.device_scale_factor ?? ""}
                  onChange={(e) => set("device_scale_factor", e.target.value ? Number(e.target.value) : null)}
                  placeholder="1.0"
                />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_mobile ?? false}
                    onChange={(e) => set("is_mobile", e.target.checked)}
                    className="rounded border-border bg-surface-2"
                  />
                  Is Mobile
                </label>
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.has_touch ?? false}
                    onChange={(e) => set("has_touch", e.target.checked)}
                    className="rounded border-border bg-surface-2"
                  />
                  Has Touch
                </label>
              </div>
            </div>
            <div>
              <label className="label">Extension Paths</label>
              <input
                className="input font-mono"
                value={(form.extension_paths ?? []).join(", ")}
                onChange={(e) => {
                  const vals = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  set("extension_paths", vals.length > 0 ? vals : null);
                }}
                placeholder="/data/extensions/ublock, /data/extensions/proxy-switcher"
              />
              <p className="text-[10px] text-gray-500 mt-1">Comma-separated absolute paths.</p>
            </div>
          </div>
        </section>

        {/* Coherence Warnings */}
        {isEdit && profile.coherence_warnings && profile.coherence_warnings.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-4">
              Coherence Warnings ({profile.coherence_warnings.length})
            </h3>
            <div className="bg-amber-400/5 border border-amber-400/20 rounded p-3 space-y-2">
              {profile.coherence_warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-amber-200/80">
                  <span className="text-amber-400 mt-0.5 shrink-0">⚠</span>
                  <span>{w}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Tags */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Tags</h3>
          {(form.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {(form.tags ?? []).map((t) => (
                <span
                  key={t.tag}
                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-surface-3 text-gray-300"
                  style={t.color ? { backgroundColor: `${t.color}20`, color: t.color } : undefined}
                >
                  {t.tag}
                  <button
                    type="button"
                    onClick={() => removeTag(t.tag)}
                    className="hover:opacity-70"
                    aria-label={`Remove tag ${t.tag}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2 items-center">
            <div className="flex gap-1">
              {TAG_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setTagColor(c)}
                  className="w-4 h-4 rounded-full border-2 transition-transform"
                  style={{
                    backgroundColor: c,
                    borderColor: tagColor === c ? "#fff" : "transparent",
                    transform: tagColor === c ? "scale(1.2)" : undefined,
                  }}
                  aria-label={`Tag color ${c}`}
                  aria-pressed={tagColor === c}
                />
              ))}
            </div>
            <input
              className="input flex-1"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
              placeholder="Add tag..."
            />
            <button type="button" onClick={addTag} className="btn-secondary text-xs">
              Add
            </button>
          </div>
        </section>

        {/* Launch Args */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Launch Args</h3>
          <p className="text-xs text-gray-500 mb-2">Custom Chromium flags passed at launch (e.g. --load-extension, --disable-features)</p>
          {(form.launch_args ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {(form.launch_args ?? []).map((arg, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-surface-3 text-gray-300 font-mono"
                >
                  {arg}
                  <button
                    type="button"
                    onClick={() => removeLaunchArg(idx)}
                    className="hover:opacity-70"
                    aria-label={`Remove launch argument ${arg}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input
              className="input flex-1 font-mono"
              value={launchArgInput}
              onChange={(e) => setLaunchArgInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLaunchArg(); } }}
              placeholder="--load-extension=/data/extensions/ublock"
            />
            <button type="button" onClick={addLaunchArg} className="btn-secondary text-xs">
              Add
            </button>
          </div>
        </section>

        {/* Notes */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Notes</h3>
          <textarea
            className="input min-h-[80px] resize-y"
            value={form.notes ?? ""}
            onChange={(e) => set("notes", e.target.value || null)}
            placeholder="Optional notes about this profile..."
          />
        </section>
      </div>

    </form>
  );
}
