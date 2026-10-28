import React, { useState, useMemo } from 'react';
import { BenchmarkRecord } from '../../types';
import { interpolateRdYlGn } from '../../utils/colors';
import { Info } from 'lucide-react';

export type HeatmapMetric =
  | 'semantic_correct'
  | 'lexical_match'
  | 'success'
  | 'denial_rate';

interface ScientificHeatmapProps {
  records: BenchmarkRecord[];
  metric?: HeatmapMetric;
  onMetricChange?: (metric: HeatmapMetric) => void;
  selectedCell?: { depth: number; context: number } | null;
  onSelectCell?: (cell: { depth: number; context: number } | null) => void;
  title?: string;
  subtitle?: string;
  showInspector?: boolean;
}

export const ScientificHeatmap: React.FC<ScientificHeatmapProps> = ({
  records,
  metric: externalMetric,
  onMetricChange,
  selectedCell: externalSelectedCell,
  onSelectCell,
  title = 'Classic NIAH heatmap: context length × depth',
  subtitle = 'Full multi-depth retrieval matrix across context sizes',
  showInspector = true,
}) => {
  const [internalMetric, setInternalMetric] = useState<HeatmapMetric>('semantic_correct');
  const [internalSelectedCell, setInternalSelectedCell] = useState<{ depth: number; context: number } | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{
    depth: number;
    context: number;
    rate: number;
    count: number;
    total: number;
  } | null>(null);

  const activeMetric = externalMetric ?? internalMetric;
  const setMetric = (m: HeatmapMetric) => {
    if (onMetricChange) onMetricChange(m);
    else setInternalMetric(m);
  };

  const selectedCell = externalSelectedCell !== undefined ? externalSelectedCell : internalSelectedCell;
  const setSelectedCell = (cell: { depth: number; context: number } | null) => {
    if (onSelectCell) onSelectCell(cell);
    else setInternalSelectedCell(cell);
  };

  // Sort depths descending (100% -> 50% -> 0%) matching Plotly go.Heatmap
  const depths = useMemo(() => {
    return Array.from(new Set(records.map(r => r.depth_pct))).sort((a, b) => b - a);
  }, [records]);

  // Sort contexts ascending (4,000 -> 8,000 -> 16,000 -> 32,000)
  const contexts = useMemo(() => {
    return Array.from(new Set(records.map(r => r.context_tokens_binned))).sort((a, b) => a - b);
  }, [records]);

  // Calculate 2D aggregation matrix
  const matrix = useMemo(() => {
    const grid: Record<string, { total: number; score: number; rate: number; rows: BenchmarkRecord[] }> = {};

    for (const d of depths) {
      for (const c of contexts) {
        const rows = records.filter(r => r.depth_pct === d && r.context_tokens_binned === c);
        const total = rows.length;

        let score = 0;
        if (total > 0) {
          if (activeMetric === 'semantic_correct') {
            score = rows.filter(r => r.semantic_correct).length;
          } else if (activeMetric === 'lexical_match') {
            score = rows.filter(r => r.lexical_match).length;
          } else if (activeMetric === 'success') {
            score = rows.filter(r => r.success).length;
          } else if (activeMetric === 'denial_rate') {
            score = rows.filter(r => r.category === 'Correct but Denied/Confused').length;
          }
        }

        const rate = total > 0 ? score / total : 0;
        grid[`${d}-${c}`] = { total, score, rate, rows };
      }
    }

    return grid;
  }, [depths, contexts, records, activeMetric]);

  const metricTabs: { id: HeatmapMetric; label: string }[] = [
    { id: 'semantic_correct', label: 'Semantic/logical correctness' },
    { id: 'lexical_match', label: 'Lexical match' },
    { id: 'success', label: 'Reported success (harness)' },
  ];

  const colorbarTicks = [
    { pct: '100%', val: 1.0 },
    { pct: '80%', val: 0.8 },
    { pct: '60%', val: 0.6 },
    { pct: '40%', val: 0.4 },
    { pct: '20%', val: 0.2 },
    { pct: '0%', val: 0.0 },
  ];

  if (depths.length === 0 || contexts.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-50 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-800">
        <p className="text-slate-600 dark:text-slate-400 font-semibold text-sm">
          No benchmark records match current filter criteria.
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Try resetting or adjusting the filters above.
        </p>
      </div>
    );
  }

  // Authentic Plotly-calibrated vertical height (360px-380px standard)
  const rowHeight = Math.max(90, Math.round(360 / Math.max(1, depths.length)));
  const gridHeight = Math.max(340, depths.length * rowHeight);

  return (
    <div className="space-y-4">
      {/* Header with Title and Streamlit Metric Radio */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight flex items-center space-x-2">
            <span>{title}</span>
          </h3>
          {subtitle && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {subtitle}
            </p>
          )}
        </div>

        {/* Metric Selector Radio Buttons matching Streamlit */}
        <div className="flex items-center space-x-1.5 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700/80 shrink-0">
          {metricTabs.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setMetric(opt.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeMetric === opt.id
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* The Authentic Scientific Heatmap Plot Container */}
      <div className="bg-slate-50/60 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-inner">
        <div className="flex items-stretch justify-center gap-4 sm:gap-6 overflow-x-auto py-2">
          
          {/* Heatmap Main Area (Y-Axis + Matrix Grid + X-Axis) */}
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

              {/* Y-Axis Ticks (Depth percentages: 100%, 50%, 0%) */}
              <div
                className="w-14 shrink-0 flex flex-col justify-between pr-2 text-right select-none font-mono text-xs font-bold text-slate-700 dark:text-slate-300"
                style={{ height: `${gridHeight}px` }}
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
                style={{ height: `${gridHeight}px` }}
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
                      const cell = matrix[`${d}-${c}`];
                      const rate = cell ? cell.rate : 0;
                      const count = cell ? cell.score : 0;
                      const total = cell ? cell.total : 0;

                      // Use RdYlGn continuous colormap (for denial rate, invert)
                      const effectiveRate = activeMetric === 'denial_rate' ? 1 - rate : rate;
                      const { bg, textColor } = interpolateRdYlGn(total > 0 ? effectiveRate : 0.5);

                      const isSelected = selectedCell?.depth === d && selectedCell?.context === c;

                      return (
                        <div
                          key={`${d}-${c}`}
                          onClick={() => {
                            setSelectedCell(isSelected ? null : { depth: d, context: c });
                          }}
                          onMouseEnter={() => {
                            setHoveredCell({ depth: d, context: c, rate, count, total });
                          }}
                          onMouseLeave={() => {
                            setHoveredCell(null);
                          }}
                          style={{
                            backgroundColor: total > 0 ? bg : undefined,
                            color: total > 0 ? textColor : undefined,
                          }}
                          className={`relative flex flex-col items-center justify-center p-3 cursor-pointer transition-all select-none ${
                            total === 0 ? 'bg-slate-200 dark:bg-slate-800 text-slate-400' : ''
                          } ${
                            isSelected
                              ? 'ring-4 ring-slate-900 dark:ring-white ring-inset z-20 scale-[1.01]'
                              : 'hover:brightness-105 hover:contrast-105'
                          }`}
                        >
                          {total > 0 ? (
                            <div className="flex flex-col items-center justify-center pointer-events-none">
                              <span className="font-mono text-2xl sm:text-3xl font-black tracking-tight leading-none drop-shadow-sm">
                                {(rate * 100).toFixed(0)}%
                              </span>
                              <span className="font-mono text-[11px] font-semibold opacity-90 mt-1.5">
                                {count}/{total} cases
                              </span>
                            </div>
                          ) : (
                            <span className="font-mono text-xs opacity-50">N/A</span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>

            {/* Bottom X-Axis Ticks (Context lengths) */}
            <div className="flex items-start pt-2">
              {/* Spacer matching Y-axis label and ticks */}
              <div className="w-[92px] shrink-0" />

              {/* X-Ticks Grid */}
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

          {/* Right Colorbar Legend (Plotly go.Heatmap style) */}
          <div className="flex items-center space-x-2 select-none pl-2 shrink-0">
            {/* Color Gradient Bar */}
            <div
              className="w-4 rounded-md border border-slate-300 dark:border-slate-700 shadow-sm"
              style={{
                height: `${gridHeight}px`,
                background:
                  'linear-gradient(to top, #d73027 0%, #f46d43 25%, #fee08b 50%, #a6d96a 75%, #1a9850 100%)',
              }}
            />

            {/* Colorbar Ticks */}
            <div
              className="flex flex-col justify-between text-[11px] font-mono font-bold text-slate-600 dark:text-slate-400"
              style={{ height: `${gridHeight}px` }}
            >
              {colorbarTicks.map((t) => (
                <div key={t.pct} className="flex items-center space-x-1">
                  <span className="w-1.5 h-[1px] bg-slate-400 dark:bg-slate-600" />
                  <span>{t.pct}</span>
                </div>
              ))}
            </div>

            {/* Colorbar Title */}
            <div
              className="font-bold text-xs text-slate-600 dark:text-slate-400 uppercase tracking-wider font-mono pl-1"
              style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
            >
              Accuracy
            </div>
          </div>
        </div>

        {/* Hover / Status Banner */}
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2 text-slate-600 dark:text-slate-300 font-mono">
            {hoveredCell ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>
                  Depth <strong>{hoveredCell.depth}%</strong> × Context{' '}
                  <strong>{hoveredCell.context.toLocaleString()} tokens</strong>:
                </span>
                <span className="font-bold text-slate-900 dark:text-white px-1.5 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  {(hoveredCell.rate * 100).toFixed(1)}% ({hoveredCell.count}/{hoveredCell.total} cases)
                </span>
              </>
            ) : (
              <span className="text-slate-500 dark:text-slate-400 flex items-center space-x-1">
                <Info className="w-3.5 h-3.5 text-slate-400" />
                <span>Click any cell on the contiguous grid to inspect individual prompt results.</span>
              </span>
            )}
          </div>

          <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
            Colorscale: <span className="font-semibold text-slate-700 dark:text-slate-300">RdYlGn</span> (Continuous [0.0, 1.0])
          </div>
        </div>
      </div>

      {/* Selected Cell Inspection Table Drawer */}
      {showInspector && selectedCell && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 animate-in fade-in duration-200">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center space-x-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h4 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white font-mono uppercase tracking-wider">
                Inspecting Cell: Depth {selectedCell.depth}% × Context {selectedCell.context.toLocaleString()} tokens
              </h4>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                {matrix[`${selectedCell.depth}-${selectedCell.context}`]?.rows.length || 0} test cases
              </span>
            </div>

            <button
              onClick={() => setSelectedCell(null)}
              className="text-xs font-semibold px-2.5 py-1 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Close Inspector
            </button>
          </div>

          <div className="space-y-3">
            {matrix[`${selectedCell.depth}-${selectedCell.context}`]?.rows.map((r, i) => (
              <div
                key={r.id || i}
                className="p-3.5 bg-slate-50/70 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 rounded-xl text-xs space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-slate-900 dark:text-white truncate">
                      {r.needle}
                    </span>
                    {r.needle_code && (
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 font-bold border border-emerald-300 dark:border-emerald-500/30">
                        {r.needle_code}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2.5 shrink-0">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        r.semantic_correct
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/30'
                          : 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300 border-rose-300 dark:border-rose-500/30'
                      }`}
                    >
                      {r.semantic_correct ? 'Semantic: Pass' : 'Semantic: Fail'}
                    </span>
                    <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {r.latency_sec.toFixed(2)}s
                    </span>
                  </div>
                </div>

                <div className="p-2.5 bg-white dark:bg-slate-900 rounded-lg border border-slate-200/80 dark:border-slate-800 font-mono text-[11px] text-slate-700 dark:text-slate-300 leading-relaxed overflow-x-auto">
                  {r.predicted}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
