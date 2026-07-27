"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useCinematicPreference } from "@/lib/hooks/use-cinematic";

/**
 * Local Appearance preference: optional cinematic atmosphere (default off).
 */
export function CinematicAtmosphereToggle() {
  const [enabled, setEnabled] = useCinematicPreference();

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Appearance</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Optional local UI preference. Does not sync to the backend.
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
