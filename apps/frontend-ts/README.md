# Job Raider - Next.js Dashboard

This is the active Job Raider frontend: a Next.js + Tailwind CSS dashboard for running and monitoring the automated job-application pipeline.

## Tech Stack

- Next.js 16 with App Router
- React 19 + TypeScript 5
- Tailwind CSS 4 + shadcn/ui
- TanStack Query, React Hook Form, Zod, Recharts
- Vitest for unit tests
- Playwright for E2E tests

## Getting Started

Install dependencies (from `apps/frontend-ts`):

```bash
npm ci
```

Run the development server:

```bash
npm run dev
```

The dashboard is served at [http://localhost:3000](http://localhost:3000). It expects the backend API at [http://localhost:8000](http://localhost:8000); start it first with `make dev-api` from the project root.

## Available Commands

```bash
npm run dev              # Start the development server
npm run build            # Build for production
npm run start            # Start the production server
npm run lint             # Run ESLint
npm run type-check       # Run TypeScript type check
npm run format           # Format with Prettier
npm run format:check     # Check Prettier formatting
npm run test             # Run unit tests in watch mode
npm run test -- --run    # Run unit tests once
npm run test:coverage    # Run unit tests with coverage
npm run test:e2e         # Run Playwright E2E tests
```

## Project Structure

```
apps/frontend-ts/
├── src/
│   ├── app/          # Next.js App Router pages
│   ├── components/   # Shared UI components and layouts
│   ├── hooks/        # Custom React hooks
│   ├── lib/          # API client, utilities, types
│   └── styles/       # Global styles
├── tests/            # Vitest unit tests and Playwright E2E specs
├── public/           # Static assets
└── package.json      # Dependencies and scripts
```

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [Project Root README](../../README.md)
