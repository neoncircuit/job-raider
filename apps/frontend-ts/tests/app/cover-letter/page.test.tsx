/**
 * Job Raider - Cover Letter Page Tests
 *
 * Tests the dedicated Cover Letter page:
 * - Form rendering and validation
 * - Successful generation from pasted job details
 * - Deep validation toggle
 * - DOCX/PDF export
 * - Copy-to-clipboard
 *
 * Author: Job Raider
 * Date: 2026-06-29
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CoverLetterPage from '@/app/cover-letter/page';
import { sampleCoverLetter, sampleCoverLetterValidation } from '../../setup/fixtures';
import type { CoverLetterResponse } from '@/lib/types/api';

const mockGenerate = vi.hoisted(() => vi.fn());
const mockExport = vi.hoisted(() => vi.fn());
const mockDownloadFile = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api/coverLetter', () => ({
  coverLetterApi: {
    generate: (...args: unknown[]) => mockGenerate(...args),
    export: (...args: unknown[]) => mockExport(...args),
  },
  downloadFile: (...args: unknown[]) => mockDownloadFile(...args),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const sampleResponse: CoverLetterResponse = {
  success: true,
  job_id: 'manual-test-123',
  cover_letter: sampleCoverLetter,
  validation: sampleCoverLetterValidation,
};

describe('CoverLetterPage', () => {
  beforeEach(() => {
    mockGenerate.mockReset();
    mockExport.mockReset();
    mockDownloadFile.mockReset();

    mockGenerate.mockResolvedValue(sampleResponse);
    mockExport.mockResolvedValue(new Response(new Blob(['mock']), { status: 200 }));
    mockDownloadFile.mockResolvedValue(undefined);
  });

  it('renders the form and disables generate until required fields are filled', () => {
    renderWithClient(<CoverLetterPage />);

    expect(screen.getByRole('heading', { name: /cover letter/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location \(optional\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/job description/i)).toBeInTheDocument();

    const generateButton = screen.getByRole('button', { name: /generate cover letter/i });
    expect(generateButton).toBeDisabled();
  });

  it('generates a cover letter and shows the validation panel', async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), 'Senior Software Engineer');
    await user.type(screen.getByLabelText(/company/i), 'Tech Innovations Inc');
    await user.type(screen.getByLabelText(/location \(optional\)/i), 'Remote');
    await user.type(
      screen.getByLabelText(/job description/i),
      'We are seeking a talented Senior Software Engineer to join our team. ' +
        'Requirements include 5+ years of React and TypeScript experience and strong architecture skills.',
    );

    const generateButton = screen.getByRole('button', { name: /generate cover letter/i });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledTimes(1);
    });
    expect(mockGenerate).toHaveBeenCalledWith(
      {
        title: 'Senior Software Engineer',
        company: 'Tech Innovations Inc',
        description: expect.stringContaining('We are seeking a talented Senior Software Engineer'),
        location: 'Remote',
      },
      false,
      false,
    );

    expect(await screen.findByDisplayValue(sampleCoverLetter.content)).toBeInTheDocument();
    expect(screen.getByText(/ready to send/i)).toBeInTheDocument();
    expect(screen.getByText('88/100')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export docx/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export pdf/i })).toBeInTheDocument();
  });

  it('toggles deep validation and sends deep=true', async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), 'Senior Software Engineer');
    await user.type(screen.getByLabelText(/company/i), 'Tech Innovations Inc');
    await user.type(
      screen.getByLabelText(/job description/i),
      'We are seeking a talented Senior Software Engineer with React and TypeScript experience.',
    );

    const deepSwitch = screen.getByRole('switch', { name: /deep validation/i });
    await user.click(deepSwitch);
    expect(deepSwitch).toHaveAttribute('aria-checked', 'true');

    const generateButton = screen.getByRole('button', { name: /generate cover letter/i });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledTimes(1);
    });
    expect(mockGenerate).toHaveBeenCalledWith(expect.any(Object), true, false);
  });

  it('exports the generated cover letter as DOCX', async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), 'Senior Software Engineer');
    await user.type(screen.getByLabelText(/company/i), 'Tech Innovations Inc');
    await user.type(
      screen.getByLabelText(/job description/i),
      'We are seeking a talented Senior Software Engineer with React and TypeScript experience.',
    );

    await user.click(screen.getByRole('button', { name: /generate cover letter/i }));
    await screen.findByDisplayValue(sampleCoverLetter.content);

    await user.click(screen.getByRole('button', { name: /export docx/i }));

    await waitFor(() => {
      expect(mockExport).toHaveBeenCalledTimes(1);
    });
    expect(mockExport).toHaveBeenCalledWith({
      content: sampleCoverLetter.content,
      format: 'docx',
      company: 'Tech Innovations Inc',
      title: 'Senior Software Engineer',
    });
    expect(mockDownloadFile).toHaveBeenCalledTimes(1);
  });

  it('copies the generated cover letter to clipboard', async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), 'Senior Software Engineer');
    await user.type(screen.getByLabelText(/company/i), 'Tech Innovations Inc');
    await user.type(
      screen.getByLabelText(/job description/i),
      'We are seeking a talented Senior Software Engineer with React and TypeScript experience.',
    );

    await user.click(screen.getByRole('button', { name: /generate cover letter/i }));
    await screen.findByDisplayValue(sampleCoverLetter.content);

    // jsdom may not expose navigator.clipboard until after rendering, so mock it lazily.
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn() },
        configurable: true,
        writable: true,
      });
    }
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);

    await user.click(screen.getByRole('button', { name: /copy$/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(sampleCoverLetter.content);
    });
    expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument();
  });

  it('shows validation issues when the result needs revision', async () => {
    const user = userEvent.setup();
    const issuesResponse: CoverLetterResponse = {
      ...sampleResponse,
      validation: {
        ...sampleCoverLetterValidation,
        is_valid: false,
        recommendation: 'needs_revision',
        score: 62,
        issues: ['too_short', 'missing_call_to_action'],
        details: {
          ...sampleCoverLetterValidation.details,
          has_call_to_action: false,
        },
      },
    };
    mockGenerate.mockResolvedValueOnce(issuesResponse);
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), 'Senior Software Engineer');
    await user.type(screen.getByLabelText(/company/i), 'Tech Innovations Inc');
    await user.type(
      screen.getByLabelText(/job description/i),
      'We are seeking a talented Senior Software Engineer with React and TypeScript experience.',
    );

    await user.click(screen.getByRole('button', { name: /generate cover letter/i }));

    expect(await screen.findByText(/needs revision/i)).toBeInTheDocument();
    expect(screen.getByText(/too short/i)).toBeInTheDocument();
  });
});
