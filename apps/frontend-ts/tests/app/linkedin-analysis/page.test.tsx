/**
 * Job Raider - LinkedIn Analysis Page Tests
 *
 * Tests cover the four-tab input flow:
 * - LinkedIn URL tab submission
 * - People search tab submission and result selection
 * - Paste profile text tab submission
 *
 * Author: Job Raider
 * Date: 2026-06-28
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import LinkedInAnalysisPage from '@/app/linkedin-analysis/page';

const mockAnalyzeLinkedIn = vi.fn();
const mockSearchLinkedInPeople = vi.fn();

vi.mock('@/lib/api/profile', () => ({
  profileApi: {
    analyzeLinkedIn: (...args: unknown[]) => mockAnalyzeLinkedIn(...args),
    searchLinkedInPeople: (...args: unknown[]) => mockSearchLinkedInPeople(...args),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('LinkedInAnalysisPage', () => {
  beforeEach(() => {
    mockAnalyzeLinkedIn.mockReset();
    mockSearchLinkedInPeople.mockReset();

    mockAnalyzeLinkedIn.mockResolvedValue({
      overall_score: 78,
      summary: 'Strong profile with good keywords.',
      section_scores: [],
      insights: [],
      keyword_recommendations: [],
      action_plan: [],
      generated_headline_options: [],
      summary_rewrite_suggestions: [],
      competitive_edge: '',
      metadata: {},
      analyzed_at: '2026-06-28T12:00:00Z',
    });

    mockSearchLinkedInPeople.mockResolvedValue({
      query: { keywords: 'engineer' },
      total: 1,
      results: [
        {
          name: 'Jane Doe',
          headline: 'Software Engineer at Example',
          profile_url: 'https://www.linkedin.com/in/janedoe',
          location: 'Remote',
        },
      ],
    });
  });

  it('renders all four input tabs', () => {
    renderWithClient(<LinkedInAnalysisPage />);

    expect(screen.getByRole('tab', { name: /linkedin url/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /search profiles/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /paste profile text/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /fill sections manually/i })).toBeInTheDocument();
  });

  it('submits LinkedIn URL for analysis', async () => {
    const user = userEvent.setup();
    renderWithClient(<LinkedInAnalysisPage />);

    const urlInput = screen.getByPlaceholderText(/https:\/\/www\.linkedin\.com\/in/i);
    await user.type(urlInput, 'https://www.linkedin.com/in/testuser');

    const analyzeButton = screen.getByRole('button', { name: /analyze linkedin profile/i });
    await user.click(analyzeButton);

    await waitFor(() => {
      expect(mockAnalyzeLinkedIn).toHaveBeenCalledTimes(1);
    });
    expect(mockAnalyzeLinkedIn).toHaveBeenCalledWith({
      profile_url: 'https://www.linkedin.com/in/testuser',
    });

    expect(await screen.findByText(/strong profile with good keywords/i)).toBeInTheDocument();
  });

  it('submits pasted profile text for analysis', async () => {
    const user = userEvent.setup();
    renderWithClient(<LinkedInAnalysisPage />);

    await user.click(screen.getByRole('tab', { name: /paste profile text/i }));

    const textArea = screen.getByPlaceholderText(/copy and paste your linkedin profile content/i);
    await user.type(textArea, 'Senior engineer with cloud experience.');

    const analyzeButton = screen.getByRole('button', { name: /analyze linkedin profile/i });
    await user.click(analyzeButton);

    await waitFor(() => {
      expect(mockAnalyzeLinkedIn).toHaveBeenCalledTimes(1);
    });
    expect(mockAnalyzeLinkedIn).toHaveBeenCalledWith({
      raw_text: 'Senior engineer with cloud experience.',
    });
  });

  it('searches for profiles and selects a result', async () => {
    const user = userEvent.setup();
    renderWithClient(<LinkedInAnalysisPage />);

    await user.click(screen.getByRole('tab', { name: /search profiles/i }));

    const keywordsInput = screen.getByPlaceholderText(/e\.g\.\, react, typescript/i);
    await user.type(keywordsInput, 'engineer');

    const searchButton = screen.getByRole('button', { name: /search linkedin profiles/i });
    await user.click(searchButton);

    await waitFor(() => {
      expect(mockSearchLinkedInPeople).toHaveBeenCalledTimes(1);
    });
    expect(mockSearchLinkedInPeople).toHaveBeenCalledWith(
      expect.objectContaining({ keywords: 'engineer' }),
    );

    expect(await screen.findByText(/jane doe/i)).toBeInTheDocument();

    const selectButton = screen.getByRole('button', { name: /analyze$/i });
    await user.click(selectButton);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /linkedin url/i })).toHaveAttribute('aria-selected', 'true');
    });

    const urlInput = screen.getByPlaceholderText(/https:\/\/www\.linkedin\.com\/in/i);
    expect(urlInput).toHaveValue('https://www.linkedin.com/in/janedoe');
  });
});
