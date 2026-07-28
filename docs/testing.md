# Job Raider - Testing Guide

## Overview

Job Raider uses a comprehensive testing strategy with unit tests, integration tests, and E2E tests to ensure code quality and prevent regressions.

## Test Frameworks

### Frontend (Next.js/TypeScript)

- **Unit Tests**: Vitest with jsdom environment
- **E2E Tests**: Playwright for cross-browser testing
- **API Mocking**: MSW (Mock Service Worker)
- **Test Utilities**: React Testing Library, @testing-library/user-event

### Backend (Python/FastAPI)

- **Unit Tests**: pytest with pytest-asyncio
- **Coverage**: pytest-cov
- **Mocking**: pytest-mock

## Running Tests Locally

### Frontend Unit Tests

```bash
cd apps/frontend-ts

# Run all tests once
npm run test

# Run tests in watch mode
npm run test -- --watch

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Run a specific test file
npm run test -- tests/basic.test.ts
```

### Frontend E2E Tests

```bash
cd apps/frontend-ts

# Run all E2E tests
npm run test:e2e

# If Docker (or another process) already owns :3000, point Playwright at a free port
PLAYWRIGHT_PORT=3001 npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui

# Run E2E tests in debug mode
npm run test:e2e:debug

# Run a specific E2E test
npx playwright test tests/e2e/basic.spec.ts
```

Playwright starts `next dev` on `PLAYWRIGHT_PORT` (default `3000`) and uses that as `baseURL`. When a local Docker stack is already bound to `:3000`, reuse would hit the container instead of your working tree — set `PLAYWRIGHT_PORT` to avoid that.
### Backend Tests

```bash
cd apps/backend-py

# Run all tests (use the venv interpreter to avoid broken shebangs)
.venv/bin/python -m pytest tests/

# Run tests with coverage
.venv/bin/python -m pytest tests/ --cov=src --cov-report=term

# Run a specific test file
.venv/bin/python -m pytest tests/unit/test_linkedin_analyzer.py

# Run tests in verbose mode
.venv/bin/python -m pytest tests/ -v
```

## Test Structure

### Frontend Tests

```
apps/frontend-ts/tests/
├── basic.test.ts              # Smoke test for test infrastructure
├── setup/
│   ├── globals.ts            # Global test setup (MSW, mocks)
│   ├── mocks.ts              # API mock handlers
│   └── fixtures.ts           # Test data fixtures
├── utils/
│   ├── test-helpers.ts       # Common test utilities
│   └── test-setup.ts         # Playwright fixtures
├── components/               # Component tests
│   └── utils/
│       └── formatting.test.ts
└── e2e/                      # E2E tests
    ├── basic.spec.ts         # Basic smoke tests
    └── smoke.spec.ts         # Application smoke tests
```

### Backend Tests

```
apps/backend-py/tests/
├── conftest.py                         # Shared pytest fixtures
├── test_cover_letter_validator.py
├── test_cover_letter_writer.py
├── test_resume_analyzer.py
├── unit/                               # Unit tests
│   ├── agents/                         # Multi-agent system tests
│   │   ├── test_base_agent.py
│   │   ├── test_communication_bus.py
│   │   └── test_config_and_rate_limit.py
│   ├── test_application_tracker.py
│   ├── test_apply_method.py
│   ├── test_assessment_api.py
│   ├── test_assessment_engine.py
│   ├── test_assessment_storage.py
│   ├── test_bm25_retriever.py
│   ├── test_chunker.py
│   ├── test_cover_letter_grounding.py  # Overlap + severity-weighted penalties
│   ├── test_cross_encoder.py
│   ├── test_deduplicate_applied_sync.py
│   ├── test_embedding_client.py
│   ├── test_gemini_client.py
│   ├── test_linkedin_analyzer.py       # LinkedIn profile analyzer
│   ├── test_metrics.py
│   ├── test_metrics_api.py
│   ├── test_models.py
│   ├── test_rag_ranker.py
│   ├── test_rrf_fusion.py
│   ├── test_scorer.py
│   ├── test_settings_api.py
│   ├── test_text_normalizer.py
│   └── test_vector_store.py
└── integration/                        # Integration tests
    ├── test_application_api.py
    ├── test_pipeline.py
    └── test_rag_pipeline.py
```

Cover-letter grounding tests verify soft versus hard penalties, double-count avoidance, and the max grounding cap. Run:

```bash
cd apps/backend-py
source .venv/bin/activate
pytest tests/unit/test_cover_letter_grounding.py tests/test_cover_letter_validator.py -q
```

## Writing Tests

### Frontend Unit Tests

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { sampleJob } from '@/tests/setup/fixtures';

describe('JobCard Component', () => {
  it('should render job title', () => {
    const { container } = render(<JobCard job={sampleJob} />);
    expect(screen.getByText('Senior Software Engineer')).toBeInTheDocument();
  });
});
```

### Frontend E2E Tests

```typescript
import { test, expect } from '@playwright/test';

