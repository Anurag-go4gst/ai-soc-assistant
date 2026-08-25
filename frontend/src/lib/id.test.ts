import { afterEach, describe, expect, it, vi } from 'vitest';
import { newClientId } from '@/lib/id';

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('newClientId', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses randomUUID when available', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '11111111-1111-4111-8111-111111111111',
    });
    expect(newClientId()).toBe('11111111-1111-4111-8111-111111111111');
  });

  it('falls back to getRandomValues with UUID v4 shape', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (arr: Uint8Array) => {
        arr.set(Array.from({ length: arr.length }, (_, index) => index));
        return arr;
      },
    });
    const id = newClientId();
    expect(id).toMatch(UUID_V4);
  });

  it('does not throw when crypto is undefined', () => {
    vi.stubGlobal('crypto', undefined);
    const id = newClientId();
    expect(id.startsWith('client-')).toBe(true);
  });

  it('does not throw when randomUUID is not a function', () => {
    vi.stubGlobal('crypto', { randomUUID: 'not-a-function', getRandomValues: undefined });
    const id = newClientId();
    expect(id.startsWith('client-')).toBe(true);
  });
});
