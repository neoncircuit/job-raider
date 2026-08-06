"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useCinematicPreference } from "@/lib/hooks/use-cinematic";
import {
  COLOR_SCHEME_LABELS,
  COLOR_SCHEME_SWATCHES,
  COLOR_SCHEMES,
  useColorSchemePreference,
  type ColorScheme,
} from "@/lib/hooks/use-color-scheme";
import { cn } from "@/lib/utils/cn";

/**
 * Odysseus-inspired preset card: three overlapping color dots + name.
 *
 * @param scheme - Scheme id for this card.
 * @param selected - Whether this card is the active preference.
 * @param onSelect - Called when the user activates the card.
 */
function SchemePresetCard({
  scheme,
  selected,
  onSelect,
}: {
  scheme: ColorScheme;
  selected: boolean;
  onSelect: (scheme: ColorScheme) => void;
}) {
  const [bg, primary, accent] = COLOR_SCHEME_SWATCHES[scheme];
  const label = COLOR_SCHEME_LABELS[scheme];

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={label}
      onClick={() => onSelect(scheme)}
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border bg-card px-3 py-3 text-center transition-colors",
        "hover:border-primary/50 hover:bg-muted/40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-primary ring-2 ring-primary/30" : "border-border",
      )}
    >
      <span
        className="relative flex h-8 w-14 items-center justify-center"
        aria-hidden
      >
        <span
          className="absolute left-1 size-6 rounded-full border border-background/80"
          style={{ backgroundColor: bg }}
        />
        <span
          className="absolute left-4 size-6 rounded-full border border-background/80"
          style={{ backgroundColor: primary }}
        />
        <span
          className="absolute left-7 size-6 rounded-full border border-background/80"
          style={{ backgroundColor: accent }}
        />
      </span>
      <span className="text-xs font-medium text-foreground">
        {label}
        {scheme === "default" ? (
          <span className="block text-[10px] font-normal text-muted-foreground">
            default
          </span>
        ) : null}
      </span>
    </button>
  );
}

/**
 * Local Appearance preferences: color scheme and cinematic atmosphere.
 *
 * Preferences stay in localStorage and do not sync to the backend.
 */
export function CinematicAtmosphereToggle() {
  const [enabled, setEnabled] = useCinematicPreference();
  const [scheme, setScheme] = useColorSchemePreference();

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Appearance</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Optional local UI preferences. Do not sync to the backend.
        </p>
      </div>

      <div className="space-y-2">
        <Label id="color-scheme-label">Color scheme</Label>
        <div
          role="radiogroup"
          aria-labelledby="color-scheme-label"
          className="grid grid-cols-3 gap-2 sm:grid-cols-4"
        >
          {COLOR_SCHEMES.map((id) => (
            <SchemePresetCard
              key={id}
              scheme={id}
              selected={scheme === id}
              onSelect={setScheme}
            />
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Presets remap accents on top of light or dark mode. Customize panel
          comes later.
        </p>
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="space-y-0.5">
          <Label htmlFor="cinematic-atmosphere">Cinematic atmosphere</Label>
          <p className="text-xs text-muted-foreground">
            Soft depth and motion on Dashboard and Pipeline. Off by default.
          </p>
        </div>
        <Switch
          id="cinematic-atmosphere"
          checked={enabled}
          onCheckedChange={setEnabled}
        />
      </div>
    </div>
  );
}
