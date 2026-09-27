/**
 * `/api/setup`, shared by the status bar and the setup screen.
 *
 * One small store rather than a fetch per component, so a settings change made on the setup screen moves the
 * port in the status bar at the same moment. It changes rarely, so reading it with `useStore` is fine.
 */
import { useEffect } from "react";
import { useStore } from "zustand";
import { createStore } from "zustand/vanilla";

import { ApiError, api } from "@/api/client";
import type { SettingsChange, SettingsResult, SetupInfo } from "@/api/types";

const setupStore = createStore<{ setup: SetupInfo | null }>()(() => ({
  setup: null,
}));

export function useSetup(): SetupInfo | null {
  return useStore(setupStore, (state) => state.setup);
}

/**
 * Keep the setup info fresh: poll every `pollMs` while given, otherwise fetch once if nothing is held yet.
 *
 * Once packets flow the port is not news and the live socket reports everything that changes, so the
 * status bar stops polling then rather than asking every two seconds for nothing.
 */
export function useSetupPoll(pollMs: number | null): void {
  useEffect(() => {
    if (pollMs === null && setupStore.getState().setup !== null) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        setupStore.setState({ setup: await api.setup(controller.signal) });
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError || error instanceof TypeError) setupStore.setState({ setup: null });
      }
      if (pollMs !== null && !controller.signal.aborted) timer = setTimeout(() => void poll(), pollMs);
    };

    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [pollMs]);
}

/** Save and rebind. The reply is the new setup info as well, so the store takes it straight away. */
export async function saveSettings(change: SettingsChange): Promise<SettingsResult> {
  const result = await api.saveSettings(change);
  setupStore.setState({ setup: result });
  return result;
}
