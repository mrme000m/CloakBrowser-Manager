/**
 * Keystroke injection helpers for the noVNC viewer.
 *
 * The guest session is Linux/X11, so paste/copy shortcuts must arrive as
 * Ctrl+<key>. On macOS hosts the browser reports Cmd as the Meta modifier and
 * noVNC forwards it as Super, which leaves Super held in the guest when we
 * inject a Ctrl combo — these helpers clear that state first.
 */

// X11 keysyms for the modifiers and keys we inject.
export const XK_Control_L = 0xffe3;
export const XK_Super_L = 0xffeb;
export const XK_Super_R = 0xffec;
export const XK_v = 0x0076;

/**
 * macOS Cmd+<key> shortcuts translated into Ctrl+<key> for the guest, keyed by
 * `KeyboardEvent.code` (layout-independent). Paste (KeyV) is intentionally
 * absent — it needs clipboard transfer, handled separately.
 */
export const MAC_CMD_SHORTCUTS: Record<string, number> = {
  KeyC: 0x0063,
  KeyX: 0x0078,
  KeyA: 0x0061,
  KeyZ: 0x007a,
  KeyY: 0x0079,
};

interface RfbLike {
  sendKey(keysym: number, code: string, down: boolean): void;
}

interface ShortcutEventLike {
  code: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
}

/** Ctrl+V or Cmd+V (Shift excluded — Ctrl+Shift+V stays with noVNC). */
export function isPasteShortcut(e: ShortcutEventLike): boolean {
  return e.code === "KeyV" && !e.altKey && !e.shiftKey && (e.ctrlKey || e.metaKey);
}

/** macOS Cmd+shortcut that should reach the guest as Ctrl+shortcut. */
export function isMacCmdShortcut(e: ShortcutEventLike): boolean {
  return (
    e.metaKey &&
    !e.ctrlKey &&
    !e.altKey &&
    Object.prototype.hasOwnProperty.call(MAC_CMD_SHORTCUTS, e.code)
  );
}

/**
 * Release both Super keys in the guest. noVNC forwards the macOS Cmd keydown
 * as Super_L before our capture-phase handler can intercept the combo, so the
 * guest would otherwise see Super+Ctrl+<key> instead of Ctrl+<key>.
 */
export function releaseSuperModifiers(rfb: RfbLike): void {
  rfb.sendKey(XK_Super_L, "MetaLeft", false);
  rfb.sendKey(XK_Super_R, "MetaRight", false);
}

/** Send a full Ctrl+<key> stroke (down/up) with stuck Cmd/Super cleared. */
export function sendCtrlCombo(rfb: RfbLike, keysym: number, code: string): void {
  releaseSuperModifiers(rfb);
  rfb.sendKey(XK_Control_L, "ControlLeft", true);
  rfb.sendKey(keysym, code, true);
  rfb.sendKey(keysym, code, false);
  rfb.sendKey(XK_Control_L, "ControlLeft", false);
}

/** Send Ctrl+V so the guest pastes from its own (already-synced) clipboard. */
export function sendPasteKeys(rfb: RfbLike): void {
  sendCtrlCombo(rfb, XK_v, "KeyV");
}
