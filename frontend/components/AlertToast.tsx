"use client";



import { AnimatePresence, motion } from "framer-motion";

import { ShieldAlert, X } from "lucide-react";

import { useCallback, useEffect, useRef, useState } from "react";

import { useLiveEvents } from "@/lib/sse";



function blockId(e: { request_id?: string; ts?: number }): string {

  return e.request_id ?? `noid-${e.ts ?? 0}`;

}



export function AlertToast() {

  const events = useLiveEvents(20);

  const dismissed = useRef<Set<string>>(new Set());

  const [visible, setVisible] = useState<{

    id: string;

    user?: string;

    risk?: number;

    cats: string[];

  } | null>(null);

  const visibleRef = useRef(visible);

  visibleRef.current = visible;



  const dismiss = useCallback(() => {

    setVisible((v) => {

      if (v) {

        dismissed.current.add(v.id);

        if (dismissed.current.size > 200) {

          const arr = [...dismissed.current];

          dismissed.current = new Set(arr.slice(-100));

        }

      }

      return null;

    });

  }, []);



  useEffect(() => {

    const blocked = events.find(

      (e) => e.type === "request" && e.verdict === "BLOCK"

    );

    if (!blocked) return;

    const id = blockId(blocked);

    if (dismissed.current.has(id)) return;

    if (visibleRef.current?.id === id) return;



    setVisible({

      id,

      user: blocked.user,

      risk: blocked.risk,

      cats: blocked.categories_in || [],

    });

    const t = setTimeout(() => {

      dismissed.current.add(id);

      setVisible((cur) => (cur?.id === id ? null : cur));

    }, 5500);

    return () => clearTimeout(t);

  }, [events]);



  return (

    <AnimatePresence>

      {visible && (

        <motion.div

          initial={{ opacity: 0, y: 24, scale: 0.96 }}

          animate={{ opacity: 1, y: 0, scale: 1 }}

          exit={{ opacity: 0, y: 24, scale: 0.96 }}

          className="fixed bottom-6 right-6 z-50 panel border-danger/60 shadow-glow w-80 p-4"

        >

          <div className="flex items-start gap-3">

            <ShieldAlert className="w-6 h-6 text-danger shrink-0" />

            <div className="flex-1 min-w-0">

              <div className="font-semibold text-sm">Attack Blocked</div>

              <div className="text-xs text-muted mt-0.5">

                user <span className="text-text">{visible.user || "?"}</span> ·

                risk <span className="text-danger">{visible.risk}</span>

              </div>

              <div className="mt-2 flex flex-wrap gap-1">

                {(visible.cats || []).slice(0, 3).map((c) => (

                  <span

                    key={c}

                    className="chip border-danger/40 text-danger bg-danger/10"

                  >

                    {c}

                  </span>

                ))}

              </div>

            </div>

            <button

              type="button"

              onClick={dismiss}

              aria-label="Dismiss"

              className="shrink-0 p-1 rounded text-muted hover:text-text hover:bg-panel2 focus:outline-none focus:ring-2 focus:ring-primary/40"

            >

              <X className="w-4 h-4" />

            </button>

          </div>

        </motion.div>

      )}

    </AnimatePresence>

  );

}

