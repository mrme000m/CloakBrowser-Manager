import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Test">
        body
      </Modal>,
    );
    expect(screen.queryByText("Test")).toBeNull();
  });

  it("renders the title and children as a dialog when open", () => {
    render(
      <Modal open onClose={() => {}} title="My Modal">
        modal body
      </Modal>,
    );
    expect(screen.getByText("My Modal")).toBeTruthy();
    expect(screen.getByText("modal body")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        x
      </Modal>,
    );
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when the overlay is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open onClose={onClose} title="T">
        x
      </Modal>,
    );
    const overlay = container.querySelector(".modal-overlay") as HTMLElement;
    expect(overlay).toBeTruthy();
    fireEvent.mouseDown(overlay);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when a click lands inside the panel", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open onClose={onClose} title="T">
        <button>inside</button>
      </Modal>,
    );
    const panel = container.querySelector(".modal-panel") as HTMLElement;
    expect(panel).toBeTruthy();
    fireEvent.mouseDown(panel);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("locks body scroll while open and restores on close", () => {
    const { unmount } = render(
      <Modal open onClose={() => {}} title="T">
        x
      </Modal>,
    );
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });
});
