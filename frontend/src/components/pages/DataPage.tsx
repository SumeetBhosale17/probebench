import React, { useState } from 'react';
import {
  FileSpreadsheet,
  FileCode,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useBenchmark } from '../../context/BenchmarkContext';
import { FilterBar } from '../common/FilterBar';
import { CATEGORY_BG_CLASSES } from '../../utils/taxonomy';

export const DataPage: React.FC = () => {
  const { filteredRecords, activeDatasetName } = useBenchmark();
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 12;

  const totalPages = Math.ceil(filteredRecords.length / pageSize) || 1;
  const paginatedRows = filteredRecords.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const exportCSV = () => {
    const headers = [
      'context_tokens',
      'depth_pct',
      'needle',
      'predicted',
      'success',
      'lexical_match',
      'semantic_correct',
      'category',
      'latency_sec',
    ];

    const csvRows = [headers.join(',')];

    for (const r of filteredRecords) {
      const values = [
        r.context_tokens,
        r.depth_pct,
        `"${r.needle.replace(/"/g, '""')}"`,
        `"${r.predicted.replace(/"/g, '""')}"`,
        r.success,
        r.lexical_match,
        r.semantic_correct,
        `"${r.category}"`,
        r.latency_sec.toFixed(3),
      ];
      csvRows.push(values.join(','));
    }

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `probebench_${activeDatasetName.replace(/[^a-zA-Z0-9]/g, '_')}_annotated.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(filteredRecords, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `probebench_${activeDatasetName.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Raw Data Explorer & Export</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20 font-semibold">
              Data Inspector
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Search, inspect, and export all annotated benchmark test instances.
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex items-center space-x-2.5">
          <button
            onClick={exportCSV}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={exportJSON}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-800 dark:text-white text-xs font-semibold border border-slate-200 dark:border-slate-700 transition-colors shadow-sm"
          >
            <FileCode className="w-4 h-4 text-emerald-600 dark:text-sky-400" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      <FilterBar />

      {/* Table Container */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-900 dark:text-white">
            Showing {paginatedRows.length} rows (Page {currentPage} of {totalPages})
          </span>

          <div className="flex items-center space-x-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 disabled:opacity-40 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span className="font-mono text-xs text-slate-500 dark:text-slate-400 px-1 font-bold">
              {currentPage} / {totalPages}
            </span>

            <button
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 disabled:opacity-40 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Data Grid */}
        <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 font-mono text-[11px]">
              <tr>
                <th className="py-2.5 px-3">context_tokens</th>
                <th className="py-2.5 px-3">depth_pct</th>
                <th className="py-2.5 px-3 min-w-[200px]">needle</th>
                <th className="py-2.5 px-3 min-w-[250px]">predicted</th>
                <th className="py-2.5 px-3">success</th>
                <th className="py-2.5 px-3">lexical_match</th>
                <th className="py-2.5 px-3">semantic_correct</th>
                <th className="py-2.5 px-3">category</th>
                <th className="py-2.5 px-3">latency_sec</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-[11px]">
              {paginatedRows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 text-emerald-700 dark:text-emerald-400 font-bold whitespace-nowrap">
                    {r.context_tokens.toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 text-slate-700 dark:text-slate-300 whitespace-nowrap">
                    {r.depth_pct}%
                  </td>
                  <td className="py-2.5 px-3 font-sans text-slate-800 dark:text-slate-300 max-w-xs truncate" title={r.needle}>
                    {r.needle}
                  </td>
                  <td className="py-2.5 px-3 font-sans text-slate-800 dark:text-slate-300 max-w-md truncate" title={r.predicted}>
                    {r.predicted}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className={r.success ? 'text-emerald-700 dark:text-emerald-400 font-bold' : 'text-slate-400'}>
                      {String(r.success)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className={r.lexical_match ? 'text-emerald-700 dark:text-emerald-400 font-bold' : 'text-slate-400'}>
                      {String(r.lexical_match)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className={r.semantic_correct ? 'text-emerald-700 dark:text-emerald-400 font-bold' : 'text-rose-700 dark:text-rose-400 font-bold'}>
                      {String(r.semantic_correct)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${CATEGORY_BG_CLASSES[r.category]}`}>
                      {r.category}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                    {r.latency_sec.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
