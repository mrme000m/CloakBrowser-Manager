import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  /** Leading icon in the header (e.g. <Shield className="h-4 w-4 text-accent" />). */
  icon?: React.ReactNode;
  /** Extra controls rendered in the header, left of the close button. */
  headerExtra?: React.ReactNode;
  /** Override the panel width; defaults to max-w-lg. */
  panelClassName?: string;
  children: React.ReactNode;
}

/**
 * Accessible modal shell: Escape closes, clicking the overlay closes, focus
 * is moved into the panel on open and restored to the trigger on close, and
 * body scroll is locked while open. The body is provided as children; each
 * manager keeps full control over its list/form layout.
 */
export function Modal({ open, onClose, title, icon, headerExtra, panelClassName, children }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const titleId = useId();

  // Open → lock scroll, save focus, move focus into the panel.
  // Close → unlock scroll, restore focus.
  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    // Focus the panel on next paint so the element is mounted.
    const raf = requestAnimationFrame(() => panelRef.current?.focus());
    return () => {
      cancelAnimationFrame(raf);
      document.body.style.overflow = "";
      previouslyFocused.current?.focus?.();
    };
  }, [open]);

  // Escape closes (only while open).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="modal-overlay"
      onMouseDown={(e) => {
        // Close only when the overlay itself (not the panel) is pressed.
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={panelClassName ?? "modal-panel"}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            {icon}
            <h2 id={titleId} className="text-sm font-semibold truncate">
              {title}
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {headerExtra}
            <button onClick={onClose} className="icon-btn" aria-label={`Close ${title}`}>
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
