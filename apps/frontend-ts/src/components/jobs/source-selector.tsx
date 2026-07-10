"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";

interface SourceSelectorProps {
  /** Available source options. */
  available: string[];
  /** Currently selected sources. */
  selected: string[];
  /** Called when the selection changes. */
  onChange: (selected: string[]) => void;
}

/**
 * Multi-select dropdown for choosing job sources.
 *
 * Keyboard accessible with Escape to close and focus returned to the trigger.
 */
export function SourceSelector({
  available,
  selected,
  onChange,
}: SourceSelectorProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = "source-selector-panel";

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        open &&
        panelRef.current &&
        !panelRef.current.contains(target) &&
        !triggerRef.current?.contains(target)
      ) {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [open]);

  const toggleSource = (source: string) => {
    const next = selected.includes(source)
      ? selected.filter((s) => s !== source)
      : [...selected, source];
    onChange(next);
  };

  const allSelected =
    available.length > 0 && selected.length === available.length;
  const noneSelected = selected.length === 0;

  return (
    <div className="relative">
      <Button
        ref={triggerRef}
        type="button"
        variant="outline"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "w-40 justify-between text-xs font-normal",
          noneSelected && "border-warning/50 bg-warning/10 text-warning",
        )}
      >
        <span className="truncate">
          {noneSelected ? (
            <span className="flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              No sources
            </span>
          ) : allSelected ? (
            "All sources"
          ) : (
            `${selected.length} selected`
          )}
        </span>
        <ChevronDown className="h-3.5 w-3.5 opacity-70" />
      </Button>

      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="listbox"
          aria-multiselectable="true"
          className="absolute z-50 mt-1 w-56 rounded-md border border-border bg-card p-2 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between border-b border-border pb-2">
            <button
              type="button"
              onClick={() => onChange([...available])}
              className="text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded px-1"
            >
              Select all
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              className="text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded px-1"
            >
              Clear
            </button>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {available.map((source) => {
              const checked = selected.includes(source);
              return (
                <label
                  key={source}
                  role="option"
                  aria-selected={checked}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-muted focus-within:ring-2 focus-within:ring-primary"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSource(source)}
                    className="h-3.5 w-3.5 accent-primary rounded border-border"
                    aria-label={source}
                  />
                  <span className="capitalize text-foreground">{source}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
