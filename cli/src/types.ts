/** Response types mirroring the CloakBrowser-Manager backend (Pydantic) models. */

export interface Tag {
  tag: string;
  color: string | null;
}

export interface ProxyCredential {
  id: string;
  name: string;
  scheme: string;
  host: string;
  port: number;
  username: string;
  has_password: boolean;
  proxy_url: string;
  provider_id: string | null;
  provider_location: string | null;
  last_status: string | null;
  last_exit_ip: string | null;
  last_country: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProxyProvider {
  id: string;
  name: string;
  type: string;
  scheme: string;
  host_template: string;
  port: number;
  username: string;
  has_password: boolean;
  options: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProxyGroupMember {
  credential_id: string;
  position: number;
  name: string;
  scheme: string;
  host: string;
  port: number;
  username: string;
  provider_id: string | null;
  provider_location: string | null;
  last_status: string | null;
  last_exit_ip: string | null;
  last_country: string | null;
}

export interface ProxyGroup {
  id: string;
  name: string;
  rotation_mode: string;
  member_count: number;
  members: ProxyGroupMember[];
  created_at: string;
  updated_at: string;
}

export interface ProfileResources {
  cpu_percent: number | null;
  mem_mb: number | null;
  uptime_s: number | null;
  proc_count: number | null;
}

export interface Profile {
  id: string;
  name: string;
  fingerprint_seed: number;
  proxy: string | null;
  proxy_credential_id: string | null;
  proxy_credential: ProxyCredential | null;
  proxy_group_id: string | null;
  proxy_group: ProxyGroup | null;
  timezone: string | null;
  locale: string | null;
  platform: string;
  user_agent: string | null;
  screen_width: number;
  screen_height: number;
  gpu_vendor: string | null;
  gpu_renderer: string | null;
  hardware_concurrency: number | null;
  humanize: boolean;
  human_preset: string;
  headless: boolean;
  geoip: boolean;
  clipboard_sync: boolean;
  auto_launch: boolean;
  color_scheme: string | null;
  launch_args: string[];
  notes: string | null;
  is_template: boolean;
  restart_on_crash: boolean;
  max_restarts: number;
  user_data_dir: string;
  created_at: string;
  updated_at: string;
  tags: Tag[];
  status: "running" | "stopped";
  vnc_ws_port: number | null;
  cdp_url: string | null;
  cdp_endpoint: string | null;
  resources: ProfileResources | null;
}

export interface ProfileStatus {
  status: string;
  vnc_ws_port: number | null;
  display: string | null;
  cdp_url: string | null;
  cdp_endpoint: string | null;
  cdp_clients: number;
  exit_ip: string | null;
  effective_timezone: string | null;
  effective_locale: string | null;
  resources: ProfileResources | null;
}

export interface LaunchResult {
  profile_id: string;
  status: string;
  vnc_ws_port: number;
  display: string;
  cdp_url: string | null;
  cdp_endpoint: string | null;
}

export interface SystemStatus {
  running_count: number;
  binary_version: string;
  profiles_total: number;
  max_running: number | null;
  total_cpu_percent: number | null;
  total_mem_mb: number | null;
  total_proc_count: number | null;
}

export interface ProxyTestResult {
  id: string | null;
  ok: boolean;
  exit_ip: string | null;
  country: string | null;
  timezone: string | null;
  latency_ms: number | null;
  error: string | null;
}

export interface BulkResultItem {
  id: string;
  ok: boolean;
  error: string | null;
}

export interface BulkResultResponse {
  results: BulkResultItem[];
}

export interface AuthStatus {
  auth_required: boolean;
  authenticated: boolean;
}

export interface OkResponse {
  ok: boolean;
}

/** GET /api/proxy-locations → { providerType: { code: {host, city, country} } }. */
export type ProxyLocations = Record<string, Record<string, ProxyLocation>>;

export interface ProxyLocation {
  host: string;
  city: string;
  country: string;
}
