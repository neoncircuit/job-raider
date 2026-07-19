import { HelpCircle, AlertTriangle, Lightbulb } from "lucide-react";
import type { PrepSheetResponse } from "@/lib/api/coverLetter";

/**
 * Render an interview prep sheet (likely questions, gaps to address, talking
 * points). Shared by the Cover Letter page and the tracker's interview-prep
 * dialog so both surfaces present prep the same way.
 */
export function PrepSheetDisplay({ prep }: { prep: PrepSheetResponse }) {
  return (
    <div className="space-y-4 text-sm">
      {prep.likely_questions.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-medium flex items-center gap-2">
            <HelpCircle className="h-3.5 w-3.5 text-primary" />
            Likely questions
          </p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            {prep.likely_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      )}
      {prep.gaps_to_address.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-medium flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            Gaps to address honestly
          </p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            {prep.gaps_to_address.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
      )}
      {prep.talking_points.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-medium flex items-center gap-2">
            <Lightbulb className="h-3.5 w-3.5 text-indigo-500" />
            Talking points
          </p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            {prep.talking_points.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
