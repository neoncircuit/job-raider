"use client";

import { useForm, useWatch } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { DollarSign, Globe, Calendar, Briefcase } from "lucide-react";
import { profileApi } from "@/lib/api/profile";
import type { UserProfile, VisaStatus } from "@/lib/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// ── Component ───────────────────────────────────────────────────────────────────

interface ApplicationSettingsModalProps {
  profile: UserProfile;
  open: boolean;
  onClose: () => void;
}

interface ApplicationSettingsFormValues {
  visa_status?: VisaStatus;
  visa_expiration_date?: string;
  salary_expectation_min?: string | number;
  salary_expectation_max?: string | number;
  salary_currency?: string;
  notice_period_weeks?: string | number;
  willing_to_relocate?: boolean;
  preferred_work_locations?: string;
}

// ── Visa status options ───────────────────────────────────────────────────────────

const VISA_STATUS_OPTIONS: {
  value: VisaStatus;
  label: string;
  description: string;
}[] = [
  {
    value: "citizen",
    label: "Citizen",
    description: "I am a citizen and don't need sponsorship",
  },
  {
    value: "permanent_resident",
    label: "Permanent Resident",
    description: "I have permanent residency / Green Card",
  },
  { value: "h1b", label: "H1B Visa", description: "I have an H1B visa" },
  {
    value: "other_visa",
    label: "Other Work Visa",
    description: "I have another type of work visa",
  },
  {
    value: "need_sponsorship",
    label: "Need Sponsorship",
    description: "I will need visa sponsorship",
  },
  {
    value: "student_visa",
    label: "Student Visa",
    description: "I am on a student visa (F1, etc.)",
  },
  {
    value: "not_specified",
    label: "Prefer not to say",
    description: "I prefer not to disclose this information",
  },
];

export function ApplicationSettingsModal({
  profile,
  open,
  onClose,
}: ApplicationSettingsModalProps) {
  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { isDirty },
  } = useForm({
    defaultValues: {
      visa_status: profile.visa_status ?? undefined,
      visa_expiration_date: profile.visa_expiration_date
        ? profile.visa_expiration_date.split("T")[0]
        : "",
      salary_expectation_min: profile.salary_expectation_min ?? "",
      salary_expectation_max: profile.salary_expectation_max ?? "",
      salary_currency: profile.salary_currency ?? "USD",
      notice_period_weeks: profile.notice_period_weeks ?? "",
      willing_to_relocate: profile.willing_to_relocate ?? false,
      preferred_work_locations:
        profile.preferred_work_locations?.join(", ") ?? "",
    },
  });

  const save = useMutation({
    mutationFn: (values: ApplicationSettingsFormValues) => {
      const updates: Partial<UserProfile> = {
        visa_status: values.visa_status || undefined,
        visa_expiration_date: values.visa_expiration_date || undefined,
        salary_expectation_min: values.salary_expectation_min
          ? Number(values.salary_expectation_min)
          : undefined,
        salary_expectation_max: values.salary_expectation_max
          ? Number(values.salary_expectation_max)
          : undefined,
        salary_currency: values.salary_currency,
        notice_period_weeks: values.notice_period_weeks
          ? Number(values.notice_period_weeks)
          : undefined,
        willing_to_relocate: values.willing_to_relocate,
        preferred_work_locations: values.preferred_work_locations
          ? values.preferred_work_locations
              .split(",")
              .map((s: string) => s.trim())
              .filter(Boolean)
          : undefined,
      };
      return profileApi.update(updates);
    },
    onSuccess: () => {
      toast.success("Application settings saved");
      onClose();
    },
    onError: () => toast.error("Failed to save settings"),
  });

  const selectedVisaStatus = useWatch({ control, name: "visa_status" });
  const willingToRelocate = useWatch({ control, name: "willing_to_relocate" });

  const onSubmit = (values: ApplicationSettingsFormValues) => {
    save.mutate(values);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Application Settings</DialogTitle>
          <DialogDescription>
            These settings help us auto-answer application questions and improve
            your application success rate.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Work Authorization */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-muted-foreground" />
              <Label className="text-base font-semibold">
                Work Authorization
              </Label>
            </div>
            <p className="text-sm text-muted-foreground">
              This helps us answer visa/sponsorship questions correctly.
            </p>

            <div className="space-y-2">
              {VISA_STATUS_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                    selectedVisaStatus === option.value
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted",
                  )}
                >
                  <input
                    type="radio"
                    value={option.value}
                    {...register("visa_status")}
                    className="mt-1 h-4 w-4 accent-primary"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">
                      {option.label}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {option.description}
                    </p>
                  </div>
                </label>
              ))}
            </div>

            {(selectedVisaStatus === "h1b" ||
              selectedVisaStatus === "other_visa") && (
              <div className="space-y-1">
                <Label htmlFor="visa_expiration">Visa Expiration Date</Label>
                <Input
                  id="visa_expiration"
                  type="date"
                  {...register("visa_expiration_date")}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground">
                  When does your visa expire?
                </p>
              </div>
            )}
          </div>

          {/* Salary Expectations */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <Label className="text-base font-semibold">
                Salary Expectations
              </Label>
            </div>
            <p className="text-sm text-muted-foreground">
              Helps us answer salary requirement questions. Leave blank if you
              prefer not to specify.
            </p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label htmlFor="salary_min">Minimum (Annual)</Label>
                <Input
                  id="salary_min"
                  type="number"
                  placeholder="80000"
                  {...register("salary_expectation_min")}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="salary_max">Maximum (Annual)</Label>
                <Input
                  id="salary_max"
                  type="number"
                  placeholder="150000"
                  {...register("salary_expectation_max")}
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="salary_currency">Currency</Label>
              <select
                id="salary_currency"
                {...register("salary_currency")}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
              >
                <option value="USD">USD - US Dollar</option>
                <option value="EUR">EUR - Euro</option>
                <option value="GBP">GBP - British Pound</option>
                <option value="SGD">SGD - Singapore Dollar</option>
                <option value="CAD">CAD - Canadian Dollar</option>
                <option value="AUD">AUD - Australian Dollar</option>
                <option value="INR">INR - Indian Rupee</option>
              </select>
            </div>
          </div>

          {/* Notice Period */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <Label className="text-base font-semibold">Notice Period</Label>
            </div>
            <p className="text-sm text-muted-foreground">
              How many weeks notice do you need to give your current employer?
            </p>

            <div className="space-y-1">
              <Input
                type="number"
                min={0}
                max={52}
                placeholder="2"
                {...register("notice_period_weeks")}
              />
              <p className="text-xs text-muted-foreground">
                Weeks (0 means immediately available)
              </p>
            </div>
          </div>

          {/* Relocation */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <Label className="text-base font-semibold">
                Location Preferences
              </Label>
            </div>

            <div className="flex items-center gap-3">
              <Switch
                id="relocate"
                checked={willingToRelocate}
                onCheckedChange={(v) => setValue("willing_to_relocate", v)}
              />
              <Label htmlFor="relocate" className="cursor-pointer">
                I am willing to relocate for the right opportunity
              </Label>
            </div>

            <div className="space-y-1">
              <Label htmlFor="preferred_locations">
                Preferred Work Locations
              </Label>
              <Input
                id="preferred_locations"
                placeholder="Singapore, Remote..."
                {...register("preferred_work_locations")}
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of locations you&apos;d consider (beyond
                your target job locations)
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t">
            <Button
              type="submit"
              disabled={save.isPending || !isDirty}
              className="flex-1"
            >
              {save.isPending ? "Saving..." : "Save Settings"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="w-32"
            >
              Cancel
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
