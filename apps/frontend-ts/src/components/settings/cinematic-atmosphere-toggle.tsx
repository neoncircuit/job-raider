"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCinematicPreference } from "@/lib/hooks/use-cinematic";
import {
  COLOR_SCHEME_LABELS,
  COLOR_SCHEME_SWATCHES,
  COLOR_SCHEMES,
  useColorSchemePreference,
  type ColorScheme,
} from "@/lib/hooks/use-color-scheme";
import { useDateTimePrefs } from "@/lib/hooks/use-datetime-prefs";
import {
  DATE_TIME_FORMAT_OPTIONS,
  MANUAL_TIME_ZONES,
  TIME_ZONE_MODE_OPTIONS,
  formatDateTimeWithPrefs,
  type DateTimeFormatId,
  type TimeZoneMode,
} from "@/lib/datetime-prefs";
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
 * Local Appearance preferences: color scheme, cinematic atmosphere, datetime.
 *
 * Preferences stay in localStorage and do not sync to the backend.
 */
export function CinematicAtmosphereToggle() {
  const [enabled, setEnabled] = useCinematicPreference();
  const [scheme, setScheme] = useColorSchemePreference();
  const [dateTimePrefs, setDateTimePrefs] = useDateTimePrefs();
  const preview = formatDateTimeWithPrefs(
    new Date().toISOString(),
    dateTimePrefs,
    "Singapore, Singapore",
  );

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

      <div className="space-y-3 border-t border-border pt-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Date &amp; time</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Applies to dates and timestamps across the app (Profile, Pipeline,
            Dashboard, Jobs, Metrics, Career Coach, Applications, and more).
            Default is this device’s system locale and time zone.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="datetime-format">Format</Label>
          <Select
            value={dateTimePrefs.format}
            onValueChange={(value) => {
              if (!value) return;
              setDateTimePrefs({
                ...dateTimePrefs,
                format: value as DateTimeFormatId,
              });
            }}
          >
            <SelectTrigger id="datetime-format" className="w-full">
              <SelectValue placeholder="Format" />
            </SelectTrigger>
            <SelectContent>
              {DATE_TIME_FORMAT_OPTIONS.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label} — {option.exampleHint}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="datetime-timezone-mode">Time zone</Label>
          <Select
            value={dateTimePrefs.timeZoneMode}
            onValueChange={(value) => {
              if (!value) return;
              setDateTimePrefs({
                ...dateTimePrefs,
                timeZoneMode: value as TimeZoneMode,
              });
            }}
          >
            <SelectTrigger id="datetime-timezone-mode" className="w-full">
              <SelectValue placeholder="Time zone" />
            </SelectTrigger>
            <SelectContent>
              {TIME_ZONE_MODE_OPTIONS.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {
              TIME_ZONE_MODE_OPTIONS.find(
                (option) => option.id === dateTimePrefs.timeZoneMode,
              )?.description
            }
          </p>
        </div>

        {dateTimePrefs.timeZoneMode === "manual" && (
          <div className="space-y-2">
            <Label htmlFor="datetime-manual-timezone">Manual time zone</Label>
            <Select
              value={dateTimePrefs.manualTimeZone}
              onValueChange={(value) => {
                if (!value) return;
                setDateTimePrefs({
                  ...dateTimePrefs,
                  manualTimeZone: value,
                });
              }}
            >
              <SelectTrigger id="datetime-manual-timezone" className="w-full">
                <SelectValue placeholder="IANA time zone" />
              </SelectTrigger>
              <SelectContent>
                {MANUAL_TIME_ZONES.map((zone) => (
                  <SelectItem key={zone.id} value={zone.id}>
                    {zone.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {preview && (
          <p className="text-xs text-muted-foreground">
            Preview: <span className="text-foreground">{preview}</span>
            {dateTimePrefs.timeZoneMode === "profile_location"
              ? " (sample location: Singapore)"
              : null}
          </p>
        )}
      </div>
    </div>
  );
}
