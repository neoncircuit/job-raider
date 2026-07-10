import { request } from "./client";
import type { CoverLetterResponse } from "@/lib/types/api";

export interface ManualCoverLetterRequest {
  title: string;
  company: string;
  description: string;
  location?: string;
}

export interface CoverLetterExportRequest {
  content: string;
  format: "docx" | "pdf";
  company: string;
  title: string;
}

export const coverLetterApi = {
  /**
   * Generate a tailored cover letter from a manually pasted job description.
   */
  generate: (req: ManualCoverLetterRequest, deep = false, review = false) => {
    const params: Record<string, boolean> = {};
    if (deep) params.deep = true;
    if (review) params.review = true;
    return request<CoverLetterResponse>("POST", "/cover-letter/manual", {
      body: req,
      params: Object.keys(params).length > 0 ? params : undefined,
    });
  },

  /**
   * Export an existing cover letter to DOCX or PDF.
   * Returns a raw Response so the caller can stream the file to disk.
   */
  export: (req: CoverLetterExportRequest) =>
    fetch("/api/proxy/cover-letter/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }),
};

/**
 * Trigger a browser download from a fetch Response.
 */
export async function downloadFile(
  res: Response,
  fallbackName: string,
): Promise<void> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json?.detail ?? json?.message ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(`Export failed: ${detail}`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);

  const header = res.headers.get("content-disposition");
  let filename = fallbackName;
  if (header) {
    const match = header.match(/filename="?([^";]+)"?/);
    if (match?.[1]) filename = match[1];
  }

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
