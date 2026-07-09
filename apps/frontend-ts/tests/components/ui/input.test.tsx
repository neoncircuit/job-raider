/**
 * Job Raider - UI Input Component Tests
 *
 * Tests for the Input UI component.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/ui/input';

describe('Input Component', () => {
  it('should render input element', () => {
    render(<Input />);
    const input = screen.getByRole('textbox');
    expect(input).toBeInTheDocument();
  });

  it('should accept user input', async () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText('Enter text');

    await userEvent.type(input, 'Hello World');
    expect(input).toHaveValue('Hello World');
  });

  it('should apply type prop correctly', () => {
    const { container } = render(<Input type="email" />);
    const input = container.querySelector('input[type="email"]');
    expect(input).toBeInTheDocument();
  });

  it('should be disabled when disabled prop is true', () => {
    render(<Input disabled />);
    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });

  it('should apply placeholder text', () => {
    render(<Input placeholder="Search..." />);
    const input = screen.getByPlaceholderText('Search...');
    expect(input).toBeInTheDocument();
  });

  it('should call onChange when value changes', async () => {
    let value = '';
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      value = e.target.value;
    };

    render(<Input onChange={handleChange} />);
    const input = screen.getByRole('textbox');

    await userEvent.type(input, 'test');
    expect(value).toBe('test');
  });

  it('should apply className prop', () => {
    const { container } = render(<Input className="custom-input" />);
    const input = container.querySelector('.custom-input');
    expect(input).toBeInTheDocument();
  });
});
