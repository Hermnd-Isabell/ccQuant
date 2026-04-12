import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { PayoffData } from "../types";

interface Props {
  data: PayoffData;
  compact?: boolean;
}

export function PayoffChart({ data, compact = false }: Props) {
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
    if (!chartInstance.current || !data) return;

    // 防御性数据检查
    const underlyingPrices = data.underlyingPrices || [];
    const payoffs = data.payoffs || [];

    if (underlyingPrices.length === 0 || payoffs.length === 0) return;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        formatter: (params: any) => {
          const p = params[0];
          return `标的价格: ${p.name}<br/>盈亏: ¥${Number(p.value).toFixed(2)}`;
        },
      },
      grid: compact
        ? { left: '8%', right: '5%', bottom: '12%', top: '8%' }
        : { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        data: underlyingPrices.map((p: number) => p.toFixed(3)),
        name: compact ? undefined : "标的价格",
        nameTextStyle: { color: "#5f6368" },
        boundaryGap: false,
        axisLine: { show: !compact, lineStyle: { color: "#dadce0" } },
        axisTick: { show: false },
        axisLabel: { color: "#5f6368", fontSize: compact ? 10 : 12, interval: compact ? 5 : 'auto' },
      },
      yAxis: {
        type: "value",
        name: compact ? undefined : "盈亏",
        nameTextStyle: { color: "#5f6368" },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: "#5f6368",
          fontSize: compact ? 10 : 12,
          formatter: (v: number) => compact ? `¥${v.toFixed(0)}` : `¥${v.toFixed(0)}`,
        },
        splitLine: { lineStyle: { color: "#f1f3f4", type: compact ? 'dashed' : 'solid' } },
      },
      series: [
        {
          name: data.label || "到期盈亏",
          type: "line",
          data: payoffs,
          smooth: false,
          lineStyle: { width: compact ? 2 : 3, color: "#1a73e8" },
          itemStyle: { color: "#1a73e8" },
          areaStyle: {
            color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(26, 115, 232, 0.2)" },
              { offset: 1, color: "rgba(26, 115, 232, 0.02)" },
            ]),
          },
          markLine: {
            silent: true,
            lineStyle: { color: "#ea4335", type: "dashed", width: compact ? 1 : 2 },
            data: [{ yAxis: 0 }],
          },
        },
      ],
    };
    chartInstance.current.setOption(option, true);
  }, [data, compact]);

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
}
