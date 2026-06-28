"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Plus, Search, Trash2 } from "lucide-react";
import { profileApi } from "@/lib/api/profile";
import type {
  LinkedInProfileAnalysis,
  LinkedInProfileInput,
  LinkedInExperienceEntry,
  LinkedInEducationEntry,
  LinkedInPeopleSearchInput,
  LinkedInPeopleSearchResult,
} from "@/lib/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils/cn";

/**
 * Render a circular score indicator for the LinkedIn profile analysis.
 *
 * @param props - Component props.
 * @param props.score - Numeric score from 0-100.
 * @returns A score ring element.
 */
function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : "text-red-500";
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={cn("text-5xl font-bold", color)}>{score}</div>
      <div className="text-xs text-gray-400">/ 100</div>
    </div>
  );
}

/**
 * Render a priority badge for an inbound attraction insight.
 *
 * @param props - Component props.
 * @param props.priority - Priority level (critical, high, medium, low).
 * @returns A styled badge element.
 */
function PriorityBadge({ priority }: { priority: "critical" | "high" | "medium" | "low" }) {
  const variants: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border-red-200",
    high: "bg-orange-100 text-orange-700 border-orange-200",
    medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
    low: "bg-blue-100 text-blue-700 border-blue-200",
  };
  return (
    <Badge variant="outline" className={cn("text-[10px] uppercase tracking-wide", variants[priority])}>
      {priority}
    </Badge>
  );
}

/**
 * Display a completed LinkedIn profile analysis with export support.
 *
 * @param props - Component props.
 * @param props.analysis - The analysis result to display.
 * @returns The analysis display element.
 */
