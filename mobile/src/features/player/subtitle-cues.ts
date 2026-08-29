export type SubtitleCue = { start: number; end: number; text: string };

function timestampSeconds(value: string): number {
  const clean = value.trim().replace(',', '.');
  const parts = clean.split(':').map(Number);
  if (parts.some((part) => !Number.isFinite(part))) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] ?? 0;
}

export function parseSubtitleFile(raw: string): SubtitleCue[] {
  return raw
    .replace(/^\uFEFF/, '')
    .replace(/^WEBVTT[^\n]*\n/i, '')
    .split(/\r?\n\s*\r?\n/)
    .flatMap((block) => {
      const lines = block.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      const timingIndex = lines.findIndex((line) => line.includes('-->'));
      if (timingIndex < 0) return [];
      const [startRaw, endRaw] = lines[timingIndex].split('-->').map((part) => part.trim().split(/\s+/)[0]);
      if (!startRaw || !endRaw) return [];
      const text = lines.slice(timingIndex + 1).join('\n').replace(/<[^>]+>/g, '').trim();
      if (!text) return [];
      return [{ start: timestampSeconds(startRaw), end: timestampSeconds(endRaw), text }];
    })
    .sort((left, right) => left.start - right.start);
}
