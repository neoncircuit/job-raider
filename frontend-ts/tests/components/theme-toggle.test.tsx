/**
 * Job Raider - Theme Toggle Component Tests
 *
 * ThemeToggle reads its state from next-themes' useTheme() and takes no
 * props, so the hook is mocked rather than props being passed through.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeToggle } from '@/components/theme-toggle';
import { useTheme } from 'next-themes';

vi.mock('next-themes', () => ({
  useTheme: vi.fn(),
}));

type UseThemeReturn = ReturnType<typeof useTheme>;

describe('ThemeToggle', () => {
  it('renders the toggle button', () => {
    vi.mocked(useTheme).mockReturnValue({
      theme: 'light',
      setTheme: vi.fn(),
    } as unknown as UseThemeReturn);
    render(<ThemeToggle />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('switches to light mode when clicked in dark mode', async () => {
    const setTheme = vi.fn();
    vi.mocked(useTheme).mockReturnValue({
      theme: 'dark',
      setTheme,
    } as unknown as UseThemeReturn);
    render(<ThemeToggle />);
    // In dark mode the button is labelled "Light Mode" (the action it performs)
    await userEvent.click(screen.getByRole('button', { name: /light mode/i }));
    expect(setTheme).toHaveBeenCalledWith('light');
  });
});
