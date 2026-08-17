import type { EcScenarioSummary } from '@/components/ec/types';

const TOKEN_RE = /[a-z0-9]+/gi;

function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function tokens(text: string): Set<string> {
  const normalized = normalize(text);
  const out = new Set<string>();
  for (const match of normalized.matchAll(TOKEN_RE)) {
    const token = match[0].toLowerCase();
    if (token.length > 1) out.add(token);
  }
  return out;
}

export interface EcQuerySuggestion {
  scenario_id: string;
  label: string;
  question: string;
  score: number;
}

function phraseEntries(scenarios: EcScenarioSummary[]): Array<{ scenario_id: string; label: string; question: string }> {
  const rows: Array<{ scenario_id: string; label: string; question: string }> = [];
  for (const scenario of scenarios) {
    const phrases = [scenario.query, scenario.canonical_query, ...(scenario.aliases ?? [])].filter(
      (phrase): phrase is string => Boolean(phrase),
    );
    const seen = new Set<string>();
    for (const phrase of phrases) {
      if (seen.has(phrase)) continue;
      seen.add(phrase);
      rows.push({ scenario_id: scenario.scenario_id, label: scenario.label, question: phrase });
    }
  }
  return rows;
}

export function scoreQueryMatch(userText: string, candidate: string): number {
  const userNorm = normalize(userText);
  const candNorm = normalize(candidate);
  if (!userNorm) return 0;
  if (userNorm === candNorm) return 1;
  if (candNorm.includes(userNorm)) return 0.92;
  const userTokens = tokens(userText);
  const candTokens = tokens(candidate);
  if (!userTokens.size || !candTokens.size) return 0;
  let overlap = 0;
  for (const token of userTokens) {
    if (candTokens.has(token)) overlap += 1;
  }
  if (!overlap) return 0;
  const recall = overlap / userTokens.size;
  const precision = overlap / candTokens.size;
  return (2 * recall * precision) / (recall + precision);
}

export function suggestEcQueries(scenarios: EcScenarioSummary[], prefix: string, limit = 8): EcQuerySuggestion[] {
  const trimmed = prefix.trim();
  if (trimmed.length < 2) return [];
  const scored: EcQuerySuggestion[] = [];
  for (const entry of phraseEntries(scenarios)) {
    const score = scoreQueryMatch(trimmed, entry.question);
    if (score < 0.18) continue;
    scored.push({ ...entry, score });
  }
  const bestPerScenario = new Map<string, EcQuerySuggestion>();
  for (const row of scored) {
    const current = bestPerScenario.get(row.scenario_id);
    if (!current || row.score > current.score) bestPerScenario.set(row.scenario_id, row);
  }
  return [...bestPerScenario.values()]
    .sort((a, b) => b.score - a.score || a.question.localeCompare(b.question))
    .slice(0, limit);
}

export function resolveEcQueryLocal(scenarios: EcScenarioSummary[], query: string, minScore = 0.38): EcScenarioSummary | null {
  const trimmed = query.trim();
  if (!trimmed) return null;
  let best: EcScenarioSummary | null = null;
  let bestScore = 0;
  for (const scenario of scenarios) {
    const phrases = [scenario.query, scenario.canonical_query, ...(scenario.aliases ?? [])].filter(
      (phrase): phrase is string => Boolean(phrase),
    );
    for (const phrase of phrases) {
      const score = scoreQueryMatch(trimmed, phrase);
      if (score > bestScore) {
        bestScore = score;
        best = scenario;
      }
    }
  }
  return bestScore >= minScore ? best : null;
}
