/**
 * MSW handlers of the demo (Step 4).
 *
 * Reads return the demo data. Any other request gets a 501 with a readable
 * message: the API client does not retry a 501, so no page waits. Nothing
 * changes state, because a demo must not pretend that an action took effect.
 */

import { http, HttpResponse } from "msw";

import {
  demoApplications,
  demoHealth,
  demoHistory,
  demoLetter,
  demoMetrics,
  demoModels,
  demoProfile,
  demoResources,
  demoSettings,
  demoShortlist,
} from "./data";

export const NOT_IN_DEMO =
  "This needs the local backend, so it is not in the demo.";
export const ONE_SAMPLE_LETTER =
  "The demo has one sample letter. Open the first job on the Jobs page.";

/**
 * Match a path of the API proxy, on any host and base path.
 *
 * @param path - The backend path.
 * @returns The MSW path pattern.
 */
function api(path: string): string {
  return `*/api/proxy${path}`;
}

/**
 * Answer a request that the demo cannot serve.
 *
 * @param detail - The message for the user.
 * @returns The response.
 */
function notInDemo(detail: string = NOT_IN_DEMO): HttpResponse<{
  detail: string;
}> {
  return HttpResponse.json({ detail }, { status: 501 });
}

export const handlers = [
  http.get(api("/health"), () => HttpResponse.json(demoHealth)),
  http.get(api("/health/resources"), () => HttpResponse.json(demoResources)),
  http.get(api("/metrics/summary"), () => HttpResponse.json(demoMetrics)),
  http.get(api("/pipeline/history"), () => HttpResponse.json(demoHistory)),
  http.get(api("/pipeline/shortlist/latest"), () =>
    HttpResponse.json(demoShortlist),
  ),
  http.get(api("/profile"), () => HttpResponse.json(demoProfile)),
  http.get(api("/settings/"), () => HttpResponse.json(demoSettings)),
  http.get(api("/settings/models"), () => HttpResponse.json(demoModels)),
  http.get(api("/applications/dashboard"), () =>
    HttpResponse.json(demoApplications),
  ),
  http.get(api("/applications/:applicationId"), ({ params }) => {
    const row = demoApplications.applications.find(
      (item) => item.application_id === params.applicationId,
    );
    if (!row) {
      return notInDemo();
    }
    return HttpResponse.json({
      ...row,
      interviews: [],
      timeline_notes: [],
      metadata: {},
    });
  }),
  http.get(api("/jobs/sources"), () =>
    HttpResponse.json({ sources: ["sample"] }),
  ),
  http.get(api("/jobs/:jobId"), ({ params }) => {
    const job = demoShortlist.jobs.find((item) => item.job_id === params.jobId);
    return job ? HttpResponse.json(job) : notInDemo();
  }),
  http.post(api("/jobs/search"), () =>
    HttpResponse.json({
      total: demoShortlist.jobs.length,
      jobs: demoShortlist.jobs,
    }),
  ),
  http.post(api("/jobs/:jobId/cover-letter"), ({ params }) =>
    params.jobId === demoLetter.job_id
      ? HttpResponse.json(demoLetter)
      : notInDemo(ONE_SAMPLE_LETTER),
  ),
  http.post(api("/cover-letter/manual"), () => notInDemo(ONE_SAMPLE_LETTER)),
  http.all(api("/*"), () => notInDemo()),
];
