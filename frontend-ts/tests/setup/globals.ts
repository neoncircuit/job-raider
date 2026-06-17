/**
 * Job Raider - Test Globals Setup
 *
 * Global test configuration and setup for Vitest.
 * Configures testing library, mocks, MSW, and global utilities.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { beforeAll, afterEach, afterAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import { setupServer } from 'msw/node';
import { handlers } from './mocks';
import React from 'react';

// Setup MSW server for API mocking
export const server = setupServer(...handlers);

// Mock IntersectionObserver
class MockIntersectionObserver implements IntersectionObserver {
  observe = vi.fn();
  disconnect = vi.fn();
  unobserve = vi.fn();
  takeRecords = vi.fn().mockReturnValue([]);
  root = null;
  rootMargin = '';
  thresholds = [];
}

beforeAll(() => {
  // Start MSW server before all tests
  server.listen({ onUnhandledRequest: 'error' });
  // Mock IntersectionObserver
  global.IntersectionObserver = MockIntersectionObserver;

  // Mock window.matchMedia
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Mock Next.js router
  vi.mock('next/navigation', () => ({
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      back: vi.fn(),
      pathname: '/',
      query: {},
    }),
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => '/',
  }));

  // Mock Next.js image optimization
  vi.mock('next/image', () => ({
    default: ({ src, alt, ...props }: React.ComponentProps<'img'>) => {
      // Use createElement instead of JSX in .ts file
      return React.createElement('img', { src, alt, ...props });
    },
  }));
});

// Cleanup after each test
afterEach(() => {
  cleanup();
  // Reset MSW handlers after each test
  server.resetHandlers();
});

// Close MSW server after all tests
afterAll(() => {
  server.close();
});
