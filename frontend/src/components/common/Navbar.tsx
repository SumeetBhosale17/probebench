import React, { useRef } from 'react';
import {
  UploadCloud,
  RotateCcw,
  Sun,
  Moon,
  Layers,
  ChevronDown,
} from 'lucide-react';
import Papa from 'papaparse';
import { useBenchmark } from '../../context/BenchmarkContext';

export const Navbar: React.FC = () => {
  const {
    activeDatasetName,
    switchPreset,
    setRecordsFromCSV,
    resetFilters,
    resetToDefault,
    isDark,
    toggleTheme,
    kpi,
    filteredRecords,
    records,
  } = useBenchmark();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.data && results.data.length > 0) {
          setRecordsFromCSV(results.data as Record<string, any>[], file.name);
        } else {
          alert('Could not parse any rows from this CSV file.');
        }
      },
      error: (error) => {
        alert(`CSV parse error: ${error.message}`);
      },
    });

    if (e.target) {
      e.target.value = '';
    }
  };

  return (
    <header className="h-16 bg-white/95 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-6 flex items-center justify-between sticky top-0 z-30 transition-colors duration-200">
      {/* Left: Active Dataset Selector */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 text-xs">
          <Layers className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="text-slate-500 dark:text-slate-400 font-medium">Dataset:</span>
          
          <div className="relative group">
            <select
              aria-label="Active benchmark dataset"
              value={activeDatasetName}
              onChange={(e) => {
                const val = e.target.value;
                if (val.includes('4K-32K')) switchPreset('llama3');
                else if (val.includes('2K-8K')) switchPreset('run2');
                else if (val.includes('Combined')) switchPreset('all');
              }}
              className="appearance-none bg-slate-50 dark:bg-slate-800/90 text-slate-800 dark:text-slate-100 text-xs font-semibold pl-3 pr-8 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700/80 focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer shadow-sm hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
            >
              <option value="Llama-3-8B (4K-32K Sweep)">Meta-Llama-3-8B (4K - 32K Sweep)</option>
              <option value="Run 2 (2K-8K Short Context)">Run 2 (2K - 8K Short Context)</option>
              <option value="Combined Multi-Run Archive (72 Cases)">Combined Multi-Run Archive (72 Cases)</option>
              {!['Llama-3-8B (4K-32K Sweep)', 'Run 2 (2K-8K Short Context)', 'Combined Multi-Run Archive (72 Cases)'].includes(activeDatasetName) && (
                <option value={activeDatasetName}>{activeDatasetName} (Custom)</option>
              )}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Quick Health Status Indicator */}
        <div className="hidden lg:flex items-center space-x-3 text-xs pl-4 border-l border-slate-200 dark:border-slate-800">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500 dark:text-slate-400">Semantic Correctness:</span>
            <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
              {(kpi.semanticCorrectRate * 100).toFixed(1)}%
            </span>
          </div>

          <span className="text-slate-300 dark:text-slate-700">•</span>

          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500 dark:text-slate-400">Repudiations:</span>
            <span
              className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
                kpi.confusedCount > 0
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-400 border border-amber-300 dark:border-amber-500/30'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {kpi.confusedCount}
            </span>
          </div>
        </div>
      </div>

      {/* Right: Actions & Theme Toggle Bar */}
      <div className="flex items-center space-x-3">
        {/* Reset Filter Button if any filters are applied */}
        {filteredRecords.length !== records.length && (
          <button
            onClick={resetFilters}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-700 dark:text-sky-400 text-xs font-medium border border-slate-200 dark:border-slate-700 transition-colors"
            title="Reset active filters"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Filters</span>
          </button>
        )}

        {/* Upload Custom CSV button */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.txt"
          onChange={handleFileUpload}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-sm shadow-emerald-600/20 hover:shadow-emerald-600/40 transition-all duration-200"
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Results CSV</span>
        </button>

        {/* Restore Baseline button */}
        <button
          onClick={resetToDefault}
          className="p-2 rounded-xl text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
          title="Restore baseline dataset"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        {/* ☀️/🌙 Theme Toggle Bar: Smooth White/Black Switcher */}
        <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-xl border border-slate-200 dark:border-slate-700 shadow-inner">
          <button
            onClick={() => isDark && toggleTheme()}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200 ${
              !isDark
                ? 'bg-white text-emerald-800 shadow-sm border border-slate-200'
                : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
            title="Switch to White (Light) Theme"
          >
            <Sun className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-[11px]">Light</span>
          </button>

          <button
            onClick={() => !isDark && toggleTheme()}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200 ${
              isDark
                ? 'bg-slate-900 text-white shadow-sm border border-slate-700'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'
            }`}
            title="Switch to Black/Slate (Dark) Theme"
          >
            <Moon className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-[11px]">Dark</span>
          </button>
        </div>
      </div>
    </header>
  );
};
