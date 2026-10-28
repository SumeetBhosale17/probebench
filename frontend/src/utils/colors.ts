export interface ColorStop {
  t: number;
  r: number;
  g: number;
  b: number;
}

// Authentic Plotly / ColorBrewer RdYlGn (Red-Yellow-Green) colormap
// 0.00 -> #d73027 (crimson red)
// 0.25 -> #f46d43 (coral orange)
// 0.50 -> #fee08b (warm yellow)
// 0.75 -> #a6d96a (light green)
// 1.00 -> #1a9850 (deep emerald green)
export const RD_YL_GN_STOPS: ColorStop[] = [
  { t: 0.0, r: 215, g: 48, b: 39 },
  { t: 0.25, r: 244, g: 109, b: 67 },
  { t: 0.5, r: 254, g: 224, b: 139 },
  { t: 0.75, r: 166, g: 217, b: 106 },
  { t: 1.0, r: 26, g: 152, b: 80 },
];

export function interpolateRdYlGn(value: number): {
  bg: string;
  textColor: string;
  hex: string;
  r: number;
  g: number;
  b: number;
} {
  const clamped = Math.max(0, Math.min(1, isNaN(value) ? 0 : value));
  let r = RD_YL_GN_STOPS[0].r;
  let g = RD_YL_GN_STOPS[0].g;
  let b = RD_YL_GN_STOPS[0].b;

  for (let i = 0; i < RD_YL_GN_STOPS.length - 1; i++) {
    const s1 = RD_YL_GN_STOPS[i];
    const s2 = RD_YL_GN_STOPS[i + 1];
    if (clamped >= s1.t && clamped <= s2.t) {
      const span = s2.t - s1.t;
      const factor = span === 0 ? 0 : (clamped - s1.t) / span;
      r = Math.round(s1.r + factor * (s2.r - s1.r));
      g = Math.round(s1.g + factor * (s2.g - s1.g));
      b = Math.round(s1.b + factor * (s2.b - s1.b));
      break;
    }
  }

  const bg = `rgb(${r}, ${g}, ${b})`;
  const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  // Standard luminance formula for high contrast text readability
  const luminance = (r * 0.299 + g * 0.587 + b * 0.114) / 255;
  const textColor = luminance > 0.62 ? '#0f172a' : '#ffffff';

  return { bg, textColor, hex, r, g, b };
}
