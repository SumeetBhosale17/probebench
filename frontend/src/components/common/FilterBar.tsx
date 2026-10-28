import React from 'react';
import { Search, X, Filter } from 'lucide-react';
import { useBenchmark } from '../../context/BenchmarkContext';
import { CATEGORY_ORDER, CATEGORY_COLORS } from '../../utils/taxonomy';

export const FilterBar: React.FC = () => {
  const {
    filters,
    setFilter,
    toggleNeedleFilter,
    toggleContextFilter,
    toggleDepthFilter,
    toggleCategoryFilter,
    availableNeedles,
    availableContextTokens,
    availableDepths,
    records,
    filteredRecords,
  } = useBenchmark();

  const isFiltered = filteredRecords.length !== records.length;

  return (
    <div className="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm mb-6 space-y-3.5 transition-colors duration-200">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Section Title & Active Counts */}
        <div className="flex items-center space-x-2 text-xs">
          <Filter className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span className="font-semibold text-slate-900 dark:text-white">Interactive Filters</span>
          <span className="font-mono text-[11px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            Showing {filteredRecords.length} of {records.length} cases
          </span>
          {isFiltered && (
            <button
              onClick={() => {
                setFilter('selectedNeedles', []);
                setFilter('selectedContextTokens', []);
                setFilter('selectedDepths', []);
                setFilter('selectedCategories', []);
                setFilter('searchQuery', '');
              }}
              className="text-xs font-semibold text-rose-600 dark:text-rose-400 hover:underline"
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Right: Search Filter */}
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search prediction or needle code..."
            value={filters.searchQuery}
            onChange={(e) => setFilter('searchQuery', e.target.value)}
            className="w-full bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-700/80 rounded-xl pl-9 pr-8 py-1.5 text-xs text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-emerald-500 transition-colors"
          />
          {filters.searchQuery && (
            <button
              onClick={() => setFilter('searchQuery', '')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-xs">
        {/* 1. Needle Prompt(s) - Matching Streamlit sidebar */}
        <div>
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2 font-mono">
            Needle Prompt(s)
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setFilter('selectedNeedles', [])}
              className={`px-2 py-1 rounded-lg text-xs font-mono transition-colors ${
                filters.selectedNeedles.length === 0
                  ? 'bg-purple-600 text-white font-semibold shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              All Needles
            </button>
            {availableNeedles.map((needle, idx) => {
              const isSelected = filters.selectedNeedles.includes(needle);
              // Extract code or short label
              const codeMatch = needle.match(/\b[A-Z0-9]+(?:-[A-Z0-9]+){1,}\b/);
              const label = codeMatch ? codeMatch[0] : `Needle ${idx + 1}`;
              return (
                <button
                  key={needle}
                  onClick={() => toggleNeedleFilter(needle)}
                  title={needle}
                  className={`px-2 py-1 rounded-lg text-xs font-mono transition-colors ${
                    isSelected
                      ? 'bg-purple-600 text-white font-semibold shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-slate-200 dark:border-slate-700/60'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Context Length Chips */}
        <div>
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2 font-mono">
            Context Length (Tokens)
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setFilter('selectedContextTokens', [])}
              className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                filters.selectedContextTokens.length === 0
                  ? 'bg-emerald-600 text-white font-semibold shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              All
            </button>
            {availableContextTokens.map((tokens) => {
              const isSelected = filters.selectedContextTokens.includes(tokens);
              return (
                <button
                  key={tokens}
                  onClick={() => toggleContextFilter(tokens)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                    isSelected
                      ? 'bg-emerald-600 text-white font-semibold shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-slate-200 dark:border-slate-700/60'
                  }`}
                >
                  {tokens >= 1000 ? `${tokens / 1000}k` : tokens}
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Needle Depth Chips */}
        <div>
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2 font-mono">
            Needle Depth Position
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setFilter('selectedDepths', [])}
              className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                filters.selectedDepths.length === 0
                  ? 'bg-teal-600 text-white font-semibold shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              All
            </button>
            {availableDepths.map((depth) => {
              const isSelected = filters.selectedDepths.includes(depth);
              const label = depth === 0 ? '0% (Top)' : depth === 50 ? '50% (Mid)' : depth === 100 ? '100% (End)' : `${depth}%`;
              return (
                <button
                  key={depth}
                  onClick={() => toggleDepthFilter(depth)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-colors ${
                    isSelected
                      ? 'bg-teal-600 text-white font-semibold shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-slate-200 dark:border-slate-700/60'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Taxonomy Categories */}
        <div>
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2 font-mono">
            Diagnostic Category
          </span>
          <div className="flex flex-wrap gap-1.5">
            {CATEGORY_ORDER.filter(c => c !== 'Unscored').map((category) => {
              const isSelected = filters.selectedCategories.includes(category);
              const color = CATEGORY_COLORS[category];
              return (
                <button
                  key={category}
                  onClick={() => toggleCategoryFilter(category)}
                  className={`px-2 py-1 rounded-lg text-[11px] font-medium transition-all flex items-center space-x-1.5 border ${
                    isSelected
                      ? 'text-white border-transparent'
                      : 'bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border-slate-200 dark:border-slate-700/60'
                  }`}
                  style={{
                    backgroundColor: isSelected ? color : undefined,
                  }}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: isSelected ? '#ffffff' : color }}
                  />
                  <span>{category.replace('Match', '').replace('Correct', '').trim() || category}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
