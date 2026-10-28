import { BenchmarkRecord, TaxonomyCategory } from '../types';

export const CODE_PATTERN = /\b[A-Z0-9]+(?:-[A-Z0-9]+){1,}\b/g;

export const DENIAL_PATTERNS = /(no important secret|no specific secret|does not (contain|mention)|doesn't (contain|mention)|not part of the actual|no mention of|\bglitch\b|\bplaceholder\b|red herring|there is no\b|none, there is|not explicitly mention|does not appear to)/i;

export const CATEGORY_ORDER: TaxonomyCategory[] = [
  'Exact / Clean Match',
  'Correct (Verbose)',
  'Correct but Denied/Confused',
  'Hallucinated / Wrong',
  'Unscored',
];

// High-contrast, stress-reducing eye-friendly color palette
export const CATEGORY_COLORS: Record<TaxonomyCategory, string> = {
  'Exact / Clean Match': '#10b981', // Emerald 500 (Calming green reduces eye strain)
  'Correct (Verbose)': '#2563eb', // Blue 600
  'Correct but Denied/Confused': '#d97706', // Amber 600
  'Hallucinated / Wrong': '#dc2626', // Red 600
  'Unscored': '#64748b', // Slate 500
};

export const CATEGORY_BG_CLASSES: Record<TaxonomyCategory, string> = {
  'Exact / Clean Match': 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/30',
  'Correct (Verbose)': 'bg-blue-50 text-blue-800 border-blue-300 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/30',
  'Correct but Denied/Confused': 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/30',
  'Hallucinated / Wrong': 'bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/30',
  'Unscored': 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-500/10 dark:text-slate-400 dark:border-slate-500/30',
};

export function extractCodes(text: string): string[] {
  if (!text || typeof text !== 'string') return [];
  const matches = text.toUpperCase().match(CODE_PATTERN);
  return matches || [];
}

export function normalizeCode(s: string | number | null | undefined): string {
  if (s == null) return '';
  return String(s).toUpperCase().replace(/[^A-Z0-9-]/g, '');
}

export function classifyRow(needle: string, predicted: string): {
  category: TaxonomyCategory;
  lexical_match: boolean;
  semantic_correct: boolean;
  needle_code: string | null;
} {
  const needleCodes = extractCodes(needle);
  const needleCode = needleCodes.length > 0 ? needleCodes[needleCodes.length - 1] : null;

  if (!needleCode) {
    return {
      category: 'Unscored',
      lexical_match: false,
      semantic_correct: false,
      needle_code: null,
    };
  }

  const predCodes = extractCodes(predicted);
  const containsCode = predCodes.includes(needleCode);
  const cleanMatch = normalizeCode(predicted) === needleCode;
  const denied = DENIAL_PATTERNS.test(predicted || '');

  let category: TaxonomyCategory;
  if (containsCode && cleanMatch) {
    category = 'Exact / Clean Match';
  } else if (containsCode && !denied) {
    category = 'Correct (Verbose)';
  } else if (containsCode && denied) {
    category = 'Correct but Denied/Confused';
  } else {
    category = 'Hallucinated / Wrong';
  }

  const lexical_match = containsCode;
  const semantic_correct = category === 'Exact / Clean Match' || category === 'Correct (Verbose)';

  return {
    category,
    lexical_match,
    semantic_correct,
    needle_code: needleCode,
  };
}

export function parseAndPrepareRow(raw: Record<string, any>, index: number, modelName = 'Default Model'): BenchmarkRecord {
  const context_tokens = parseFloat(raw.context_tokens || 0);
  const depth = parseFloat(raw.depth || 0);
  const needle = String(raw.needle || '');
  const predicted = String(raw.predicted || '');
  const latency_sec = raw.latency_sec != null ? parseFloat(raw.latency_sec) : 0;
  
  const context_tokens_binned = raw.context_tokens_binned != null
    ? Math.round(parseFloat(raw.context_tokens_binned))
    : Math.round(context_tokens / 1000) * 1000;

  const { category, lexical_match, semantic_correct, needle_code } = classifyRow(needle, predicted);
  
  let success = raw.success != null
    ? String(raw.success).toLowerCase() === 'true'
    : lexical_match;

  const depth_pct = Math.round(depth * 100);

  return {
    id: `row-${index}-${Math.random().toString(36).substring(2, 7)}`,
    context_tokens,
    depth,
    needle,
    predicted,
    success,
    latency_sec,
    context_tokens_binned,
    category,
    lexical_match,
    semantic_correct,
    needle_code,
    depth_pct,
    reported_vs_recomputed_agree: success === lexical_match,
    model_name: modelName,
  };
}
