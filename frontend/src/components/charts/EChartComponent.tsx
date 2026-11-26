import React, { useEffect, useRef } from 'react';
import ReactECharts from 'echarts-for-react';

interface EChartComponentProps {
  option: any;
  height?: string | number;
  className?: string;
  loading?: boolean;
}

export const EChartComponent: React.FC<EChartComponentProps> = ({
  option,
  height = 360,
  className = "",
  loading = false
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ReactECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      try {
        chartRef.current?.getEchartsInstance()?.resize();
      } catch {}
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className={`w-full relative ${className}`} style={{ height }}>
      {loading && (
        <div className="absolute inset-0 bg-slate-50/70 dark:bg-slate-900/70 z-10 flex items-center justify-center">
          <div className="h-5 w-5 border-2 border-slate-400 border-t-solar-600 rounded-full animate-spin"></div>
        </div>
      )}
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'svg' }}
        notMerge={true}
        lazyUpdate={true}
      />
    </div>
  );
};


