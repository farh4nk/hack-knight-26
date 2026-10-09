import { useId } from "react";

interface SparklineProps {
  values: number[];
  /** Minimum vertical range, so tiny sensor noise doesn't look like drama. */
  minSpan: number;
  className?: string;
}

const W = 240;
const H = 56;
const PAD = 4;

// Smooth curve through the points (quadratic through midpoints).
function smoothPath(pts: [number, number][]): string {
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2;
    const my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += ` Q ${pts[i][0].toFixed(1)} ${pts[i][1].toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L ${last[0].toFixed(1)} ${last[1].toFixed(1)}`;
}

export function Sparkline({ values, minSpan, className = "" }: SparklineProps) {
  const gradientId = useId();
  if (values.length < 3) return <div className={`h-14 ${className}`} />;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, minSpan);
  const mid = (max + min) / 2;
  const pts: [number, number][] = values.map((v, i) => [
    (i / (values.length - 1)) * W,
    PAD + (H - 2 * PAD) * (1 - (v - (mid - span / 2)) / span),
  ]);
  const line = smoothPath(pts);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={`h-14 w-full ${className}`} aria-hidden>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${line} L ${W} ${H} L 0 ${H} Z`} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
