"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { JobClassification } from "@/lib/types/api";
import {
  Building2,
  Users,
  Gauge,
  Target,
  AlertTriangle,
  Tag,
  Briefcase,
  TrendingUp,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface JobClassificationDisplayProps {
  classification: JobClassification;
}

export function JobClassificationDisplay({
  classification,
}: JobClassificationDisplayProps) {
  if (!classification) {
    return null;
  }

  const hasWarnings =
    classification.red_flags && classification.red_flags.length > 0;

  return (
    <div className="space-y-3">
      {/* Primary Classifications */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Building2 className="h-4 w-4 text-indigo-500" />
              Industry
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-gray-900">
              {classification.industry}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Briefcase className="h-4 w-4 text-indigo-500" />
              Role Category
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-gray-900">
              {classification.role_category}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Users className="h-4 w-4 text-indigo-500" />
              Company Size
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-gray-900">
              {classification.company_size}
            </p>
            {classification.company_stage && (
              <p className="mt-1 text-xs text-gray-500">
                {classification.company_stage}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Gauge className="h-4 w-4 text-indigo-500" />
              Work Pace
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                classification.work_pace === "Fast-Paced" &&
                  "border-orange-300 bg-orange-50 text-orange-800",
                classification.work_pace === "High Pressure" &&
                  "border-red-300 bg-red-50 text-red-800",
                classification.work_pace === "Relaxed" &&
                  "border-green-300 bg-green-50 text-green-800",
                classification.work_pace === "Steady" &&
                  "border-blue-300 bg-blue-50 text-blue-800",
              )}
            >
              {classification.work_pace}
            </Badge>
            <p className="mt-1 text-xs text-gray-500">
              {classification.team_structure}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Role Scope */}
      {(classification.management_level || classification.impact_scope) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Target className="h-4 w-4 text-indigo-500" />
              Role Scope
            </CardTitle>
          </CardHeader>
          <CardContent className="flex gap-4">
            {classification.management_level && (
              <div>
                <p className="text-xs text-gray-500">Management Level</p>
                <p className="text-sm font-medium text-gray-900 capitalize">
                  {classification.management_level.replace(/_/g, " ")}
                </p>
              </div>
            )}
            {classification.impact_scope && (
              <div>
                <p className="text-xs text-gray-500">Impact Scope</p>
                <p className="text-sm font-medium text-gray-900 capitalize">
                  {classification.impact_scope}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Skills Breakdown */}
      {(classification.technical_skills?.length > 0 ||
        classification.soft_skills?.length > 0 ||
        classification.domain_skills?.length > 0) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              Skills Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {classification.technical_skills?.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-gray-700">
                  Technical Skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {classification.technical_skills.map((skill, idx) => (
                    <Badge
                      key={idx}
                      variant={skill.is_required ? "default" : "outline"}
                      className="text-xs"
                    >
                      {skill.name}
                      <span className="ml-1 opacity-70">
                        ({skill.proficiency})
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {classification.soft_skills?.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-gray-700">
                  Soft Skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {classification.soft_skills.map((skill, idx) => (
                    <Badge
                      key={idx}
                      variant={skill.is_required ? "default" : "outline"}
                      className="bg-pink-100 text-pink-800 text-xs"
                    >
                      {skill.name}
                      <span className="ml-1 opacity-70">
                        ({skill.proficiency})
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {classification.domain_skills?.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-gray-700">
                  Domain Knowledge
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {classification.domain_skills.map((skill, idx) => (
                    <Badge
                      key={idx}
                      variant={skill.is_required ? "default" : "outline"}
                      className="bg-teal-100 text-teal-800 text-xs"
                    >
                      {skill.name}
                      <span className="ml-1 opacity-70">
                        ({skill.proficiency})
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Experience Validation */}
      {classification.actual_experience_years && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-indigo-500" />
              Experience Validation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700">
              Estimated experience required:{" "}
              <span className="font-semibold text-gray-900">
                {classification.actual_experience_years[0]} -{" "}
                {classification.actual_experience_years[1]} years
              </span>
            </p>
            {classification.experience_level_confidence > 0 && (
              <p className="mt-1 text-xs text-gray-500">
                Confidence:{" "}
                {Math.round(classification.experience_level_confidence * 100)}%
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tags */}
      {classification.tags?.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Tag className="h-4 w-4 text-indigo-500" />
              Tags
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1.5">
              {classification.tags.map((tag, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Red Flags */}
      {hasWarnings && (
        <Card className="border-amber-200 bg-amber-50">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-amber-900">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Considerations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {classification.red_flags.map((flag, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 text-xs text-amber-800"
                >
                  <span className="mt-0.5">•</span>
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Classification Confidence */}
      <p className="text-center text-xs text-gray-400">
        Classification confidence:{" "}
        {Math.round(classification.classification_confidence * 100)}%
      </p>
    </div>
  );
}
