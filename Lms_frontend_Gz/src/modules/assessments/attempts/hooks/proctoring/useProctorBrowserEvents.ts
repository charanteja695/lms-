import { useCallback, useEffect, useRef, useState } from "react";

const DEVTOOLS_THRESHOLD_PX = 160;
const DEVTOOLS_POLL_MS = 2_000;

/** What the student is told about: leaving the test, or a blocked copy/cut/paste; `count` is the running total. */
export type IntegrityWarning = { kind: "left_test" | "copy_paste"; count: number };

/**
 * Fullscreen enforcement and the browser-detectable events docs/API.md lists a client may report
 * (fullscreen_exit, tab_switch, window_blur, copy_paste, right_click, devtools_open,
 * multiple_monitors, network_lost). Copy/paste and right-click are also blocked outright, per
 * proctoring-service's README ("blocking copy/paste and right-click... is the frontend's job").
 * Leaving the test (tab switch, leaving fullscreen) and copy/cut/paste also raise a warning the student must acknowledge;
 * `resume` puts the page back in fullscreen from that click.
 */
export function useProctorBrowserEvents(active: boolean, queueEvent: (type: string, detail?: Record<string, unknown>) => void) {
  const devtoolsOpen = useRef(false);
  const [warning, setWarning] = useState<IntegrityWarning | null>(null);
  const warnings = useRef(0);
  const warn = useCallback((kind: IntegrityWarning["kind"]) => {
    warnings.current += 1;
    setWarning({ kind, count: warnings.current });
  }, []);

  useEffect(() => {
    if (!active) return;

    document.documentElement.requestFullscreen?.().catch(() => undefined);

    const onFullscreenChange = () => {
      if (document.fullscreenElement) return;
      queueEvent("fullscreen_exit");
      warn("left_test");
    };
    const onVisibilityChange = () => {
      if (!document.hidden) return;
      queueEvent("tab_switch");
      warn("left_test");
    };
    const onBlur = () => queueEvent("window_blur");
    const onCopyOrPaste = (event: Event) => {
      event.preventDefault();
      queueEvent("copy_paste", { action: event.type });
      warn("copy_paste");
    };
    const onContextMenu = (event: Event) => {
      event.preventDefault();
      queueEvent("right_click");
    };
    const onOffline = () => queueEvent("network_lost");

    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("blur", onBlur);
    document.addEventListener("copy", onCopyOrPaste);
    document.addEventListener("cut", onCopyOrPaste);
    document.addEventListener("paste", onCopyOrPaste);
    document.addEventListener("contextmenu", onContextMenu);
    window.addEventListener("offline", onOffline);

    const devtoolsTimer = window.setInterval(() => {
      const isOpen = window.outerWidth - window.innerWidth > DEVTOOLS_THRESHOLD_PX || window.outerHeight - window.innerHeight > DEVTOOLS_THRESHOLD_PX;
      if (isOpen && !devtoolsOpen.current) queueEvent("devtools_open");
      devtoolsOpen.current = isOpen;
    }, DEVTOOLS_POLL_MS);

    const extendedScreen = (window.screen as unknown as { isExtended?: boolean }).isExtended;
    if (extendedScreen) queueEvent("multiple_monitors");

    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("copy", onCopyOrPaste);
      document.removeEventListener("cut", onCopyOrPaste);
      document.removeEventListener("paste", onCopyOrPaste);
      document.removeEventListener("contextmenu", onContextMenu);
      window.removeEventListener("offline", onOffline);
      window.clearInterval(devtoolsTimer);
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
    };
  }, [active, queueEvent, warn]);

  const resume = useCallback(() => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => undefined);
    setWarning(null);
  }, []);

  return { warning: active ? warning : null, resume };
}
