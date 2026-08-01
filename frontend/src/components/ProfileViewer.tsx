import { useEffect, useRef, useState } from "react";
import { ClipboardCopy, Code2, Maximize2, Minimize2, Copy, Check, ChevronDown } from "lucide-react";
import { api, type ProfileResources } from "../lib/api";
import {
  MAC_CMD_SHORTCUTS,
  isMacCmdShortcut,
  isPasteShortcut,
  sendCtrlCombo,
  sendPasteKeys,
} from "../lib/vncKeys";

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

interface ProfileViewerProps {
  profileId: string;
  cdpUrl: string | null;
  cdpEndpoint?: string | null;
  clipboardSync: boolean;
  authRequired?: boolean;
  onDisconnect: () => void;
}

// How long the keydown handler waits for a native `paste` event before
// falling back to the async Clipboard API (Safari).
const PASTE_FALLBACK_DELAY_MS = 200;

export function ProfileViewer({ profileId, cdpUrl, cdpEndpoint, clipboardSync: initialClipboardSync, authRequired, onDisconnect }: ProfileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<any>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [clipboardSync, setClipboardSync] = useState(initialClipboardSync);
  // Per-target "copied" feedback so only the actually-copied control shows a check.
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [cdpDropdown, setCdpDropdown] = useState(false);
  // Runtime status: geoip + active CDP client count (polled while connected)
  const [geoip, setGeoip] = useState<{ exit_ip: string | null; tz: string | null; locale: string | null }>({ exit_ip: null, tz: null, locale: null });
  const [cdpClients, setCdpClients] = useState(0);
  // Per-profile resource usage (CPU% / mem / uptime), polled while connected.
  const [resources, setResources] = useState<ProfileResources | null>(null);

  // Resolve CDP endpoint
  const cdpWsUrl = cdpEndpoint || (cdpUrl ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${cdpUrl}` : null);
  // HTTP equivalent of the WS endpoint (for /json/list curl + Playwright/Puppeteer connect snippets)
  const cdpHttpUrl = cdpWsUrl
    ? cdpWsUrl.replace(/^wss:\/\//, "https://").replace(/^ws:\/\//, "http://")
    : null;

  useEffect(() => {
    let rfb: any = null;
    let cancelled = false;

    async function connect() {
      try {
        // Import noVNC dynamically
        const { default: RFB } = await import("@novnc/novnc/core/rfb.js");

        if (cancelled) return;

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/api/profiles/${profileId}/vnc`;

        rfb = new RFB(containerRef.current!, wsUrl, {
          wsProtocols: ["binary"],
        });
        rfbRef.current = rfb;

        rfb.scaleViewport = true;
        rfb.resizeSession = false;
        rfb.showDotCursor = true;

        rfb.addEventListener("connect", () => {
          if (!cancelled) setConnected(true);
        });

        rfb.addEventListener("disconnect", () => {
          if (!cancelled) {
            setConnected(false);
            onDisconnect();
          }
        });

        rfb.addEventListener("securityfailure", (e: any) => {
          setError(`Security failure: ${e.detail.reason}`);
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to connect");
        }
      }
    }

    connect();

    return () => {
      cancelled = true;
      if (rfb) {
        try {
          rfb.disconnect();
        } catch (err) {
          console.debug("[vnc] disconnect cleanup failed:", err);
        }
      }
      rfbRef.current = null;
    };
  }, [profileId, onDisconnect]);

  // Poll per-profile status (exit IP / TZ / locale + active CDP clients) while running.
  useEffect(() => {
    if (!connected) {
      setGeoip({ exit_ip: null, tz: null, locale: null });
      setCdpClients(0);
      setResources(null);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.getProfileStatus(profileId);
        if (!cancelled) {
          setGeoip({ exit_ip: s.exit_ip, tz: s.effective_timezone, locale: s.effective_locale });
          setCdpClients(s.cdp_clients ?? 0);
          setResources(s.resources ?? null);
        }
      } catch {
        // non-fatal; status is best-effort
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [profileId, connected]);

  // Host→VNC clipboard & macOS shortcut handling.
  //
  // Paste: prefer the native `paste` event — it exposes the clipboard via
  // `clipboardData` without async-clipboard permissions and works on every
  // Chromium/Firefox. Safari doesn't fire `paste` on non-editable targets, so
  // the keydown handler falls back to `navigator.clipboard.readText()` when no
  // paste event arrives shortly after the shortcut.
  //
  // macOS Cmd+C/X/A/Z/Y: noVNC would forward these as Super+<key>, which does
  // nothing in the Linux guest — translate them to Ctrl+<key> instead.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !clipboardSync || !connected) return;

    // Timestamp of the last `paste` event we handled; lets the keydown
    // fallback tell whether the browser delivered one.
    let pasteHandledAt = 0;

    const pushTextAndPaste = async (text: string) => {
      const rfb = rfbRef.current;
      if (!rfb) return;
      if (text) {
        try {
          await api.setClipboard(profileId, text);
        } catch (err) {
          // Guest clipboard would be stale — better to paste nothing than the
          // wrong thing.
          console.warn("[clipboard] failed to push text to guest:", err);
          return;
        }
      }
      sendPasteKeys(rfb);
    };

    const handlePaste = (e: ClipboardEvent) => {
      e.preventDefault();
      pasteHandledAt = Date.now();
      void pushTextAndPaste(e.clipboardData?.getData("text/plain") ?? "");
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (isMacCmdShortcut(e)) {
        e.preventDefault();
        e.stopPropagation();
        const rfb = rfbRef.current;
        const keysym = MAC_CMD_SHORTCUTS[e.code];
        if (rfb && keysym != null) sendCtrlCombo(rfb, keysym, e.code);
        return;
      }

      if (!isPasteShortcut(e)) return;

      // Keep noVNC from forwarding the raw keystroke, but DON'T preventDefault:
      // the `paste` event is the default action of this keydown, and cancelling
      // it here would stop the browser from dispatching it.
      e.stopPropagation();
      if (e.repeat) return;

      const pressedAt = Date.now();
      window.setTimeout(() => {
        if (pasteHandledAt >= pressedAt) return; // `paste` event already handled it
        navigator.clipboard
          .readText()
          .then((text) => void pushTextAndPaste(text))
          .catch((err) => console.warn("[clipboard] readText failed:", err));
      }, PASTE_FALLBACK_DELAY_MS);
    };

    container.addEventListener("keydown", handleKeyDown, true);
    container.addEventListener("paste", handlePaste, true);
    return () => {
      container.removeEventListener("keydown", handleKeyDown, true);
      container.removeEventListener("paste", handlePaste, true);
    };
  }, [profileId, clipboardSync, connected]);

  // VNC→Host clipboard event
  useEffect(() => {
    const rfb = rfbRef.current;
    if (!rfb || !clipboardSync || !connected) return;

    const handleClipboard = (e: any) => {
      const text = e.detail?.text;
      if (text) {
        navigator.clipboard.writeText(text).catch((err) => {
          console.warn("[clipboard] writeText failed:", err);
        });
      }
    };

    rfb.addEventListener("clipboard", handleClipboard);
    return () => rfb.removeEventListener("clipboard", handleClipboard);
  }, [clipboardSync, connected]);

  // VNC→Host polling
  useEffect(() => {
    if (!clipboardSync || !connected) return;

    let cancelled = false;
    let lastText = "";

    const poll = async () => {
      if (cancelled) return;
      try {
        const { text } = await api.getClipboard(profileId);
        if (text && text !== lastText) {
          lastText = text;
          await navigator.clipboard.writeText(text).catch(() => {});
        }
      } catch {
        cancelled = true;
        return;
      }
      if (!cancelled) {
        setTimeout(poll, 2000);
      }
    };

    const timer = setTimeout(poll, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [profileId, clipboardSync, connected]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setFullscreen(true);
    } else {
      document.exitFullscreen();
      setFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFsChange = () => {
      setFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
    };
    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, []);

  const copyText = (text: string, key: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    });
  };

  // Close the CDP dropdown on Escape while it's open.
  useEffect(() => {
    if (!cdpDropdown) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setCdpDropdown(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cdpDropdown]);

  // Authorization header snippet — rendered only when the manager has auth enabled.
  // The token lives in an httponic cookie the browser can't read, so it's a placeholder.
  const headersArg = authRequired ? `, headers: {"Authorization": "Bearer <YOUR_TOKEN>"}` : "";
  const curlHeader = authRequired ? ` -H "Authorization: Bearer <YOUR_TOKEN>"` : "";
  const playwrightPython = `from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp("${cdpWsUrl}"${headersArg})`;
  const playwrightJs = `const { chromium } = require("playwright");
const browser = await chromium.connectOverCDP("${cdpWsUrl}"${headersArg ? `{${headersArg.slice(2)}}` : ""});`;
  const puppeteer = `const browser = await puppeteer.connect({
  browserWSEndpoint: "${cdpWsUrl}"${headersArg ? `,${headersArg.slice(1)}` : ""},
});`;
  const curlJson = `curl${curlHeader} ${cdpHttpUrl}/json/list`;

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Connection failed</p>
          <p className="text-gray-500 text-xs">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-surface-1 border-b border-border">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-yellow-400 animate-pulse"}`} />
          <span className="text-xs text-gray-400">
            {connected ? "Connected" : "Connecting..."}
          </span>
          {connected && cdpClients > 0 && (
            <span className="text-xs text-accent flex items-center gap-1" title="Active CDP (DevTools) client sessions">
              <Code2 className="h-3 w-3" />
              {cdpClients} CDP{cdpClients === 1 ? "" : "s"}
            </span>
          )}
          {connected && (geoip.exit_ip || geoip.tz) && (
            <span className="text-xs text-gray-500 font-mono truncate max-w-[40vw]" title="Exit IP · timezone · locale (GeoIP)">
              {geoip.exit_ip ?? "—"} · {geoip.tz ?? "—"} · {geoip.locale ?? "—"}
            </span>
          )}
          {connected && resources && (resources.cpu_percent != null || resources.mem_mb != null) && (
            <span
              className="text-xs text-gray-500 font-mono truncate max-w-[30vw]"
              title={`CPU ${resources.cpu_percent ?? "—"}% · ${(resources.mem_mb ?? 0).toFixed(0)} MB · up ${formatUptime(resources.uptime_s) ?? "—"} · ${resources.proc_count ?? "—"} proc`}
            >
              <span className="text-gray-600">·</span> CPU {resources.cpu_percent ?? "—"}% · {(resources.mem_mb ?? 0).toFixed(0)}MB · {formatUptime(resources.uptime_s) ?? "—"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* CDP dropdown */}
          {cdpWsUrl && (
            <div className="relative">
              <button
                onClick={() => setCdpDropdown(!cdpDropdown)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                  cdpDropdown ? "text-accent bg-surface-3" : "text-gray-500 hover:text-gray-300"
                }`}
                aria-label="CDP connection info"
                aria-expanded={cdpDropdown}
                aria-haspopup="menu"
                title="CDP connection info"
              >
                <Code2 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">CDP</span>
                <ChevronDown className="h-3 w-3" />
              </button>

              {cdpDropdown && (
                <>
                  {/* Click-away backdrop (sits below the panel so clicks inside the panel are never swallowed) */}
                  <div className="fixed inset-0 z-40" onClick={() => setCdpDropdown(false)} aria-hidden="true" />

                  <div className="absolute right-0 top-full mt-1 w-80 bg-surface-1 border border-border rounded-md shadow-xl z-50 p-3 animate-fade-scale-in" role="menu">
                    <h4 className="text-xs font-semibold text-gray-300 mb-2">
                      Chrome DevTools Protocol
                    </h4>

                    {/* WS URL */}
                    <div className="mb-3">
                      <label className="text-[10px] font-medium text-gray-500 uppercase mb-1 block">
                        WebSocket Endpoint
                      </label>
                      <div className="flex items-center gap-1">
                        <code className="flex-1 text-[11px] text-gray-400 font-mono bg-surface-2 rounded px-2 py-1 break-all select-all">
                          {cdpWsUrl}
                        </code>
                        <button
                          onClick={() => copyText(cdpWsUrl, "ws")}
                          className="icon-btn icon-btn-sm text-gray-500 hover:text-gray-300 flex-shrink-0"
                          aria-label="Copy WebSocket endpoint"
                          title={copiedKey === "ws" ? "Copied!" : "Copy WS URL"}
                        >
                          {copiedKey === "ws" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                        </button>
                      </div>
                    </div>

                    {/* Connect snippets */}
                    <div className="mb-3">
                      <label className="text-[10px] font-medium text-gray-500 uppercase mb-1 block">
                        Connect
                      </label>
                      {([
                        { key: "pw-python", label: "Playwright (Python)", code: playwrightPython },
                        { key: "pw-js", label: "Playwright (JS)", code: playwrightJs },
                        { key: "puppeteer", label: "Puppeteer", code: puppeteer },
                        { key: "curl", label: "curl /json/list", code: curlJson },
                      ] as const).map((s) => (
                        <div key={s.key} className="mb-1.5">
                          <div className="text-[9px] text-gray-500 mb-0.5">{s.label}</div>
                          <div className="flex items-start gap-1">
                          <pre className="flex-1 text-[10px] text-gray-400 font-mono bg-surface-2 rounded px-2 py-1 break-all max-h-14 overflow-y-auto whitespace-pre-wrap">
{s.code}
                          </pre>
                          <button
                            onClick={() => copyText(s.code, s.key)}
                            className="icon-btn icon-btn-sm text-gray-500 hover:text-gray-300 flex-shrink-0"
                            aria-label={`Copy ${s.label}`}
                            title={copiedKey === s.key ? "Copied!" : `Copy ${s.label}`}
                          >
                            {copiedKey === s.key ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                          </button>
                          </div>
                        </div>
                      ))}
                      {authRequired && (
                        <p className="text-[9px] text-gray-600 mt-1">
                          Replace <code className="text-accent">&lt;YOUR_TOKEN&gt;</code> with your auth token (required over the tunnel).
                        </p>
                      )}
                    </div>

                    {/* chrome-devtools-mcp command */}
                    <div className="mb-3">
                      <label className="text-[10px] font-medium text-gray-500 uppercase mb-1 block">
                        chrome-devtools-mcp
                      </label>
                      <div className="flex items-start gap-1">
                        <code className="flex-1 text-[10px] text-gray-400 font-mono bg-surface-2 rounded px-2 py-1.5 break-all max-h-16 overflow-y-auto">
                          npx -y chrome-devtools-mcp@latest --wsEndpoint={cdpWsUrl} --usageStatistics=false
                        </code>
                        <button
                          onClick={() => copyText(
                            `npx -y chrome-devtools-mcp@latest --wsEndpoint=${cdpWsUrl} --usageStatistics=false`,
                            "mcp-cmd",
                          )}
                          className="icon-btn icon-btn-sm text-gray-500 hover:text-gray-300 flex-shrink-0"
                          aria-label="Copy chrome-devtools-mcp command"
                          title={copiedKey === "mcp-cmd" ? "Copied!" : "Copy command"}
                        >
                          {copiedKey === "mcp-cmd" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                        </button>
                      </div>
                      <p className="text-[9px] text-gray-600 mt-0.5">
                        Add <code className="text-accent">--wsHeaders={'{"Authorization":"Bearer &lt;token&gt;"}'}</code> if auth is enabled
                      </p>
                    </div>

                    {/* MCP config */}
                    <div>
                      <label className="text-[10px] font-medium text-gray-500 uppercase mb-1 block">
                        MCP Server Config
                      </label>
                      <div className="flex items-start gap-1">
                      <pre className="flex-1 text-[10px] text-gray-400 font-mono bg-surface-2 rounded px-2 py-1.5 break-all max-h-24 overflow-y-auto">
{`{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest",
        "--wsEndpoint=${cdpWsUrl}",
        "--usageStatistics=false"],
      "enabled": true
    }
  }
}`}
                      </pre>
                      <button
                        onClick={() => copyText(
                          `{"mcpServers":{"chrome-devtools":{"command":"npx","args":["-y","chrome-devtools-mcp@latest","--wsEndpoint=${cdpWsUrl}","--usageStatistics=false"],"enabled":true}}}`,
                          "mcp-config",
                        )}
                        className="icon-btn icon-btn-sm text-gray-500 hover:text-gray-300 flex-shrink-0"
                        aria-label="Copy MCP server config"
                        title={copiedKey === "mcp-config" ? "Copied!" : "Copy config"}
                      >
                        {copiedKey === "mcp-config" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      </button>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          <button
            onClick={() => setClipboardSync(!clipboardSync)}
            className={`icon-btn ${clipboardSync ? "text-accent" : "text-gray-500 hover:text-gray-300"}`}
            aria-label={clipboardSync ? "Disable clipboard sync" : "Enable clipboard sync"}
            aria-pressed={clipboardSync}
            title={clipboardSync ? "Disable clipboard sync" : "Enable clipboard sync"}
            disabled={!connected}
          >
            <ClipboardCopy className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="icon-btn text-gray-500 hover:text-gray-300"
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* VNC canvas container */}
      <div
        ref={containerRef}
        className="flex-1 bg-black overflow-hidden"
        style={{ minHeight: 0 }}
      />
    </div>
  );
}
