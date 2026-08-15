import { describe, expect, it } from "vitest";
import {
  formatJobDescription,
  parseJobMarkdown,
} from "@/lib/utils/job-description";

describe("parseJobMarkdown", () => {
  it("parses headings, paragraphs, lists, and keeps inline markers", () => {
    const text = [
      "## Role Summary",
      "",
      "We need **Python** and *Docker*.",
      "",
      "## Requirements",
      "",
      "- Python",
      "- Docker",
    ].join("\n");

    const blocks = parseJobMarkdown(text);
    expect(blocks[0]).toEqual({ type: "heading", text: "Role Summary" });
    expect(blocks[1]).toEqual({
      type: "paragraph",
      text: "We need **Python** and *Docker*.",
    });
    expect(blocks[2]).toEqual({ type: "heading", text: "Requirements" });
    expect(blocks[3]).toEqual({
      type: "list",
      ordered: false,
      items: ["Python", "Docker"],
    });
  });
});

describe("formatJobDescription", () => {
  it("splits MCF-style Role Summary and Requirements into sections", () => {
    const text = [
      "## Role Summary",
      "",
      "We are seeking a Principal AI Engineer.",
      "",
      "## Requirements",
      "",
      "- Python",
      "- Docker",
    ].join("\n");

    const sections = formatJobDescription(text);
    const titles = sections.map((section) => section.title.toLowerCase());
    expect(titles.some((title) => title.includes("role summary"))).toBe(true);
    expect(titles.some((title) => title.includes("requirements"))).toBe(true);
  });
});
