"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type ChatAutoScrollOptions = {
  threshold?: number;
};

type ScheduleScrollOptions = {
  force?: boolean;
  doubleFrame?: boolean;
};

export function useChatAutoScroll({ threshold = 120 }: ChatAutoScrollOptions = {}) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const secondFrameRef = useRef<number | null>(null);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);

  const isNearBottom = useCallback(
    (element: HTMLElement) =>
      element.scrollHeight - element.scrollTop - element.clientHeight < threshold,
    [threshold],
  );

  const cancelScheduledScroll = useCallback(() => {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    if (secondFrameRef.current !== null) {
      window.cancelAnimationFrame(secondFrameRef.current);
      secondFrameRef.current = null;
    }
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = scrollContainerRef.current;
    if (!container) return;

    bottomRef.current?.scrollIntoView({ behavior, block: "end" });
    container.scrollTo({ top: container.scrollHeight, behavior });
  }, []);

  const scheduleScrollToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth", options: ScheduleScrollOptions = {}) => {
      const { force = false, doubleFrame = false } = options;
      if (force) setAutoScrollEnabled(true);

      cancelScheduledScroll();
      frameRef.current = window.requestAnimationFrame(() => {
        const container = scrollContainerRef.current;
        if (!container) return;
        if (!force && !autoScrollEnabled && !isNearBottom(container)) return;

        const run = () => scrollToBottom(behavior);
        if (!doubleFrame) {
          run();
          return;
        }

        secondFrameRef.current = window.requestAnimationFrame(run);
      });
    },
    [autoScrollEnabled, cancelScheduledScroll, isNearBottom, scrollToBottom],
  );

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    setAutoScrollEnabled(isNearBottom(container));
  }, [isNearBottom]);

  const forceScrollToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth", doubleFrame = true) => {
      scheduleScrollToBottom(behavior, { force: true, doubleFrame });
    },
    [scheduleScrollToBottom],
  );

  const scrollIfEnabled = useCallback(
    (behavior: ScrollBehavior = "auto", doubleFrame = false) => {
      scheduleScrollToBottom(behavior, { doubleFrame });
    },
    [scheduleScrollToBottom],
  );

  useEffect(() => cancelScheduledScroll, [cancelScheduledScroll]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => {
            if (!autoScrollEnabled) return;
            scheduleScrollToBottom("auto", { doubleFrame: true });
          });
    const mutationObserver =
      typeof MutationObserver === "undefined"
        ? null
        : new MutationObserver(() => {
            if (!autoScrollEnabled) return;
            scheduleScrollToBottom("auto", { doubleFrame: true });
          });

    resizeObserver?.observe(container);
    mutationObserver?.observe(container, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => {
      resizeObserver?.disconnect();
      mutationObserver?.disconnect();
    };
  }, [autoScrollEnabled, scheduleScrollToBottom]);

  return {
    scrollContainerRef,
    bottomRef,
    autoScrollEnabled,
    handleScroll,
    scrollToBottom,
    scheduleScrollToBottom,
    forceScrollToBottom,
    scrollIfEnabled,
  };
}
