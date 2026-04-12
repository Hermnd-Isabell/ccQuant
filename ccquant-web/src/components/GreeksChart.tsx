import { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface Props {
  history: any[];
  compact?: boolean;
}

export function GreeksChart({ history, compact = false }: Props) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (chartRef.current && !chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }
    const onResize = () => chartInstance.current?.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!chartInstance.current || !history || history.length === 0) return;
    const dates = history.map((h: any) => h.datetime?.slice(0, 10));
    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: compact ? undefined : {
        trigger: "axis",
        backgroundColor: "rgba(255, 255, 255, 0.95)",
        borderColor: "#dadce0",
        borderWidth: 1,
        textStyle: { color: "#3c4043" },
        formatter: (params: any) => {
          let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].name}</div>`;
          params.forEach((p: any) => {
            html += `<div style="display:flex;align-items:center;gap:6px">
              <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color}"></span>
              <span>${p.seriesName}: ${Number(p.value).toFixed(4)}</span>
            </div>`;
          });
          return html;
        },
      },
      legend: {
        data: ["Delta", "Gamma", "Theta", "Vega", "Rho"],
        bottom: 0,
        textStyle: { color: "#5f6368", fontSize: compact ? 10 : 12 },
        itemGap: compact ? 8 : 20,
        itemWidth: compact ? 12 : 25,
        itemHeight: compact ? 8 : 14,
      },
      grid: compact
        ? { left: '8%', right: '5%', bottom: '22%', top: '5%' }
        : { left: "3%", right: "4%", bottom: "16%", containLabel: true },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLine: { show: !compact, lineStyle: { color: "#dadce0" } },
        axisTick: { show: false },
        axisLabel: { color: "#5f6368", fontSize: compact ? 9 : 12, interval: compact ? 5 : 'auto' },
      },
      yAxis: {
        type: "value",
        name: compact ? undefined : "希腊值",
        nameTextStyle: { color: "#5f6368" },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#5f6368", fontSize: compact ? 9 : 12 },
        splitLine: { lineStyle: { color: "#f1f3f4", type: compact ? 'dashed' : 'solid' } },
      },
      series: [
        {
          name: "Delta",
          type: "line",
          data: history.map((h) => h.delta ?? 0),
          smooth: true,
          symbol: "none",
          lineStyle: { width: compact ? 1.5 : 2 },
          itemStyle: { color: "#1a73e8" },
        },
        {
          name: "Gamma",
          type: "line",
          data: history.map((h) => h.gamma ?? 0),
          smooth: true,
          symbol: "none",
          lineStyle: { width: compact ? 1.5 : 2 },
          itemStyle: { color: "#34a853" },
        },
        {
          name: "Theta",
          type: "line",
          data: history.map((h) => h.theta ?? 0),
          smooth: true,
          symbol: "none",
          lineStyle: { width: compact ? 1.5 : 2 },
          itemStyle: { color: "#f9ab00" },
        },
        {
          name: "Vega",
          type: "line",
          data: history.map((h) => h.vega ?? 0),
          smooth: true,
          symbol: "none",
          lineStyle: { width: compact ? 1.5 : 2 },
          itemStyle: { color: "#ea4335" },
        },
        {
          name: "Rho",
          type: "line",
          data: history.map((h) => h.rho ?? 0),
          smooth: true,
          symbol: "none",
          lineStyle: { width: compact ? 1.5 : 2 },
          itemStyle: { color: "#9334e6" },
        },
      ],
    };
    chartInstance.current.setOption(option, true);
  }, [history, compact]);

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
}
