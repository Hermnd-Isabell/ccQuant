/**
 * vnpy-style 4-subplot chart: Balance, Drawdown, Daily PnL, Distribution.
 * Uses Plotly.js loaded from CDN (window.Plotly).
 */
import { useEffect, useRef, useState } from 'react';
import type { DailyResultRow } from '../types';

interface Props {
  dailyDf: DailyResultRow[];
}

export function BacktesterChart({ dailyDf }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [plotlyReady, setPlotlyReady] = useState(false);

  // Poll for Plotly.js availability (loaded from CDN asynchronously)
  useEffect(() => {
    if ((window as any).Plotly) {
      setPlotlyReady(true);
      return;
    }
    const id = setInterval(() => {
      if ((window as any).Plotly) {
        setPlotlyReady(true);
        clearInterval(id);
      }
    }, 200);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!ref.current || !dailyDf || dailyDf.length === 0) return;
    const Plotly = (window as any).Plotly;
    if (!Plotly) {
      console.warn('Plotly.js not loaded');
      return;
    }

    const dates = dailyDf.map((d) => d.date);
    const balances = dailyDf.map((d) => d.balance);
    const drawdowns = dailyDf.map((d) => d.drawdown);
    const netPnls = dailyDf.map((d) => d.net_pnl);

    // Colors for daily pnl bars
    const pnlColors = netPnls.map((v) => (v >= 0 ? '#ee6666' : '#91cc75'));

    const traceBalance = {
      x: dates, y: balances, type: 'scatter', mode: 'lines',
      name: 'Balance', line: { color: '#fac858', width: 1.5 },
      xaxis: 'x', yaxis: 'y',
    };
    const traceDrawdown = {
      x: dates, y: drawdowns, type: 'scatter', mode: 'lines',
      name: 'Drawdown', fill: 'tozeroy',
      fillcolor: 'rgba(51, 73, 127, 0.3)',
      line: { color: '#334b7f', width: 1 },
      xaxis: 'x2', yaxis: 'y2',
    };

    const tracePnl = {
      x: dates, y: netPnls, type: 'bar',
      name: 'Daily Pnl',
      marker: { color: pnlColors },
      xaxis: 'x3', yaxis: 'y3',
    };

    const traceHist = {
      x: netPnls, type: 'histogram', nbinsx: 80,
      name: 'Days',
      marker: { color: '#c4a35a' },
      xaxis: 'x4', yaxis: 'y4',
    };

    const layout: any = {
      xaxis:  { domain: [0, 1], anchor: 'y',  showticklabels: false },
      xaxis2: { domain: [0, 1], anchor: 'y2', showticklabels: false },
      xaxis3: { domain: [0, 1], anchor: 'y3', showticklabels: false },
      xaxis4: { domain: [0, 1], anchor: 'y4', title: { text: 'PnL', font: { size: 10 } } },
      yaxis:  { domain: [0.78, 1.0],  anchor: 'x',  title: { text: 'Balance', font: { size: 10 } } },
      yaxis2: { domain: [0.53, 0.75], anchor: 'x2', title: { text: 'Drawdown', font: { size: 10 } } },
      yaxis3: { domain: [0.28, 0.50], anchor: 'x3', title: { text: 'Daily PnL', font: { size: 10 } } },
      yaxis4: { domain: [0.0,  0.25], anchor: 'x4', title: { text: 'Days', font: { size: 10 } } },
      showlegend: false,
      margin: { l: 60, r: 20, t: 10, b: 30 },
      plot_bgcolor: '#ffffff',
      paper_bgcolor: '#ffffff',
      font: { size: 10, color: '#64748b' },
      hovermode: 'x unified',
    };

    Plotly.newPlot(ref.current, [traceBalance, traceDrawdown, tracePnl, traceHist], layout, {
      responsive: true, displayModeBar: false,
    });

    return () => {
      if (ref.current) Plotly.purge(ref.current);
    };
  }, [dailyDf, plotlyReady]);

  if (!dailyDf || dailyDf.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13 }}>
        运行回测后显示图表
      </div>
    );
  }

  if (!plotlyReady) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13 }}>
        Plotly.js 加载中，请稍候…
      </div>
    );
  }

  return <div ref={ref} style={{ width: '100%', height: '100%' }} />;
}