"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL } from "./api";

export type LiveEvent = {
  type: string;
  request_id?: string;
  user?: string;
  tier?: string;
  model_used?: string;
  model_requested?: string;
  fallback?: boolean;
  verdict?: string;
  output_verdict?: string;
  risk?: number;
  output_risk?: number;
  latency_ms?: number;
  categories_in?: string[];
  categories_out?: string[];
  prompt_preview?: string;
  response_preview?: string;
  before_after?: {
    prompt_before?: string;
    prompt_after?: string;
    response_before?: string;
    response_after?: string;
  };
  ts?: number;
};

export function useLiveEvents(maxItems = 50): LiveEvent[] {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = `${API_URL}/api/events`;
    const es = new EventSource(url);
    ref.current = es;
    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as LiveEvent;
        setEvents((cur) => [data, ...cur].slice(0, maxItems));
      } catch {
        /* ignore */
      }
    };
    es.addEventListener("message", handler);
    es.addEventListener("request", handler);
    es.addEventListener("review.pending", handler);
    es.addEventListener("review.decided", handler);
    es.onerror = () => {
      // browser will auto-reconnect
    };
    return () => {
      es.close();
    };
  }, [maxItems]);

  return events;
}
