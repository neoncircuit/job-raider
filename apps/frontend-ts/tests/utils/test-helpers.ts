/**
 * Job Raider - Test Helpers
 *
 * Common test utility functions to reduce test code duplication.
 * Provides custom render functions, user interaction helpers, and assertions.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { render, RenderOptions } from "@testing-library/react";
import { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { vi, expect } from "vitest";

/**
 * Custom render function that includes global providers
 *
 * @param ui - React component to render
 * @param options - Render options from Testing Library
 * @returns Render result with queries
 */
export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  // Add any global providers here (QueryClient, ThemeProvider, etc.)
  // For now, using default render
  return render(ui, options);
}

/**
 * Create a mock function with TypeScript typing
 *
 * @returns Mock function
 */
export function createMockFn() {
  return vi.fn();
}

/**
 * Wait for async operations to complete
 *
 * @param ms - Milliseconds to wait (default: 0 for next tick)
 * @returns Promise that resolves after delay
 */
export function waitForAsync(ms: number = 0): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Create a mock file object for file upload testing
 *
 * @param filename - Name of the file
 * @param content - Content of the file
 * @param mimeType - MIME type of the file
 * @returns Mock File object
 */
export function createMockFile(
  filename: string,
  content: string,
  mimeType: string,
): File {
  const file = new File([content], filename, { type: mimeType });
  Object.defineProperty(file, "name", {
    value: filename,
    configurable: true,
  });
  return file;
}

/**
 * Mock window.location for testing navigation
 *
 * @param href - Location href to set
 */
export function mockLocation(href: string = "http://localhost:3000") {
  // window.location is readonly; cast to a mutable shape for the test mock.
  const mockWindow = window as unknown as { location?: Location };
  delete mockWindow.location;
  mockWindow.location = { href } as unknown as Location;
}

/**
 * Helper to type in input fields
 *
 * @param element - Input element
 * @param value - Value to type
 */
export async function typeInInput(element: HTMLElement, value: string) {
  const user = userEvent.setup();
  await user.clear(element);
  await user.type(element, value);
}

/**
 * Helper to select option from dropdown
 *
 * @param element - Select element or trigger
 * @param optionText - Text of option to select
 */
export async function selectOption(element: HTMLElement, optionText: string) {
  const user = userEvent.setup();
  await user.click(element);

  const option = document.querySelector(
    `option[value="${optionText}"]`,
  ) as HTMLElement;
  if (option) {
    await user.click(option);
  }
}

/**
 * Helper to wait for loading state to complete
 *
 * @param selector - Selector for loading element
 */
export async function waitForLoadingComplete(
  selector: string = '[data-loading="true"]',
) {
  const { waitFor } = await import("@testing-library/react");
  await waitFor(
    () => {
      const loadingElements = document.querySelectorAll(selector);
      expect(loadingElements.length).toBe(0);
    },
    { timeout: 5000 },
  );
}

/**
 * Helper to check if element has text content
 *
 * @param element - Element to check
 * @param text - Expected text content
 */
export function hasTextContent(element: HTMLElement, text: string): boolean {
  return element.textContent?.includes(text) ?? false;
}

/**
 * Helper to find element by data-testid
 *
 * @param testId - Data test id attribute value
 * @returns Element or null
 */
export function findByTestId(testId: string): HTMLElement | null {
  return document.querySelector(`[data-testid="${testId}"]`);
}

/**
 * Helper to click element by data-testid
 *
 * @param testId - Data test id attribute value
 */
export async function clickByTestId(testId: string) {
  const element = findByTestId(testId);
  if (!element) {
    throw new Error(`Element with testid "${testId}" not found`);
  }

  const user = userEvent.setup();
  await user.click(element);
}

/**
 * Mock localStorage for testing
 */
export class MockLocalStorage {
  private store: Record<string, string> = {};

  get length(): number {
    return Object.keys(this.store).length;
  }

  clear(): void {
    this.store = {};
  }

  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }

  setItem(key: string, value: string): void {
    this.store[key] = value;
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  key(index: number): string | null {
    const keys = Object.keys(this.store);
    return keys[index] ?? null;
  }
}

/**
 * Setup mock localStorage
 */
export function setupMockLocalStorage() {
  const mockStorage = new MockLocalStorage();
  vi.stubGlobal("localStorage", mockStorage);
  return mockStorage;
}

/**
 * Helper to test responsive breakpoints
 */
export const breakpoints = {
  xs: "375px",
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1536px",
};

/**
 * Set viewport size for responsive testing
 *
 * @param width - Viewport width
 * @param height - Viewport height
 */
export function setViewport(width: string, height: string = "800px") {
  window.innerWidth = parseInt(width);
  window.innerHeight = parseInt(height);
  window.dispatchEvent(new Event("resize"));
}
