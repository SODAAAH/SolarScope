export const PALETTE = {
  solar: '#D97706',
  solarLight: '#FEF3C7',
  load: '#475569',
  loadLight: '#F1F5F9',
  grid: '#EA580C',
  gridLight: '#FFEDD5',
  battery: '#0D9488',
  batteryLight: '#CCFBF1',
  soc: '#0284C7',
  residual: '#0284C7',
  slateDark: '#0F172A',
  slateLight: '#F8FAFC',
  border: '#E2E8F0',
  gridLine: '#F1F5F9'
};

export function getBaseEChartsOption(isDark = false) {
  const textColor = isDark ? '#94A3B8' : '#64748B';
  const gridColor = isDark ? '#1E293B' : '#F1F5F9';

  return {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 500,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 400,
    animationEasingUpdate: 'cubicInOut',
    textStyle: {
      fontFamily: 'Plus Jakarta Sans, system-ui, sans-serif'
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark ? '#1E293B' : '#FFFFFF',
      borderColor: isDark ? '#334155' : '#CBD5E1',
      borderWidth: 1,
      textStyle: {
        color: isDark ? '#F8FAFC' : '#0F172A',
        fontSize: 12
      },
      padding: [8, 12],
      extraCssText: 'box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08); border-radius: 8px;'
    },
    grid: {
      left: '3%',
      right: '3%',
      bottom: '12%',
      top: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: {
        lineStyle: {
          color: gridColor,
          type: 'dashed'
        }
      }
    }
  };
}

export const theme = {
  colors: {
    solar: PALETTE.solar,
    teal: PALETTE.battery,
    coral: PALETTE.grid,
    emerald: '#10B981',
    slate: PALETTE.load,
    residual: PALETTE.residual
  }
};