function AnalysisDisplay({ analysis }: { analysis: LinkedInProfileAnalysis }) {
  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "linkedin-analysis.json";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
  };

  return (
    <div className="space-y-4">
      {/* Score header */}
      <Card>
        <CardContent className="flex items-center gap-8 pt-6 pb-5">
          <ScoreRing score={analysis.overall_score} />
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-700">LinkedIn Profile Analysis</p>
            <p className="mt-1 text-sm text-gray-600 leading-relaxed">{analysis.summary}</p>
            {analysis.competitive_edge && (
              <p className="mt-2 text-sm text-gray-700">
                <span className="font-semibold">Competitive edge:</span> {analysis.competitive_edge}
              </p>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={downloadJson} className="shrink-0">
            <Download className="mr-1.5 h-3.5 w-3.5" />
            Export
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Section scores */}
        {(analysis.section_scores?.length ?? 0) > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Section Scores</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {(analysis.section_scores ?? []).map((s, i) => (
                  <div key={i} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-700">{s.section_name}</span>
                      <span
                        className={cn(
                          "text-sm font-bold",
                          s.score >= 80 ? "text-green-600" : s.score >= 60 ? "text-yellow-600" : "text-red-600"
                        )}
                      >
                        {s.score}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-gray-400">Weight: {s.weight}</div>
                    <p className="mt-1.5 text-xs text-gray-600 leading-relaxed">{s.feedback}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Insights */}
        {(analysis.insights?.length ?? 0) > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Prioritized Insights</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {(analysis.insights ?? []).map((insight, i) => (
                  <div key={i} className="rounded-lg border p-3">
                    <div className="flex items-center gap-2">
                      <PriorityBadge priority={insight.priority} />
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        {insight.category}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm text-gray-700">
                      <span className="font-semibold">Observation:</span> {insight.observation}
                    </p>
                    <p className="mt-1 text-sm text-gray-600">
                      <span className="font-semibold">Recommendation:</span> {insight.recommendation}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Keyword recommendations */}
        {(analysis.keyword_recommendations?.length ?? 0) > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-blue-700">Keyword Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {(analysis.keyword_recommendations ?? []).map((k) => (
                  <Badge key={k} variant="outline" className="border-blue-200 text-blue-600 text-xs">
                    {k}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Generated headline options */}
        {(analysis.generated_headline_options?.length ?? 0) > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-purple-700">Headline Options</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5">
                {(analysis.generated_headline_options ?? []).map((h, i) => (
                  <li key={i} className="text-sm text-gray-700">
                    {i + 1}. {h}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Summary rewrite suggestions */}
        {(analysis.summary_rewrite_suggestions?.length ?? 0) > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Summary Rewrite Suggestions</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2">
                {(analysis.summary_rewrite_suggestions ?? []).map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="shrink-0 font-semibold text-blue-600">{i + 1}.</span>
                    {s}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        )}

        {/* Action plan */}
        {(analysis.action_plan?.length ?? 0) > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Action Plan</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2">
                {(analysis.action_plan ?? []).map((step, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="shrink-0 font-semibold text-green-600">{i + 1}.</span>
                    {step}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ── Input form ────────────────────────────────────────────────────────────────

const EMPTY_EXPERIENCE: LinkedInExperienceEntry = {
  title: "",
  company: "",
  dates: "",
  description: "",
};

const EMPTY_EDUCATION: LinkedInEducationEntry = {
  school: "",
  degree: "",
  field: "",
  dates: "",
};

/**
 * Display LinkedIn people search results and allow selecting a profile.
 *
 * @param props - Component props.
 * @param props.results - Search results to display.
 * @param props.onSelect - Callback invoked with the selected profile URL.
 * @returns The search results element.
 */
function SearchResults({
  results,
  onSelect,
}: {
  results: LinkedInPeopleSearchResult[];
  onSelect: (profileUrl: string) => void;
}) {
  if (results.length === 0) {
    return (
      <p className="text-sm text-gray-500">No results found. Try adjusting your search terms.</p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-gray-700">Search results</p>
      {results.map((result, index) => (
        <Card key={index} className="hover:border-primary/50 transition-colors">
          <CardContent className="p-3 space-y-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-gray-900 truncate">{result.name}</p>
                <p className="text-xs text-gray-600 line-clamp-2">{result.headline}</p>
                {result.location && <p className="text-xs text-gray-400">{result.location}</p>}
              </div>
              <Button size="sm" variant="outline" onClick={() => onSelect(result.profile_url)}>
                Analyze
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/**
 * Form for submitting a LinkedIn profile for analysis.
 *
 * @param props - Component props.
 * @param props.onResult - Callback invoked with the analysis result on success.
 * @returns The analysis form element.
 */
function AnalysisForm({ onResult }: { onResult: (r: LinkedInProfileAnalysis) => void }) {
  const [activeTab, setActiveTab] = useState("url");
  const [profileUrl, setProfileUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [experienceEntries, setExperienceEntries] = useState<LinkedInExperienceEntry[]>([
    { ...EMPTY_EXPERIENCE },
  ]);
  const [educationEntries, setEducationEntries] = useState<LinkedInEducationEntry[]>([
    { ...EMPTY_EDUCATION },
  ]);
  const [skills, setSkills] = useState("");
  const [industry, setIndustry] = useState("");
  const [careerGoals, setCareerGoals] = useState("");
  const [targetRoles, setTargetRoles] = useState("");

  // Search tab state
  const [searchInput, setSearchInput] = useState<LinkedInPeopleSearchInput>({
    keywords: "",
    name: "",
    title: "",
    company: "",
    location: "",
  });
  const [searchResults, setSearchResults] = useState<LinkedInPeopleSearchResult[]>([]);

  const updateExperience = (index: number, field: keyof LinkedInExperienceEntry, value: string) => {
    setExperienceEntries((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, [field]: value } : entry))
    );
  };

  const addExperience = () => {
    setExperienceEntries((prev) => [...prev, { ...EMPTY_EXPERIENCE }]);
  };

  const removeExperience = (index: number) => {
    setExperienceEntries((prev) => prev.filter((_, i) => i !== index));
  };

  const updateEducation = (index: number, field: keyof LinkedInEducationEntry, value: string) => {
    setEducationEntries((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, [field]: value } : entry))
    );
  };

  const addEducation = () => {
    setEducationEntries((prev) => [...prev, { ...EMPTY_EDUCATION }]);
  };

  const removeEducation = (index: number) => {
    setEducationEntries((prev) => prev.filter((_, i) => i !== index));
  };

  const analyze = useMutation({
    mutationFn: () => {
      let input: LinkedInProfileInput;
      if (activeTab === "url") {
        if (!profileUrl.trim()) throw new Error("Please enter a LinkedIn profile URL");
        input = { profile_url: profileUrl.trim() };
      } else if (activeTab === "paste") {
        if (!rawText.trim()) throw new Error("Please paste your profile text");
        input = { raw_text: rawText.trim() };
      } else {
        const experience = experienceEntries.filter(
          (entry) => entry.title?.trim() || entry.company?.trim() || entry.description?.trim()
        );
        const education = educationEntries.filter(
          (entry) => entry.school?.trim() || entry.degree?.trim() || entry.field?.trim()
        );

        input = {
          headline: headline.trim() || null,
          summary: summary.trim() || null,
          experience_entries: experience,
          education_entries: education,
          skills: skills.trim() ? skills.split(",").map((s) => s.trim()).filter(Boolean) : [],
          industry: industry.trim() || null,
          career_goals: careerGoals.trim() || null,
          target_roles: targetRoles.trim() ? targetRoles.split(",").map((s) => s.trim()).filter(Boolean) : [],
        };
      }
      return profileApi.analyzeLinkedIn(input);
    },
    onSuccess: onResult,
    onError: (err: Error) => toast.error(err.message || "Analysis failed. Check that the backend is running."),
  });

  const search = useMutation({
    mutationFn: () => {
      const hasSearchInput = Object.values(searchInput).some((v) => typeof v === "string" && v.trim());
      if (!hasSearchInput) throw new Error("Please enter at least one search term");
      const input: LinkedInPeopleSearchInput = {
        keywords: searchInput.keywords?.trim() || null,
        name: searchInput.name?.trim() || null,
        title: searchInput.title?.trim() || null,
        company: searchInput.company?.trim() || null,
        location: searchInput.location?.trim() || null,
      };
      return profileApi.searchLinkedInPeople(input);
    },
    onSuccess: (data) => {
      setSearchResults(data.results);
      if (data.results.length === 0) {
        toast.info("No profiles found. Try broadening your search.");
      }
    },
    onError: (err: Error) => toast.error(err.message || "Search failed. Check that the backend is running."),
  });

  const hasManualInput = Boolean(
    headline.trim() ||
      summary.trim() ||
      industry.trim() ||
      careerGoals.trim() ||
      skills.trim() ||
      targetRoles.trim() ||
      experienceEntries.some(
        (entry) => entry.title?.trim() || entry.company?.trim() || entry.description?.trim()
      ) ||
      educationEntries.some(
        (entry) => entry.school?.trim() || entry.degree?.trim() || entry.field?.trim()
      )
  );

  const canSubmit =
    activeTab === "url"
      ? profileUrl.trim().length > 0
      : activeTab === "paste"
        ? rawText.trim().length > 0
        : hasManualInput;

  const handleSelectSearchResult = (url: string) => {
    setProfileUrl(url);
    setActiveTab("url");
    setSearchResults([]);
    toast.success("Profile URL selected. Click Analyze to continue.");
  };

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="url">LinkedIn URL</TabsTrigger>
          <TabsTrigger value="search">Search Profiles</TabsTrigger>
          <TabsTrigger value="paste">Paste Profile Text</TabsTrigger>
          <TabsTrigger value="manual">Fill Sections Manually</TabsTrigger>
        </TabsList>

        <TabsContent value="url" className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="profile-url">LinkedIn profile URL</Label>
            <Input
              id="profile-url"
              placeholder="https://www.linkedin.com/in/username"
              value={profileUrl}
              onChange={(e) => setProfileUrl(e.target.value)}
            />
            <p className="text-xs text-gray-500">
              Requires LinkedIn credentials configured on the backend. If unavailable, the URL itself
              will be used as context.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="search" className="space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="search-keywords">Keywords</Label>
              <Input
                id="search-keywords"
                placeholder="e.g., React, TypeScript"
                value={searchInput.keywords ?? ""}
                onChange={(e) => setSearchInput((prev) => ({ ...prev, keywords: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="search-name">Name</Label>
              <Input
                id="search-name"
                placeholder="Person name"
                value={searchInput.name ?? ""}
                onChange={(e) => setSearchInput((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="search-title">Title</Label>
              <Input
                id="search-title"
                placeholder="Job title"
                value={searchInput.title ?? ""}
                onChange={(e) => setSearchInput((prev) => ({ ...prev, title: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="search-company">Company</Label>
              <Input
                id="search-company"
                placeholder="Company name"
                value={searchInput.company ?? ""}
                onChange={(e) => setSearchInput((prev) => ({ ...prev, company: e.target.value }))}
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor="search-location">Location</Label>
              <Input
                id="search-location"
                placeholder="City, country, or region"
                value={searchInput.location ?? ""}
                onChange={(e) => setSearchInput((prev) => ({ ...prev, location: e.target.value }))}
              />
            </div>
          </div>

          <Button
            onClick={() => search.mutate()}
            disabled={search.isPending}
            variant="secondary"
            className="w-full"
          >
            <Search className="mr-1.5 h-4 w-4" />
            {search.isPending ? "Searching..." : "Search LinkedIn Profiles"}
          </Button>

          <SearchResults results={searchResults} onSelect={handleSelectSearchResult} />
        </TabsContent>

        <TabsContent value="paste" className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="raw-text">Paste your LinkedIn profile text</Label>
            <Textarea
              id="raw-text"
              rows={12}
              placeholder="Copy and paste your LinkedIn profile content here (headline, summary, experience, education, skills)..."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>
        </TabsContent>

        <TabsContent value="manual" className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="headline">Headline</Label>
              <Input
                id="headline"
                placeholder="e.g., Senior Software Engineer at..."
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="industry">Industry</Label>
              <Input
                id="industry"
                placeholder="e.g., Information Technology"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="summary">Summary / About</Label>
            <Textarea
              id="summary"
              rows={4}
              placeholder="Your LinkedIn summary..."
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </div>

          {/* Experience entries */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Experience</Label>
              <Button type="button" variant="outline" size="sm" onClick={addExperience}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                Add experience
              </Button>
            </div>
            {experienceEntries.map((entry, index) => (
              <div key={index} className="rounded-lg border p-3 space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input
                    placeholder="Title"
                    value={entry.title}
                    onChange={(e) => updateExperience(index, "title", e.target.value)}
                  />
                  <Input
                    placeholder="Company"
                    value={entry.company}
                    onChange={(e) => updateExperience(index, "company", e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input
                    placeholder="Dates, e.g., 2020-Present"
                    value={entry.dates}
                    onChange={(e) => updateExperience(index, "dates", e.target.value)}
                  />
                  {experienceEntries.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="justify-self-end text-red-600 hover:text-red-700"
                      onClick={() => removeExperience(index)}
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      Remove
                    </Button>
                  )}
                </div>
                <Textarea
                  placeholder="Description"
                  rows={2}
                  value={entry.description}
                  onChange={(e) => updateExperience(index, "description", e.target.value)}
                />
              </div>
            ))}
          </div>

          {/* Education entries */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Education</Label>
              <Button type="button" variant="outline" size="sm" onClick={addEducation}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                Add education
              </Button>
            </div>
            {educationEntries.map((entry, index) => (
              <div key={index} className="rounded-lg border p-3 space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input
                    placeholder="School"
                    value={entry.school}
                    onChange={(e) => updateEducation(index, "school", e.target.value)}
                  />
                  <Input
                    placeholder="Degree"
                    value={entry.degree}
                    onChange={(e) => updateEducation(index, "degree", e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input
                    placeholder="Field of study"
                    value={entry.field}
                    onChange={(e) => updateEducation(index, "field", e.target.value)}
                  />
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Dates, e.g., 2015-2019"
                      value={entry.dates}
                      onChange={(e) => updateEducation(index, "dates", e.target.value)}
                    />
                    {educationEntries.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="shrink-0 text-red-600 hover:text-red-700"
                        onClick={() => removeEducation(index)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="skills">Skills (comma-separated)</Label>
              <Input
                id="skills"
                placeholder="React, TypeScript, Node.js..."
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="target-roles">Target Roles (comma-separated)</Label>
              <Input
                id="target-roles"
                placeholder="Senior Engineer, Tech Lead..."
                value={targetRoles}
                onChange={(e) => setTargetRoles(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="career-goals">Career Goals</Label>
            <Textarea
              id="career-goals"
              rows={2}
              placeholder="What are you looking for in your next role?"
              value={careerGoals}
              onChange={(e) => setCareerGoals(e.target.value)}
            />
          </div>
        </TabsContent>
      </Tabs>

      {activeTab !== "search" && (
        <Button
          onClick={() => analyze.mutate()}
          disabled={!canSubmit || analyze.isPending}
          className="w-full"
        >
          {analyze.isPending ? "Analyzing..." : "Analyze LinkedIn Profile"}
        </Button>
      )}
    </div>
  );
}

/**
 * LinkedIn profile analysis page.
 *
 * @returns The page element.
 */
export default function LinkedInAnalysisPage() {
  const [result, setResult] = useState<LinkedInProfileAnalysis | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">LinkedIn Analysis</h1>
          <p className="mt-1 text-sm text-gray-500">
            AI-powered feedback on your LinkedIn profile to attract inbound opportunities.
          </p>
        </div>
        {result && (
          <Button variant="outline" size="sm" onClick={() => setResult(null)}>
            New Analysis
          </Button>
        )}
      </div>

      {result ? (
        <AnalysisDisplay analysis={result} />
      ) : (
        <div className="max-w-2xl">
          <AnalysisForm onResult={setResult} />
        </div>
      )}
    </div>
  );
}
