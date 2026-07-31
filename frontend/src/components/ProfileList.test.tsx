import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProfileList } from "./ProfileList";
import type { Profile } from "../lib/api";

function baseProfile(over: Partial<Profile> = {}): Profile {
  return {
    id: "p1",
    name: "Test",
    fingerprint_seed: 1,
    proxy: null,
    proxy_credential_id: null,
    proxy_credential: null,
    proxy_group_id: null,
    proxy_group: null,
    timezone: null,
    locale: null,
    platform: "windows",
    user_agent: null,
    screen_width: 1920,
    screen_height: 1080,
    gpu_vendor: null,
    gpu_renderer: null,
    hardware_concurrency: null,
    humanize: false,
    human_preset: "default",
    headless: false,
    geoip: false,
    clipboard_sync: true,
    auto_launch: false,
    color_scheme: null,
    launch_args: [],
    notes: null,
    is_template: false,
    restart_on_crash: false,
    max_restarts: 5,
    user_data_dir: "/data/p1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    tags: [],
    status: "running",
    vnc_ws_port: 6100,
    cdp_url: "/api/profiles/p1/cdp",
    cdp_endpoint: "ws://localhost:8080/api/profiles/p1/cdp",
    resources: null,
    ...over,
  };
}

const props = {
  selectedId: null,
  onSelect: () => {},
  onNew: () => {},
};

describe("ProfileList resources", () => {
  it("shows CPU/mem for a running profile with resources", () => {
    render(
      <ProfileList
        {...props}
        profiles={[baseProfile({
          status: "running",
          resources: { cpu_percent: 42, mem_mb: 512, uptime_s: 120, proc_count: 3 },
        })]}
      />,
    );
    expect(screen.getByText("CPU 42% · 512MB")).toBeTruthy();
  });

  it("hides the resources span when the profile is stopped", () => {
    render(
      <ProfileList
        {...props}
        profiles={[baseProfile({ status: "stopped", resources: null })]
      }
      />,
    );
    expect(screen.queryByText(/CPU \d+% · \d+MB/)).toBeNull();
  });
});
