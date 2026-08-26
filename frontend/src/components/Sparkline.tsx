import { useId } from "react";

/**
 * Compact SVG sparkline used inside KPI cards.
 *
 * The chart renders a smoothed polyline plus a soft gradient fill underneath.
 * All colours are taken from CSS custom properties so the chart follows the
 * active theme (light/dark). The gradient id is derived from React's `useId`
 * so it stays stable across renders and avoids collisions when multiple
 * sparklines share the page.
 */
export function Sparkline({
  data,
  width = 60,
  height = 30,
  color = "var(--primary)",
  fillColor = "color-mix(in srgb, var(--primary) 15%, transparent)",
  strokeWidth = 1.5,
  ariaLabel,
}: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillColor?: string;
  strokeWidth?: number;
  ariaLabel?: string;
}) {
  const rawId = useId();
  if (!data || data.length === 0) {
    return null;
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const stepX = data.length > 1 ? width / (data.length - 1) : 0;
  const padding = strokeWidth * 2;
  const usableHeight = height - padding;

  const points = data.map((value, i) => {
    const x = i * stepX;
    const y = height - ((value - min) / range) * usableHeight - strokeWidth;
    return [x, y] as const;
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${width.toFixed(1)},${height.toFixed(1)} L0,${height.toFixed(1)} Z`;
  const gradientId = `sparkline-grad-${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;

  return (
    <svg
      className="sparkline"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={fillColor} />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path
        d={linePath}
        stroke={color}
        strokeWidth={strokeWidth}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
