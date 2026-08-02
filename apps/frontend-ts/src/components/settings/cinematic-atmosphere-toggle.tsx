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
  COLOR_SCHEMES,
  isColorScheme,
  useColorSchemePreference,
  type ColorScheme,
} from "@/lib/hooks/use-color-scheme";

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
        <Label htmlFor="color-scheme">Color scheme</Label>
        <Select
          value={scheme}
          onValueChange={(value) => {
            if (isColorScheme(value)) {
              setScheme(value as ColorScheme);
            }
          }}
        >
          <SelectTrigger id="color-scheme" className="w-full">
            <SelectValue placeholder="Choose a scheme" />
          </SelectTrigger>
          <SelectContent>
            {COLOR_SCHEMES.map((id) => (
              <SelectItem key={id} value={id}>
                {COLOR_SCHEME_LABELS[id]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Neon and Retrowave remap accent colors on top of light or dark mode.
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
