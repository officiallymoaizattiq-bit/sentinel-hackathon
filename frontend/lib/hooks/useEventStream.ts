"use client";

import { useEffect, useRef, useState } from "react";

export type StreamEvent =
  | { type: "hello" }
  | { type: "alert"; patient_id: string; call_id: string; severity: string;
      summary: string; at: string }
  | { type: "call_scored"; call_id: string; patient_id: string;
      score: Record<string, unknown>; at: string }
  | { type: "pending_call"; patient_id: string; mode: "phone" | "widget";
      at: string }
  | { type: "vitals"; patient_id: string; device_id: string;
      accepted: number; at: string };

export function useEventStream(onEvent: (e: StreamEvent) => void): {
  connected: boolean;
  reconnectAt: number | null;
} {
  const [connected, setConnected] = useState(false);
  const [reconnectAt, setReconnectAt] = useState<number | null>(null);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    let cancelled = false;
    let source: EventSource | null = null;
    let retry = 0;

    const open = () => {
      if (cancelled) return;
      // Bypass Next dev proxy which buffers SSE; hit backend direct in browser.
      const base =
        typeof window !== "undefined" &&
        (window as unknown as { SENTINEL_BACKEND?: string }).SENTINEL_BACKEND
          ? (window as unknown as { SENTINEL_BACKEND: string }).SENTINEL_BACKEND
          : (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000");
      source = new EventSource(`${base}/api/stream`, { withCredentials: true });
      source.onopen = () => {
        setConnected(true);
        setReconnectAt(null);
        retry = 0;
      };
      source.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as StreamEvent;
          handlerRef.current(data);
        } catch { /* ignore malformed */ }
      };
      source.onerror = () => {
        setConnected(false);
        source?.close();
        retry = Math.min(retry + 1, 6);
        const delay = Math.min(1000 * 2 ** retry, 30_000);
        const at = Date.now() + delay;
        setReconnectAt(at);
        setTimeout(open, delay);
      };
    };

    open();
    return () => {
      cancelled = true;
      source?.close();
    };
  }, []);

  return { connected, reconnectAt };
}
