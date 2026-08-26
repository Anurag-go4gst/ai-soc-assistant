import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ChatPanel } from './ChatPanel';

afterEach(() => cleanup());

describe('ChatPanel production empty state', () => {
  it('does not render demo picker or Run scenario controls; composer remains', () => {
    render(<ChatPanel />);
    expect(screen.queryByText(/demo scenario/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^run$/i })).not.toBeInTheDocument();
    expect(document.querySelector('[data-testid="demo-scenario-picker"]')).toBeNull();
    expect(screen.getByPlaceholderText(/ask v\.ai soc/i)).toBeInTheDocument();
  });
});
