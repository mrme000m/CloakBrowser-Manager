import { describe, expect, it, vi } from "vitest";
import {
  MAC_CMD_SHORTCUTS,
  XK_Control_L,
  XK_Super_L,
  XK_Super_R,
  XK_v,
  isMacCmdShortcut,
  isPasteShortcut,
  sendCtrlCombo,
  sendPasteKeys,
} from "./vncKeys";

const key = (over: Partial<Parameters<typeof isPasteShortcut>[0]> = {}) => ({
  code: "KeyV",
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  ...over,
});

describe("isPasteShortcut", () => {
  it("matches Ctrl+V (Windows/Linux hosts)", () => {
    expect(isPasteShortcut(key({ ctrlKey: true }))).toBe(true);
  });

  it("matches Cmd+V (macOS hosts)", () => {
    expect(isPasteShortcut(key({ metaKey: true }))).toBe(true);
  });

  it("is layout-independent (uses code, not key)", () => {
    // e.code stays "KeyV" even on Cyrillic/etc. layouts
    expect(isPasteShortcut(key({ metaKey: true }))).toBe(true);
  });

  it("rejects plain V and modified variants", () => {
    expect(isPasteShortcut(key())).toBe(false);
    expect(isPasteShortcut(key({ ctrlKey: true, shiftKey: true }))).toBe(false);
    expect(isPasteShortcut(key({ ctrlKey: true, altKey: true }))).toBe(false);
    expect(isPasteShortcut(key({ code: "KeyC", ctrlKey: true }))).toBe(false);
  });
});

describe("isMacCmdShortcut", () => {
  it.each(["KeyC", "KeyX", "KeyA", "KeyZ", "KeyY"])("matches Cmd+%s", (code) => {
    expect(isMacCmdShortcut(key({ code, metaKey: true }))).toBe(true);
  });

  it("does not match Cmd+V (paste has its own clipboard path)", () => {
    expect(isMacCmdShortcut(key({ metaKey: true }))).toBe(false);
  });

  it("requires Cmd alone", () => {
    expect(isMacCmdShortcut(key({ code: "KeyC" }))).toBe(false);
    expect(isMacCmdShortcut(key({ code: "KeyC", ctrlKey: true }))).toBe(false);
    expect(isMacCmdShortcut(key({ code: "KeyC", metaKey: true, altKey: true }))).toBe(false);
  });
});

describe("sendCtrlCombo", () => {
  it("releases both Super keys before the stroke (macOS Cmd would otherwise be held)", () => {
    const rfb = { sendKey: vi.fn() };
    sendCtrlCombo(rfb, MAC_CMD_SHORTCUTS.KeyC, "KeyC");

    expect(rfb.sendKey.mock.calls).toEqual([
      [XK_Super_L, "MetaLeft", false],
      [XK_Super_R, "MetaRight", false],
      [XK_Control_L, "ControlLeft", true],
      [MAC_CMD_SHORTCUTS.KeyC, "KeyC", true],
      [MAC_CMD_SHORTCUTS.KeyC, "KeyC", false],
      [XK_Control_L, "ControlLeft", false],
    ]);
  });
});

describe("sendPasteKeys", () => {
  it("sends Ctrl+V so the guest pastes from its synced clipboard", () => {
    const rfb = { sendKey: vi.fn() };
    sendPasteKeys(rfb);

    const calls = rfb.sendKey.mock.calls;
    expect(calls.at(-3)).toEqual([XK_v, "KeyV", true]);
    expect(calls.at(-2)).toEqual([XK_v, "KeyV", false]);
    expect(calls.at(-1)).toEqual([XK_Control_L, "ControlLeft", false]);
  });
});
