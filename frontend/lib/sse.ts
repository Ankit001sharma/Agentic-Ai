"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL } from "./api";

export type LiveEvent = {
  type: string;
  request_id?: string;
  user?: string;
  tier?: string;
  conv_id?: string;
  model_used?: string;
  model_requested?: string;
  fallback?: boolean;
  verdict?: string;
  output_verdict?: string;
  risk?: number;
  output_risk?: number;
  latency_ms?: number;
  pipeline_stage?: number;
  intent?: string;
  tool_id?: string;
  tool_executed?: boolean;
  simulated?: boolean;
  categories_in?: string[];
  categories_out?: string[];
  prompt_preview?: string;
  response_preview?: string;
  pipeline_error?: unknown;
  ts?: number;
  sentinel?: Record<string, unknown>;
};

export function useLiveEvents(maxItems = 80): LiveEvent[] {
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
    es.onerror = () => {
      /* browser reconnects */
    };
    return () => {
      es.close();
    };
  }, [maxItems]);

  return events;
}
