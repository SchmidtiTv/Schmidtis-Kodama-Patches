// Better Lyrics names the voices of a duet v1 (lead), v2 (the other voice, drawn on the right) and
// v1000 (everyone). Kodama's TTML parser calls the same three lead, featured and group.
const AGENT = { lead: "v1", featured: "v2", group: "v1000" };

const ms = (s) => Math.max(0, Math.round(s * 1000));
const lineText = (line) =>
  line.wordSync ? (line.words || []).map((w) => w.text).join("") : line.text || "";

// Kodama keeps a space as a word of its own; Braccato expects it on the end of the word before, the
// way Better Lyrics' own lyrics carry it. A space with no word before it is dropped.
function toParts(words, background) {
  const parts = [];
  for (const w of words || []) {
    if (w.isSpace) {
      if (parts.length) parts[parts.length - 1].words += w.text;
      continue;
    }
    parts.push({
      startTimeMs: ms(w.time),
      durationMs: Math.max(0, ms(w.end) - ms(w.time)),
      words: w.text,
      ...(background ? { isBackground: true } : {}),
    });
  }
  return parts;
}

// Kodama's lines are { time, endTime, text | words[], bgWords?, agentRole? } in seconds.
// Translations and romaji are not part of this: Braccato builds a line from its words alone and
// takes what goes under it afterwards (see decorate below).
export function toBraccatoLyrics(lines) {
  if (!Array.isArray(lines)) return [];
  return lines.map((line, i) => {
    const text = lineText(line);
    const next = lines[i + 1]?.time;
    const end = line.endTime ?? (next != null && next > line.time ? next : line.time + 5);
    const out = {
      key: String(i),
      startTimeMs: ms(line.time),
      durationMs: Math.max(0, ms(end) - ms(line.time)),
      words: text.trim() ? text : "",
    };
    let parts = line.wordSync ? toParts(line.words, false) : [];
    if (line.bgWords?.length) {
      // A line-synced line with background vocals: the main text becomes one part spanning the
      // line, so the background parts have something to sit beside.
      if (!line.wordSync && out.words)
        parts = [{ startTimeMs: out.startTimeMs, durationMs: out.durationMs, words: out.words }];
      parts = parts.concat(toParts(line.bgWords, true));
    }
    if (parts.length) out.parts = parts;
    if (line.agentRole && AGENT[line.agentRole]) out.agent = AGENT[line.agentRole];
    return out;
  });
}
