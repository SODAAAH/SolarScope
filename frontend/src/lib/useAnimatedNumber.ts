import { useState, useEffect } from 'react';

export function useAnimatedNumber(target: number, durationMs: number = 600, decimals: number = 2): string {
  const [current, setCurrent] = useState<number>(target);

  useEffect(() => {
    let startTimestamp: number | null = null;
    const initial = current;
    const diff = target - initial;
    if (Math.abs(diff) < 0.001) {
      setCurrent(target);
      return;
    }

    let frameId: number;
    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / durationMs, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setCurrent(initial + diff * ease);

      if (progress < 1) {
        frameId = requestAnimationFrame(step);
      } else {
        setCurrent(target);
      }
    };

    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [target, durationMs]);

  return current.toFixed(decimals);
}
