'use client';

import { useCallback, useEffect, useRef } from 'react';

/**
 * Keeps a chat scrolled to the newest message, the way chat apps do. It follows the content as it
 * grows (messages arriving, cards rising in and folding away). Only a real scroll up by the user
 * (wheel, trackpad, touch, keys) pauses it; getting back near the bottom, or a new message, resumes it.
 * Scroll events alone never pause it: layout changes and our own scrolling fire those too.
 */
export function useStickToBottom<Scroller extends HTMLElement, Content extends HTMLElement>() {
  const scroller = useRef<Scroller>(null);
  const content = useRef<Content>(null);
  const stick = useRef(true);
  const timers = useRef<number[]>([]);

  const jump = useCallback(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, []);

  /** Back to the bottom, and again while new content animates in (cards rise for ~0.6 s). */
  const toBottom = useCallback(() => {
    stick.current = true;
    timers.current.forEach(clearTimeout);
    timers.current = [0, 120, 400, 800, 1400].map((ms) => window.setTimeout(jump, ms));
  }, [jump]);

  useEffect(() => {
    const el = scroller.current;
    const inner = content.current;
    if (!el || !inner) return;

    const nearBottom = () => el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    const pause = () => {
      if (!nearBottom()) stick.current = false;
    };
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) stick.current = false;
      else if (nearBottom()) stick.current = true;
    };
    let touchY = 0;
    const onTouchStart = (e: TouchEvent) => (touchY = e.touches[0]?.clientY ?? 0);
    const onTouchMove = (e: TouchEvent) => {
      if ((e.touches[0]?.clientY ?? 0) > touchY) stick.current = false; // finger moves down = scroll up
    };
    const onKey = (e: KeyboardEvent) => {
      if (['ArrowUp', 'PageUp', 'Home'].includes(e.key)) pause();
    };
    const onScroll = () => {
      if (nearBottom()) stick.current = true;
    };
    const follow = new ResizeObserver(jump);

    el.scrollTop = el.scrollHeight; // open at the newest message, no animation
    el.addEventListener('wheel', onWheel, { passive: true });
    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: true });
    el.addEventListener('keydown', onKey);
    el.addEventListener('scroll', onScroll, { passive: true });
    inner.addEventListener('animationend', jump);
    inner.addEventListener('transitionend', jump);
    follow.observe(inner);
    const pending = timers.current;
    return () => {
      el.removeEventListener('wheel', onWheel);
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('keydown', onKey);
      el.removeEventListener('scroll', onScroll);
      inner.removeEventListener('animationend', jump);
      inner.removeEventListener('transitionend', jump);
      follow.disconnect();
      pending.forEach(clearTimeout);
    };
  }, [jump]);

  return { scroller, content, toBottom };
}
