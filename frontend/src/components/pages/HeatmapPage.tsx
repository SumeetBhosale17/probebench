import React, { useState, useMemo } from 'react';
import {
  Layers,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { useBenchmark } from '../../context/BenchmarkContext';
import { FilterBar } from '../common/FilterBar';
import { ScientificHeatmap, HeatmapMetric } from '../common/ScientificHeatmap';

export const HeatmapPage: React.FC = () => {
  const { filteredRecords, activeDatasetName } = useBenchmark();
  const [metric, setMetric] = useState<HeatmapMetric>('semantic_correct');
  const [selectedCell, setSelectedCell] = useState<{ depth: number; context: number } | null>(null);

  // Overall metric statistics
  const stats = useMemo(() => {
    const total = filteredRecords.length;
    if (total === 0) return { mean: 0, min: 0, max: 0, nonZeroCount: 0 };

    let score = 0;
    if (metric === 'semantic_correct') {
      score = filteredRecords.filter(r => r.semantic_correct).length;
    } else if (metric === 'lexical_match') {
      score = filteredRecords.filter(r => r.lexical_match).length;
    } else if (metric === 'success') {
      score = filteredRecords.filter(r => r.success).length;
    } else {
      score = filteredRecords.filter(r => r.category === 'Correct but Denied/Confused').length;
    }

    const mean = (score / total) * 100;
    return { mean, total };
  }, [filteredRecords, metric]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              2D NIAH Heatmap Matrix
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20 font-semibold">
              Scientific Heatmap
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Contiguous RdYlGn retrieval matrix: Needle depth ($Y$-axis) versus Context window ($X$-axis).
          </p>
        </div>

        {/* Metric Selector Tabs */}
        <div className="flex items-center space-x-1.5 p-1 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
          {[
            { id: 'semantic_correct', label: 'Semantic/Logical' },
            { id: 'lexical_match', label: 'Lexical Match' },
            { id: 'success', label: 'Reported Success' },
            { id: 'denial_rate', label: 'Denial Rate' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setMetric(tab.id as HeatmapMetric)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                metric === tab.id
                  ? 'bg-emerald-600 text-white font-semibold shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filter Bar */}
      <FilterBar />

      {/* Quick Summary Pill Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              Active Metric Average
            </span>
            <span className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {stats.mean.toFixed(1)}%
            </span>
          </div>
          <div className="p-2.5 rounded-xl bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              Test Cases in View
            </span>
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-white">
              {filteredRecords.length}
            </span>
          </div>
          <div className="p-2.5 rounded-xl bg-sky-100 dark:bg-sky-500/10 text-sky-800 dark:text-sky-400">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              Selected Dataset
            </span>
            <span className="text-sm font-bold text-slate-900 dark:text-white truncate block max-w-[200px]" title={activeDatasetName}>
              {activeDatasetName}
            </span>
          </div>
          <div className="p-2.5 rounded-xl bg-amber-100 dark:bg-amber-500/10 text-amber-800 dark:text-amber-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* The Authentic Scientific Heatmap */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <ScientificHeatmap
          records={filteredRecords}
          metric={metric}
          onMetricChange={setMetric}
          selectedCell={selectedCell}
          onSelectCell={setSelectedCell}
          title="Classic NIAH heatmap: context length × depth"
          subtitle="Contiguous scientific grid with seamless adjacent tiles, RdYlGn smooth color scale and vertical accuracy colorbar."
          showInspector={true}
        />
      </div>
    </div>
  );
};
