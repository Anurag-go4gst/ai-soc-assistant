const ZERO_WIDTH_CHARS = /[\u200B-\u200D\uFEFF]/g;

/** Normalize user input for slash-command matching. */
export function normalizeChatCommandInput(raw: string): string {
  return raw
    .trim()
    .replace(ZERO_WIDTH_CHARS, '')
    .replace(/\uFF0F/g, '/')
    .toLowerCase()
    .replace(/[.!?]+$/, '');
}

/** True when the user intends to reset the chat (e.g. /clear, clear). */
export function isClearChatCommand(raw: string): boolean {
  const normalized = normalizeChatCommandInput(raw);
  return normalized === '/clear' || normalized === 'clear';
}
