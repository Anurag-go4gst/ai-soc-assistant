/**
 * Frontend correlation/message IDs only — not for auth, sessions, or security decisions.
 */

function uuidV4FromBytes(bytes: Uint8Array): string {
  const normalized = bytes.slice(0, 16);
  normalized[6] = (normalized[6] & 0x0f) | 0x40;
  normalized[8] = (normalized[8] & 0x3f) | 0x80;
  const hex = Array.from(normalized, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function newClientId(): string {
  const cryptoObj = globalThis.crypto;
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID();
  }
  if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') {
    const bytes = new Uint8Array(16);
    cryptoObj.getRandomValues(bytes);
    return uuidV4FromBytes(bytes);
  }
  return `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
