import { describe, expect, it } from "vitest";
import {
  SETTINGS_DEFAULT_MODEL_VALUE,
  buildModelSelectOptions,
  resolveWriterModelOverride,
} from "@/lib/model-select";

describe("buildModelSelectOptions", () => {
  it("allowlists Anthropic catalog and greys Ollama installed + Gemini", () => {
    const { provider, baselineModel, options } = buildModelSelectOptions(
      "cover_letter_writing",
      {
        cover_letter_writing: {
          primary_provider: "anthropic",
          primary_model: "claude-sonnet-4-6",
        },
      },
      {
        anthropic: ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        gemini: ["gemini-2.5-flash"],
        ollama_installed: ["qwen2.5:7b"],
      },
    );

    expect(provider).toBe("anthropic");
    expect(baselineModel).toBe("claude-sonnet-4-6");

    const byValue = Object.fromEntries(options.map((o) => [o.value, o]));
    expect(byValue[SETTINGS_DEFAULT_MODEL_VALUE]?.disabled).toBe(false);
    expect(byValue["claude-haiku-4-5-20251001"]?.disabled).toBe(false);
    expect(byValue["qwen2.5:7b"]?.disabled).toBe(true);
    expect(byValue["gemini-2.5-flash"]?.disabled).toBe(true);
  });

  it("uses installed Ollama tags only when provider is ollama", () => {
    const { options } = buildModelSelectOptions(
      "cover_letter_writing",
      {
        cover_letter_writing: {
          primary_provider: "ollama",
          primary_model: "qwen2.5:7b",
        },
      },
      {
        ollama: ["qwen2.5:7b", "catalog-only:1b"],
        ollama_installed: ["qwen2.5:7b"],
        anthropic: ["claude-sonnet-4-6"],
      },
    );

    const selectable = options.filter((o) => !o.disabled).map((o) => o.value);
    expect(selectable).toContain("qwen2.5:7b");
    expect(selectable).not.toContain("catalog-only:1b");
    expect(options.some((o) => o.value === "claude-sonnet-4-6" && o.disabled)).toBe(
      true,
    );
  });
});

describe("resolveWriterModelOverride", () => {
  it("returns undefined for Settings default sentinel", () => {
    expect(
      resolveWriterModelOverride(SETTINGS_DEFAULT_MODEL_VALUE, "qwen2.5:7b"),
    ).toBeUndefined();
  });

  it("returns the selected model when overriding", () => {
    expect(resolveWriterModelOverride("qwen2.5:3b", "qwen2.5:7b")).toBe(
      "qwen2.5:3b",
    );
  });
});
