import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useBenchmark } from '../../context/BenchmarkContext';
import { ScientificHeatmap } from '../common/ScientificHeatmap';

// Calibrated Distinct Colors for Model Comparison:
// Model A: Electric Cyan (#06b6d4 / #0284c7)
// Model B: Neon Rose/Amber (#f43f5e / #e11d48)
const COLOR_MODEL_A = '#0284c7';
const COLOR_MODEL_B = '#e11d48';

export const ComparisonPage: React.FC = () => {
  const { modelA, modelB, recordsModelA, recordsModelB, isDark } = useBenchmark();
  const [viewMode, setViewMode] = useState<'diff' | 'side-by-side'>('diff');

  // Compute metrics for Model A
  const metricsA = useMemo(() => {
    const total = recordsModelA.length;
    const lexical = total > 0 ? recordsModelA.filter(r => r.lexical_match).length / total : 0;
    const semantic = total > 0 ? recordsModelA.filter(r => r.semantic_correct).length / total : 0;
    const confused = recordsModelA.filter(r => r.category === 'Correct but Denied/Confused').length;
    const latencies = recordsModelA.map(r => r.latency_sec).filter(l => l > 0);
    const avgLat = latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0;

    return { total, lexical, semantic, confused, avgLat };
  }, [recordsModelA]);

  // Compute metrics for Model B
  const metricsB = useMemo(() => {
    const total = recordsModelB.length;
    const lexical = total > 0 ? recordsModelB.filter(r => r.lexical_match).length / total : 0;
    const semantic = total > 0 ? recordsModelB.filter(r => r.semantic_correct).length / total : 0;
    const confused = recordsModelB.filter(r => r.category === 'Correct but Denied/Confused').length;
    const latencies = recordsModelB.map(r => r.latency_sec).filter(l => l > 0);
    const avgLat = latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0;

    return { total, lexical, semantic, confused, avgLat };
  }, [recordsModelB]);

  // Delta calculations (Model B minus Model A)
  const deltaSemantic = (metricsB.semantic - metricsA.semantic) * 100;
  const deltaLatency = metricsB.avgLat - metricsA.avgLat;

  // Accuracy curves by context tokens for both models
  const comparativeCurve = useMemo(() => {
    const contexts = Array.from(new Set(recordsModelA.map(r => r.context_tokens_binned))).sort((a, b) => a - b);

    return contexts.map((tokens) => {
      const rowsA = recordsModelA.filter(r => r.context_tokens_binned === tokens);
      const rowsB = recordsModelB.filter(r => r.context_tokens_binned === tokens);

      const semA = rowsA.length > 0 ? (rowsA.filter(r => r.semantic_correct).length / rowsA.length) * 100 : 0;
      const semB = rowsB.length > 0 ? (rowsB.filter(r => r.semantic_correct).length / rowsB.length) * 100 : 0;

      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        [modelA]: Number(semA.toFixed(1)),
        [modelB]: Number(semB.toFixed(1)),
      };
    });
  }, [recordsModelA, recordsModelB, modelA, modelB]);

  // 2D Difference Matrix Data
  const depths = useMemo(() => {
    return Array.from(new Set(recordsModelA.map(r => r.depth_pct))).sort((a, b) => b - a);
  }, [recordsModelA]);

  const contexts = useMemo(() => {
    return Array.from(new Set(recordsModelA.map(r => r.context_tokens_binned))).sort((a, b) => a - b);
  }, [recordsModelA]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Model Comparison Lab</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20 font-semibold">
              Head-to-Head
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Comparative analysis with distinct color systems highlighting retrieval deltas, repudiation differences and latency.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center space-x-1.5 p-1 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
          <button
            onClick={() => setViewMode('diff')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              viewMode === 'diff'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            Delta Matrix View
          </button>
          <button
            onClick={() => setViewMode('side-by-side')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              viewMode === 'side-by-side'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            Dual Grid View
          </button>
        </div>
      </div>

      {/* Model Badges Legend Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Model A Card */}
        <div className="bg-white dark:bg-slate-900/90 border border-sky-300 dark:border-cyan-500/30 rounded-2xl p-4 flex items-center justify-between shadow-sm">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-sky-100 dark:bg-cyan-500/10 border border-sky-300 dark:border-cyan-500/30 flex items-center justify-center font-mono font-bold text-sky-700 dark:text-cyan-400 text-sm">
              A
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-slate-900 dark:text-white text-sm">{modelA}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-100 text-sky-800 dark:bg-cyan-500/10 dark:text-cyan-300 border border-sky-300 dark:border-cyan-500/20 font-bold">
                  Primary Model
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Ocean Blue Color System</p>
            </div>
          </div>

          <div className="text-right">
            <span className="font-mono text-xl font-bold text-sky-600 dark:text-cyan-400">
              {(metricsA.semantic * 100).toFixed(0)}%
            </span>
            <span className="block text-[10px] text-slate-500 dark:text-slate-400 uppercase tracking-wider font-mono">
              Semantic Correct
            </span>
          </div>
        </div>

        {/* Model B Card */}
        <div className="bg-white dark:bg-slate-900/90 border border-rose-300 dark:border-rose-500/30 rounded-2xl p-4 flex items-center justify-between shadow-sm">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-rose-100 dark:bg-rose-500/10 border border-rose-300 dark:border-rose-500/30 flex items-center justify-center font-mono font-bold text-rose-700 dark:text-rose-400 text-sm">
              B
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-slate-900 dark:text-white text-sm">{modelB}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-100 text-rose-800 dark:bg-rose-500/10 dark:text-rose-300 border border-rose-300 dark:border-rose-500/20 font-bold">
                  Comparative Model
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Crimson Rose Color System</p>
            </div>
          </div>

          <div className="text-right">
            <span className="font-mono text-xl font-bold text-rose-600 dark:text-rose-400">
              {(metricsB.semantic * 100).toFixed(0)}%
            </span>
            <span className="block text-[10px] text-slate-500 dark:text-slate-400 uppercase tracking-wider font-mono">
              Semantic Correct
            </span>
          </div>
        </div>
      </div>

      {/* Head-to-Head Deltas Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Delta Semantic */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs space-y-1 shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 block font-medium">Δ Semantic Correctness</span>
          <div className="flex items-baseline space-x-2">
            <span
              className={`font-mono text-2xl font-bold ${
                deltaSemantic > 0 ? 'text-rose-600 dark:text-rose-400' : deltaSemantic < 0 ? 'text-sky-600 dark:text-cyan-400' : 'text-slate-500'
              }`}
            >
              {deltaSemantic > 0 ? `+${deltaSemantic.toFixed(1)}%` : `${deltaSemantic.toFixed(1)}%`}
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
              {deltaSemantic > 0 ? `${modelB} leads` : deltaSemantic < 0 ? `${modelA} leads` : 'Equal'}
            </span>
          </div>
        </div>

        {/* Delta Latency */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs space-y-1 shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 block font-medium">Δ Average Latency (Speed)</span>
          <div className="flex items-baseline space-x-2">
            <span
              className={`font-mono text-2xl font-bold ${
                deltaLatency < 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'
              }`}
            >
              {deltaLatency > 0 ? `+${deltaLatency.toFixed(2)}s` : `${deltaLatency.toFixed(2)}s`}
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
              {deltaLatency < 0 ? `${modelB} is faster` : `${modelA} is faster`}
            </span>
          </div>
        </div>

        {/* Delta Denial Count */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs space-y-1 shadow-sm">
          <span className="text-slate-500 dark:text-slate-400 block font-medium">Repudiated / Confused Cases</span>
          <div className="flex items-baseline space-x-3 font-mono text-sm pt-1">
            <span className="text-sky-600 dark:text-cyan-400 font-bold">{modelA}: {metricsA.confused}</span>
            <span className="text-slate-400">vs</span>
            <span className="text-rose-600 dark:text-rose-400 font-bold">{modelB}: {metricsB.confused}</span>
          </div>
        </div>
      </div>

      {/* Comparative Overlaid Retrieval Curves */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Overlaid Context Degradation Curves ({modelA} vs. {modelB})
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">Tokens scaling</span>
        </div>

        <div className="h-80 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={comparativeCurve} margin={{ top: 10, right: 25, left: -10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
              <XAxis dataKey="context" stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
              <YAxis stroke={isDark ? '#94a3b8' : '#64748b'} domain={[0, 105]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: isDark ? '#090d16' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#cbd5e1',
                  color: isDark ? '#ffffff' : '#0f172a',
                  borderRadius: '0.75rem',
                  fontSize: '12px',
                }}
                formatter={(value: any) => [`${value}%`]}
              />
              <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
              <Line
                type="monotone"
                dataKey={modelA}
                stroke={COLOR_MODEL_A}
                strokeWidth={3}
                dot={{ r: 5, fill: COLOR_MODEL_A }}
                activeDot={{ r: 7 }}
              />
              <Line
                type="monotone"
                dataKey={modelB}
                stroke={COLOR_MODEL_B}
                strokeWidth={3}
                strokeDasharray="5 5"
                dot={{ r: 5, fill: COLOR_MODEL_B }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Heatmap Section: Dual Grid View OR Authentic Scientific Contiguous Delta Matrix */}
      {viewMode === 'side-by-side' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Dual 2D Heatmaps ({modelA} vs. {modelB})
            </h3>
            <span className="text-xs font-mono text-slate-500">Side-by-Side Contiguous Matrices</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-slate-900 border border-sky-200 dark:border-cyan-500/30 rounded-2xl p-6 shadow-sm">
              <ScientificHeatmap
                records={recordsModelA}
                title={`${modelA} Heatmap Matrix`}
                subtitle="Primary model retrieval performance across context length × depth"
                showInspector={false}
              />
            </div>
            <div className="bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-500/30 rounded-2xl p-6 shadow-sm">
              <ScientificHeatmap
                records={recordsModelB}
                title={`${modelB} Heatmap Matrix`}
                subtitle="Comparative model retrieval performance across context length × depth"
                showInspector={false}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Cell-by-Cell Advantage Matrix ({modelA} vs. {modelB})
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Contiguous scientific difference matrix: shows which model dominates each specific $(Depth \times Context)$ coordinate.
              </p>
            </div>

            <div className="flex items-center space-x-3 text-xs font-mono">
              <div className="flex items-center space-x-1.5">
                <span className="w-3 h-3 rounded bg-sky-500" />
                <span className="text-slate-700 dark:text-slate-300 text-[11px] font-semibold">{modelA} Leads</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-3 h-3 rounded bg-slate-300 dark:bg-slate-700" />
                <span className="text-slate-500 dark:text-slate-400 text-[11px]">Tied</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-3 h-3 rounded bg-rose-500" />
                <span className="text-slate-700 dark:text-slate-300 text-[11px] font-semibold">{modelB} Leads</span>
              </div>
            </div>
          </div>

          {/* Authentic Contiguous Scientific Delta Heatmap Plot */}
          <div className="bg-slate-50/60 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-inner">
            <div className="flex items-stretch justify-center gap-4 sm:gap-6 overflow-x-auto py-2">
              
              {/* Main Matrix Area */}
              <div className="flex flex-col min-w-[500px] flex-1 max-w-4xl">
                
                {/* Top Grid Area with Y-axis label, ticks, and cells */}
                <div className="flex items-stretch">
                  {/* Y-Axis Label: Needle Depth */}
                  <div className="w-9 shrink-0 flex items-center justify-center pr-2 select-none">
                    <span
                      className="font-bold text-xs text-slate-600 dark:text-slate-400 uppercase tracking-wider font-mono -rotate-90 whitespace-nowrap"
                      style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                    >
                      Needle depth
                    </span>
                  </div>

                  {/* Y-Axis Ticks */}
                  <div
                    className="w-14 shrink-0 flex flex-col justify-between pr-2 text-right select-none font-mono text-xs font-bold text-slate-700 dark:text-slate-300"
                    style={{ height: `${Math.max(300, depths.length * 90)}px` }}
                  >
                    {depths.map((d) => (
                      <div key={d} className="flex-1 flex items-center justify-end">
                        <span>{d}%</span>
                      </div>
                    ))}
                  </div>

                  {/* Continuous Flush Heatmap Grid */}
                  <div
                    className="flex-1 border border-slate-300 dark:border-slate-700/80 rounded-lg overflow-hidden shadow-sm"
                    style={{ height: `${Math.max(300, depths.length * 90)}px` }}
                  >
                    <div
                      className="grid h-full w-full gap-[1px] bg-slate-300 dark:bg-slate-700/80"
                      style={{
                        gridTemplateColumns: `repeat(${contexts.length}, minmax(0, 1fr))`,
                        gridTemplateRows: `repeat(${depths.length}, minmax(0, 1fr))`,
                      }}
                    >
                      {depths.map((d) =>
                        contexts.map((c) => {
                          const rowsA = recordsModelA.filter(r => r.depth_pct === d && r.context_tokens_binned === c);
                          const rowsB = recordsModelB.filter(r => r.depth_pct === d && r.context_tokens_binned === c);

                          const scoreA = rowsA.length > 0 ? (rowsA.filter(r => r.semantic_correct).length / rowsA.length) * 100 : 0;
                          const scoreB = rowsB.length > 0 ? (rowsB.filter(r => r.semantic_correct).length / rowsB.length) * 100 : 0;
                          const diff = scoreB - scoreA;

                          let bg = isDark ? '#1e293b' : '#f1f5f9';
                          let textColor = isDark ? '#94a3b8' : '#64748b';
                          let label = 'Tied';

                          if (diff > 5) {
                            // Model B Leads (Rose gradient)
                            const intensity = Math.min(1, Math.max(0.25, Math.abs(diff) / 60));
                            bg = isDark ? `rgba(225, 29, 72, ${intensity * 0.75})` : `rgba(244, 63, 94, ${intensity * 0.65})`;
                            textColor = intensity > 0.5 ? '#ffffff' : (isDark ? '#fecdd3' : '#881337');
                            label = `+${diff.toFixed(0)}% ${modelB.split('-')[0]}`;
                          } else if (diff < -5) {
                            // Model A Leads (Cyan/Blue gradient)
                            const intensity = Math.min(1, Math.max(0.25, Math.abs(diff) / 60));
                            bg = isDark ? `rgba(2, 132, 199, ${intensity * 0.75})` : `rgba(14, 165, 233, ${intensity * 0.65})`;
                            textColor = intensity > 0.5 ? '#ffffff' : (isDark ? '#bae6fd' : '#0369a1');
                            label = `+${Math.abs(diff).toFixed(0)}% ${modelA.split('-')[0]}`;
                          }

                          return (
                            <div
                              key={`${d}-${c}`}
                              style={{ backgroundColor: bg, color: textColor }}
                              className="relative flex flex-col items-center justify-center p-3 cursor-pointer transition-all select-none hover:brightness-105"
                            >
                              <span className="font-mono text-lg sm:text-xl font-black tracking-tight leading-none drop-shadow-sm">
                                {label}
                              </span>
                              <span className="font-mono text-[11px] font-semibold opacity-90 mt-1.5">
                                {scoreA.toFixed(0)}% vs {scoreB.toFixed(0)}%
                              </span>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                {/* Bottom X-Axis Ticks */}
                <div className="flex items-start pt-2">
                  <div className="w-[92px] shrink-0" />
                  <div
                    className="flex-1 grid"
                    style={{
                      gridTemplateColumns: `repeat(${contexts.length}, minmax(0, 1fr))`,
                    }}
                  >
                    {contexts.map((c) => (
                      <div key={c} className="text-center font-mono select-none px-1">
                        <span className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white block">
                          {c.toLocaleString()}
                        </span>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-mono -mt-0.5">
                          tokens
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Bottom X-Axis Label */}
                <div className="flex items-center justify-center pt-2 select-none">
                  <span className="font-bold text-xs text-slate-600 dark:text-slate-400 uppercase tracking-wider font-mono">
                    Context length (tokens)
                  </span>
                </div>
              </div>

              {/* Diverging Colorbar Legend */}
              <div className="flex items-center space-x-2 select-none pl-2 shrink-0">
                <div
                  className="w-4 rounded-md border border-slate-300 dark:border-slate-700 shadow-sm"
                  style={{
                    height: `${Math.max(300, depths.length * 90)}px`,
                    background:
                      'linear-gradient(to top, #0284c7 0%, #38bdf8 35%, #94a3b8 50%, #fb7185 65%, #e11d48 100%)',
                  }}
                />

                <div
                  className="flex flex-col justify-between text-[10px] font-mono font-bold text-slate-600 dark:text-slate-400"
                  style={{ height: `${Math.max(300, depths.length * 90)}px` }}
                >
                  <div className="flex items-center space-x-1 text-rose-600 dark:text-rose-400">
                    <span className="w-1.5 h-[1px] bg-rose-500" />
                    <span>{modelB.split('-')[0]} Leads</span>
                  </div>
                  <div className="flex items-center space-x-1 text-slate-500">
                    <span className="w-1.5 h-[1px] bg-slate-400" />
                    <span>Tied (0%)</span>
                  </div>
                  <div className="flex items-center space-x-1 text-sky-600 dark:text-sky-400">
                    <span className="w-1.5 h-[1px] bg-sky-500" />
                    <span>{modelA.split('-')[0]} Leads</span>
                  </div>
                </div>

                <div
                  className="font-bold text-xs text-slate-600 dark:text-slate-400 uppercase tracking-wider font-mono pl-1"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                >
                  Advantage Delta
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
