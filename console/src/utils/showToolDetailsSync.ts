const STORAGE_KEY = "copaw:show_tool_details";
const EVENT_NAME = "copaw:show_tool_details";
const CHANNEL_NAME = "copaw-config";

type OnChange = (value: boolean) => void;

function parseBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (typeof parsed === "boolean") return parsed;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

export function publishShowToolDetails(value: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // ignore localStorage failures
  }

  window.dispatchEvent(
    new CustomEvent(EVENT_NAME, {
      detail: value,
    }),
  );

  try {
    if ("BroadcastChannel" in window) {
      const bc = new BroadcastChannel(CHANNEL_NAME);
      bc.postMessage({ type: EVENT_NAME, value });
      bc.close();
    }
  } catch {
    // ignore BroadcastChannel failures
  }
}

export function subscribeShowToolDetails(onChange: OnChange): () => void {
  const onCustomEvent = (event: Event) => {
    const value = parseBoolean((event as CustomEvent).detail);
    if (typeof value === "boolean") onChange(value);
  };

  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return;
    const value = parseBoolean(event.newValue);
    if (typeof value === "boolean") onChange(value);
  };

  const onBroadcast = (event: MessageEvent) => {
    const data = event.data;
    if (!data || data.type !== EVENT_NAME) return;
    const value = parseBoolean(data.value);
    if (typeof value === "boolean") onChange(value);
  };

  let bc: BroadcastChannel | null = null;
  if ("BroadcastChannel" in window) {
    bc = new BroadcastChannel(CHANNEL_NAME);
    bc.addEventListener("message", onBroadcast);
  }

  window.addEventListener(EVENT_NAME, onCustomEvent as EventListener);
  window.addEventListener("storage", onStorage);

  return () => {
    window.removeEventListener(EVENT_NAME, onCustomEvent as EventListener);
    window.removeEventListener("storage", onStorage);
    if (bc) {
      bc.removeEventListener("message", onBroadcast);
      bc.close();
    }
  };
}

