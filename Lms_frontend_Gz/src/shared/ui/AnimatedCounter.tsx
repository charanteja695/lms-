import { useEffect, useRef } from "react";
import { animate } from "animejs";

export function AnimatedCounter({
  value,
  duration = 800,
  formatter = (v: number) => v.toLocaleString(),
  className,
}: {
  value: number;
  duration?: number;
  formatter?: (v: number) => string;
  className?: string;
}) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(0);

  useEffect(() => {
    if (!spanRef.current) return;
    const start = prevValue.current;
    const end = value;
    prevValue.current = value;

    const obj = { val: start };
    const anim = animate(obj, {
      val: end,
      round: 1,
      ease: "outExpo",
      duration,
      onUpdate: () => {
        if (spanRef.current) {
          spanRef.current.textContent = formatter(Math.round(obj.val));
        }
      },
    });

    return () => {
      anim.pause();
    };
  }, [value, duration, formatter]);

  return (
    <span ref={spanRef} className={className}>
      {formatter(value)}
    </span>
  );
}
