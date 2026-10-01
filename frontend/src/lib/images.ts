// ESPN publishes crests and logos as 500px PNGs (up to ~240 KB each). Its image service
// returns the same transparent PNG at the size we actually draw, which is a fraction of the bytes.
const ESPN_IMAGE = /^https:\/\/a\.espncdn\.com(\/i\/[^?#]+\.png)$/;
const BUCKETS = [64, 128, 256, 500]; // few distinct sizes, so the CDN and browser caches hit

export function sizedLogo(url: string, cssPx: number): string {
  const match = ESPN_IMAGE.exec(url);
  if (!match) return url;
  const needed = cssPx * Math.min(typeof window === "undefined" ? 1 : window.devicePixelRatio || 1, 2);
  const px = BUCKETS.find((b) => b >= needed) ?? 500;
  return px >= 500 ? url : `https://a.espncdn.com/combiner/i?img=${match[1]}&w=${px}&h=${px}`;
}