test('should search for jobs', async ({ page }) => {
  await page.goto('/jobs');

  // Fill in search form
  await page.fill('input[name="keywords"]', 'Software Engineer');
  await page.fill('input[name="locations"]', 'San Francisco, CA');

  // Submit search
  await page.click('button[type="submit"]');

  // Wait for results
  await expect(page.locator('[data-testid="job-results"]')).toBeVisible();
});
```

### Backend Tests

```python
import pytest
from src.models.job_listing import JobListing

def test_job_listing_creation():
    job = JobListing(
        title='Software Engineer',
        company='Tech Corp',
        location='San Francisco, CA'
    )
    assert job.title == 'Software Engineer'
    assert job.company == 'Tech Corp'
```

## CI/CD Integration

Tests run automatically on:
- Every push to `main` or `develop` branches
- Every pull request to `main` or `develop` branches

### CI Test Stages

1. **Lint**: ESLint (frontend), Black/Flake8 (backend)
2. **Type Check**: TypeScript (frontend), mypy (backend)
3. **Unit Tests**: Vitest (frontend), pytest (backend)
4. **E2E Tests**: Playwright (frontend)
5. **Security**: Bandit (backend)

### Coverage Requirements

- **Frontend**: 80% coverage (statements, branches, functions, lines)
- **Backend**: 70% coverage (configured in pytest)

Coverage reports are uploaded to Codecov for tracking.

## Test Data

### Fixtures

Test fixtures are defined in `tests/setup/fixtures.ts` and match real API response structures. Always use fixtures instead of inline test data to ensure tests catch API contract changes.

### API Mocking

All API calls are mocked using MSW handlers in `tests/setup/mocks.ts`. This ensures:
- Tests run in isolation without backend dependency
- Consistent responses across test runs
- Fast test execution

## Debugging Tests

### Vitest (Unit Tests)

```bash
# Run with debug output
npm run test -- --debug

# Run specific test in watch mode
npm run test -- --watch tests/basic.test.ts

# Show verbose output
npm run test -- --reporter=verbose
```

### Playwright (E2E Tests)

```bash
# Run with UI inspector
npm run test:e2e:ui

# Run in debug mode (opens DevTools)
npm run test:e2e:debug

# Run headed (show browser)
npx playwright test --headed

# Run with trace
npx playwright test --trace on
```

### pytest (Backend Tests)

```bash
# Run with debug output
pytest tests/ -v -s

# Run with pdb debugger
pytest tests/ --pdb

# Run specific test with output
pytest tests/test_example.py::test_function -v -s
```

## Common Issues

### Vitest Issues

**Issue**: Module not found errors
**Solution**: Check vitest.config.ts path aliases and ensure they match tsconfig.json

**Issue**: Tests timing out
**Solution**: Increase timeout in vitest.config.ts: `testTimeout: 30000`

### Playwright Issues

**Issue**: Browser not installed
**Solution**: Run `npx playwright install chromium`

**Issue**: Tests fail against unexpected UI (e.g. old headings) while local source looks correct
**Solution**: Something else is already listening on `:3000` (often the Docker frontend). Playwright's `reuseExistingServer` will hit that stack instead of your working tree. Re-run with `PLAYWRIGHT_PORT=3001 npm run test:e2e`.

**Issue**: Tests failing in CI but passing locally
**Solution**: Check for timing issues - use `await expect().toBeVisible()` instead of `expect().toBeVisible()`

### pytest Issues

**Issue**: Import errors
**Solution**: Ensure `PYTHONPATH=.` is set when running tests

**Issue**: Async tests failing
**Solution**: Use `pytest-asyncio` and mark async tests with `@pytest.mark.asyncio`

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Descriptive Names**: Use clear test names that describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and assertion phases
4. **Mock External Dependencies**: Use MSW to mock API calls
5. **Test Edge Cases**: Include tests for empty states, errors, and edge cases
6. **Keep Tests Fast**: Unit tests should run in milliseconds, E2E tests in seconds
7. **Use Fixtures**: Reuse test data fixtures for consistency
8. **Clean Up**: Ensure tests clean up after themselves (afterEach hooks)

## Testing Checklist

Before committing code:

- [ ] All unit tests pass locally
- [ ] All E2E tests pass locally
- [ ] Type check passes (`npm run type-check`)
- [ ] Linting passes (`npm run lint`)
- [ ] Coverage thresholds met (80% frontend, 70% backend)
- [ ] No console errors or warnings in tests
- [ ] Tests are isolated (can run in any order)
- [ ] Edge cases are covered
- [ ] Error states are tested

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [React Testing Library](https://testing-library.com/react)
- [MSW Documentation](https://mswjs.io/)
- [pytest Documentation](https://docs.pytest.org/)
