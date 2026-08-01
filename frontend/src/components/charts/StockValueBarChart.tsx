'use client';

/**
 * Stock value bar chart.
 *
 * Charting code is loaded through a dynamic import so it is not part of the
 * initial bundle. The chart is a visual summary only; the accompanying list of
 * locations remains the accessible representation of the same data, and the
 * chart exposes a text description for screen readers.
 *
 * Requirements: 19.2, 19.5, 19.6
 */

import React from 'react';
import { formatCurrency } from '@/lib/currency';

export interface StockValueDatum {
  location_id: string;
  location_name: string;
  total_value: number;
}

interface StockValueBarChartProps {
  data: StockValueDatum[];
  /** Bars are capped so a large location list cannot render an unbounded chart. */
  maxBars?: number;
}

const BAR_HEIGHT = 20;
const BAR_GAP = 12;
const CHART_WIDTH = 480;
const LABEL_WIDTH = 150;

export function StockValueBarChart({ data, maxBars = 8 }: StockValueBarChartProps) {
  const visible = data.slice(0, maxBars);
  if (visible.length === 0) return null;

  const maxValue = Math.max(...visible.map((item) => item.total_value), 1);
  const height = visible.length * (BAR_HEIGHT + BAR_GAP);
  const barArea = CHART_WIDTH - LABEL_WIDTH - 8;

  const description = visible
    .map((item) => `${item.location_name}: ${formatCurrency(item.total_value)}`)
    .join('; ');

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`Stock value by location. ${description}`}
      >
        {visible.map((item, index) => {
          const y = index * (BAR_HEIGHT + BAR_GAP);
          const width = Math.max(2, (item.total_value / maxValue) * barArea);
          return (
            <g key={item.location_id}>
              <text
                x={0}
                y={y + BAR_HEIGHT * 0.75}
                className="fill-gray-600"
                style={{ fontSize: 12 }}
              >
                {item.location_name.length > 20
                  ? `${item.location_name.slice(0, 19)}…`
                  : item.location_name}
              </text>
              <rect
                x={LABEL_WIDTH}
                y={y}
                width={width}
                height={BAR_HEIGHT}
                rx={3}
                className="fill-blue-500"
              />
            </g>
          );
        })}
      </svg>
      {data.length > visible.length && (
        <figcaption className="mt-2 text-xs text-gray-500">
          Showing the first {visible.length} of {data.length} locations. The full list is below.
        </figcaption>
      )}
    </figure>
  );
}

export default StockValueBarChart;
