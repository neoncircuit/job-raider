"""
Career Coach Agent for Job Raider Multi-Agent System

Provides intelligent career guidance, gap analysis, upskilling roadmaps,
and personalized career recommendations.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from ..llm.router import LLMRouter
from .base import AgentCapability, BaseAgent, Task, TaskResult, TaskType

logger = logging.getLogger(__name__)


@dataclass
class SkillGap:
    """Represents a gap in skills."""

    skill_name: str
    current_level: str  # none, beginner, intermediate, advanced
    required_level: str
    gap_severity: str  # low, medium, high, critical
    importance: float  # 0.0 to 1.0
    job_relevance: float  # 0.0 to 1.0
    learning_resources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LearningPath:
    """Represents a learning path for skill development."""

    skill_name: str
    current_level: str
    target_level: str
    estimated_weeks: int
    difficulty: str
    resources: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class CareerRecommendation:
    """Represents a career recommendation."""

    recommendation_type: str  # skill_gap, career_path, upskilling, experience
    title: str
    description: str
    priority: str  # low, medium, high, critical
    confidence: float  # 0.0 to 1.0
    actionable_steps: List[str] = field(default_factory=list)
    timeline: str = ""
    estimated_impact: str = ""
    resources: List[Dict[str, Any]] = field(default_factory=list)


class CareerCoachAgent(BaseAgent):
    """
    Intelligent career coach providing personalized guidance.

    Offers gap analysis, upskilling roadmaps, career path analysis,
    and strategic recommendations based on user profile and job market.
    """

    def __init__(self, llm_router: LLMRouter) -> None:
        """
        Initialize the career coach agent.

        Args:
            llm_router: LLM router for intelligent analysis
        """
        capabilities = AgentCapability(
            task_types=[
                TaskType.CAREER_PATH_ANALYSIS,
                TaskType.UPSKILLING_ROADMAP,
                TaskType.CAREER_GOAL_SETTING,
                TaskType.SKILL_DEVELOPMENT_PLAN,
                TaskType.GAP_ANALYSIS,
            ],
            parallel_execution=False,  # Sequential processing for career guidance
            dependencies=["resume_intelligence", "job_intelligence"],
            resource_requirements={"memory": "medium", "cpu": "medium"},
            max_concurrent_tasks=2,
            average_execution_time=15.0,
        )

        super().__init__("career_coach", capabilities)

        self.llm_router = llm_router
        self.career_templates = self._load_career_templates()
        self.learning_resources = self._load_learning_resources()

        logger.info("Career Coach Agent initialized")

    def _load_career_templates(self) -> Dict[str, Any]:
        """Load career path templates."""
        templates = {
            "software_engineer": {
                "career_levels": [
                    "entry",
                    "junior",
                    "mid",
                    "senior",
                    "lead",
                    "principal",
                ],
                "skill_progressions": {
                    "entry": [
                        "basic_programming",
                        "data_structures",
                        "version_control",
                    ],
                    "junior": ["frameworks", "databases", "testing", "collaboration"],
                    "mid": [
                        "system_design",
                        "api_design",
                        "performance_optimization",
                        "mentoring",
                    ],
                    "senior": [
                        "architecture",
                        "leadership",
                        "complex_problem_solving",
                        "code_review",
                    ],
                    "lead": [
                        "team_leadership",
                        "technical_strategy",
                        "cross_team_coordination",
                    ],
                    "principal": [
                        "technical_vision",
                        "org_impact",
                        "innovation",
                        "strategic_planning",
                    ],
                },
                "typical_timeline": {
                    "entry_to_junior": "1-2 years",
                    "junior_to_mid": "2-3 years",
                    "mid_to_senior": "3-5 years",
                    "senior_to_lead": "2-4 years",
                    "lead_to_principal": "3-5 years",
                },
            },
            "data_scientist": {
                "career_levels": [
                    "analyst",
                    "junior_ds",
                    "data_scientist",
                    "senior_ds",
                    "lead_ds",
                    "principal_ds",
                ],
                "skill_progressions": {
                    "analyst": [
                        "sql",
                        "excel",
                        "basic_statistics",
                        "data_visualization",
                    ],
                    "junior_ds": [
                        "python",
                        "machine_learning_basics",
                        "data_cleaning",
                        "statistical_analysis",
                    ],
                    "data_scientist": [
                        "advanced_ml",
                        "feature_engineering",
                        "model_deployment",
                        "experimentation",
                    ],
                    "senior_ds": [
                        "deep_learning",
                        "nlp",
                        "mlops",
                        "model_optimization",
                    ],
                    "lead_ds": [
                        "team_leadership",
                        "project_management",
                        "technical_strategy",
                    ],
                    "principal_ds": [
                        "research_direction",
                        "org_impact",
                        "innovation",
                        "strategic_planning",
                    ],
                },
                "typical_timeline": {
                    "analyst_to_junior_ds": "1-2 years",
                    "junior_ds_to_ds": "2-3 years",
                    "ds_to_senior_ds": "3-5 years",
                    "senior_ds_to_lead_ds": "2-4 years",
                },
            },
        }
        return templates

    def _load_learning_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load learning resources database."""
        return {
            "programming": [
                {
                    "name": "Python Official Tutorial",
                    "url": "https://docs.python.org/3/tutorial/",
                    "type": "documentation",
                    "difficulty": "beginner",
                    "duration_weeks": 4,
                    "cost": "free",
                    "quality": "high",
                },
                {
                    "name": "LeetCode",
                    "url": "https://leetcode.com/",
                    "type": "practice",
                    "difficulty": "intermediate",
                    "duration_weeks": 8,
                    "cost": "free",
                    "quality": "high",
                },
            ],
            "machine_learning": [
                {
                    "name": "Andrew Ng's ML Course",
                    "url": "https://www.coursera.org/learn/machine-learning",
                    "type": "course",
                    "difficulty": "beginner",
                    "duration_weeks": 12,
                    "cost": "free",
                    "quality": "high",
                },
                {
                    "name": "Fast.ai",
                    "url": "https://www.fast.ai/",
                    "type": "course",
                    "difficulty": "intermediate",
                    "duration_weeks": 8,
                    "cost": "free",
                    "quality": "high",
                },
            ],
            "system_design": [
                {
                    "name": "System Design Primer",
                    "url": "https://github.com/donnemartin/system-design-primer",
                    "type": "documentation",
                    "difficulty": "intermediate",
                    "duration_weeks": 6,
                    "cost": "free",
                    "quality": "high",
                }
            ],
        }

    async def execute_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        """
        Execute career coach task.

        Args:
            task: The task to execute
            context: Additional context including profile, jobs, etc.

        Returns:
            TaskResult with career analysis results
        """
        try:
            if task.type == TaskType.GAP_ANALYSIS:
                result_data = await self._analyze_gaps(task.data, context)
            elif task.type == TaskType.CAREER_PATH_ANALYSIS:
                result_data = await self._analyze_career_path(task.data, context)
            elif task.type == TaskType.UPSKILLING_ROADMAP:
                result_data = await self._create_upskilling_roadmap(task.data, context)
            elif task.type == TaskType.CAREER_GOAL_SETTING:
                result_data = await self._set_career_goals(task.data, context)
            elif task.type == TaskType.SKILL_DEVELOPMENT_PLAN:
                result_data = await self._create_skill_development_plan(
                    task.data, context
                )
            else:
                raise ValueError(f"Unsupported task type: {task.type}")

            return TaskResult(
                task_id=task.task_id,
                success=True,
                data=result_data,
                confidence=0.8,
                metrics={"analysis_type": task.type.value},
            )

        except Exception as e:
            logger.error(f"Error executing career coach task: {e}")
            return TaskResult(
                task_id=task.task_id, success=False, error=str(e), confidence=0.0
            )

    async def validate_task(self, task: Task) -> bool:
        """Validate career coach task."""
        if task.type not in self.capabilities.task_types:
            return False

        # Check for required data based on task type
        if task.type == TaskType.GAP_ANALYSIS:
            required_fields = ["profile", "target_jobs"]
        elif task.type == TaskType.CAREER_PATH_ANALYSIS:
            required_fields = ["profile"]
        elif task.type == TaskType.UPSKILLING_ROADMAP:
            # A roadmap can be produced either from a precomputed gap analysis
            # or from resolved target jobs (from which gaps are derived).
            combined_data = {**task.data, **task.context}
            has_gap = bool((combined_data.get("gap_analysis") or {}).get("skills_gap"))
            has_targets = bool(combined_data.get("target_jobs"))
            return has_gap or has_targets
        elif task.type == TaskType.CAREER_GOAL_SETTING:
            required_fields = ["profile"]
        elif task.type == TaskType.SKILL_DEVELOPMENT_PLAN:
            required_fields = ["skill_name", "current_level"]
        else:
            return False

        # Check if required fields are present in data or context
        combined_data = {**task.data, **task.context}
        return all(field in combined_data for field in required_fields)

    async def _analyze_gaps(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze skill gaps between profile and target jobs.

        Args:
            data: Task-specific data
            context: Profile and job information

        Returns:
            Gap analysis results
        """
        profile = context.get("profile", data.get("profile", {}))
        target_jobs = context.get("target_jobs", data.get("target_jobs", []))

        gap_analysis = {
            "skills_gap": {},
            "experience_gap": {},
            "education_gap": {},
            "recommendations": [],
        }

        # Analyze skill gaps for each job
        for job in target_jobs:
            job_analysis = self._analyze_job_skill_gaps(profile, job)
            gap_analysis["skills_gap"][job_analysis["job_title"]] = job_analysis[
                "gap_data"
            ]

            # Generate recommendations for missing skills
            job_recommendations = self._generate_skill_gap_recommendations(
                job_analysis["missing_skills"], job_analysis["job_title"]
            )
            gap_analysis["recommendations"].extend(job_recommendations)

        return gap_analysis

    def _analyze_job_skill_gaps(
        self, profile: Dict[str, Any], job: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze skill gaps for a specific job.

        Args:
            profile: User profile data
            job: Job description data

        Returns:
            Job analysis with gap information
        """
        job_title = job.get("title", "unknown")
        required_skills = set(
            skill.get("name", "").lower() for skill in job.get("skills", [])
        )

        # Get user skills from profile
        user_skills = set(
            skill.get("name", "").lower() for skill in profile.get("skills", [])
        )

        # Calculate gaps
        missing_skills = required_skills - user_skills
        overlap_skills = required_skills & user_skills

        return {
            "job_title": job_title,
            "missing_skills": missing_skills,
            "gap_data": {
                "missing": list(missing_skills),
                "overlap": list(overlap_skills),
                "coverage": (
                    len(overlap_skills) / len(required_skills) if required_skills else 0
                ),
                "total_required": len(required_skills),
                "total_matched": len(overlap_skills),
            },
        }

    def _generate_skill_gap_recommendations(
        self, missing_skills: set, job_title: str
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations for missing skills.

        Args:
            missing_skills: Set of missing skill names
            job_title: Job title for context

        Returns:
            List of skill gap recommendations
        """
        recommendations = []

        for skill in missing_skills:
            skill_gap = SkillGap(
                skill_name=skill,
                current_level="none",
                required_level="intermediate",
                gap_severity=self._determine_skill_severity(skill),
                importance=0.8,
                job_relevance=1.0,
                learning_resources=self._get_learning_resources_for_skill(skill),
            )
            recommendations.append(
                {
                    "type": "skill_gap",
                    "skill": skill,
                    "severity": skill_gap.gap_severity,
                    "job": job_title,
                    "resources": skill_gap.learning_resources,
                }
            )

        return recommendations

    def _determine_skill_severity(self, skill: str) -> str:
        """
        Determine the severity level of a skill gap.

        Args:
            skill: Skill name

        Returns:
            Severity level (high, medium, low)
        """
        critical_skills = {"python", "javascript", "sql", "java", "react", "node.js"}
        if skill in critical_skills:
            return "high"
        elif skill in {"html", "css", "git", "bash"}:
            return "medium"
        else:
            return "low"

    async def _analyze_career_path(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze career path and provide strategic recommendations.

        Args:
            data: Task-specific data
            context: Profile information

        Returns:
            Career path analysis results
        """
        profile = context.get("profile", data.get("profile", {}))

        career_analysis = {
            "current_positioning": self._analyze_current_position(profile),
            "career_trajectory": self._predict_career_trajectory(profile),
            "target_alignment": {},
            "strategic_recommendations": self._generate_strategic_recommendations(
                profile
            ),
        }

        return career_analysis

    async def _create_upskilling_roadmap(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create structured upskilling roadmap with timeline.

        Args:
            data: Task-specific data
            context: Gap analysis and profile information

        Returns:
            Upskilling roadmap results
        """
        gap_analysis = context.get("gap_analysis", data.get("gap_analysis")) or {}
        profile = context.get("profile", data.get("profile", {}))

        # When no precomputed gap analysis is supplied, derive one from the
        # resolved target jobs so callers can request a roadmap from keywords
        # alone (no need to paste raw gap-analysis JSON).
        if not gap_analysis.get("skills_gap") and context.get("target_jobs"):
            gap_analysis = await self._analyze_gaps(data, context)

        # Extract skill gaps
        skill_gaps = gap_analysis.get("skills_gap", {})
        missing_skills = set()
        for job_title, gap_data in skill_gaps.items():
            missing_skills.update(gap_data.get("missing", []))

        # Create roadmap
        roadmap = {
            "priority_skills": self._prioritize_skills(missing_skills),
            "learning_paths": self._generate_learning_paths(missing_skills),
            "timeline": self._create_timeline(missing_skills, profile),
            "resource_recommendations": self._recommend_learning_resources(
                missing_skills
            ),
            "milestones": self._create_milestones(missing_skills),
        }

        return roadmap

    async def _set_career_goals(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Set SMART career goals based on profile and market analysis.

        Args:
            data: Task-specific data
            context: Profile information

        Returns:
            Career goals results
        """
        profile = context.get("profile", data.get("profile", {}))

        career_goals = {
            "short_term_goals": [],
            "medium_term_goals": [],
            "long_term_goals": [],
            "smart_goals": [],
        }

        # Generate SMART goals
        experience_years = self._calculate_experience_years(profile)

        if experience_years < 2:
            career_goals["short_term_goals"] = [
                {
                    "goal": "Land first developer role",
                    "timeline": "3-6 months",
                    "actions": [
                        "Build portfolio projects",
                        "Apply to junior positions",
                        "Network in tech community",
                    ],
                }
            ]
        elif experience_years < 5:
            career_goals["medium_term_goals"] = [
                {
                    "goal": "Advance to mid-level developer",
                    "timeline": "1-2 years",
                    "actions": [
                        "Master system design",
                        "Lead small projects",
                        "Mentor junior developers",
                    ],
                }
            ]

        return career_goals

    async def _create_skill_development_plan(
        self, data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create personalized skill development plan.

        Args:
            data: Task-specific data
            context: Profile and skill information

        Returns:
            Skill development plan results
        """
        skill_name = data.get("skill_name", "")
        current_level = data.get("current_level", "beginner")

        development_plan = {
            "skill_name": skill_name,
            "current_level": current_level,
            "target_level": "advanced",
            "learning_path": self._get_learning_path_for_skill(
                skill_name, current_level
            ),
            "estimated_duration": "8-12 weeks",
            "milestones": self._create_skill_milestones(skill_name, current_level),
            "practice_projects": self._recommend_practice_projects(skill_name),
            "assessment_criteria": self._define_assessment_criteria(skill_name),
        }

        return development_plan

    def _analyze_current_position(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze current career positioning.

        Args:
            profile: User profile data containing skills and experience

        Returns:
            Dictionary with current position analysis including experience level,
            skill count, primary skills, and positioning score
        """
        experience_years: float = self._calculate_experience_years(profile)
        skills = profile.get("skills", [])

        return {
            "experience_level": self._determine_experience_level(experience_years),
            "skill_count": len(skills),
            "primary_skills": [skill.get("name") for skill in skills[:5]],
            "positioning_score": self._calculate_positioning_score(profile),
        }

    def _predict_career_trajectory(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict career trajectory based on profile experience and skills.

        Args:
            profile: User profile data containing experience and skills

        Returns:
            Dictionary with career trajectory prediction including current stage,
            next stage, promotion timeline, and required advancements
        """
        experience_years: float = self._calculate_experience_years(profile)

        trajectory = {
            "current_stage": self._determine_career_stage(experience_years),
            "next_stage": self._determine_next_stage(experience_years),
            "estimated_timeline": self._estimate_promotion_timeline(experience_years),
            "required_advancements": self._identify_advancement_requirements(profile),
        }

        return trajectory

    def _generate_strategic_recommendations(
        self, profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate strategic career recommendations."""
        recommendations = []
        experience_years = self._calculate_experience_years(profile)

        # Entry-level recommendations
        if experience_years < 2:
            recommendations.append(
                {
                    "category": "entry_strategy",
                    "title": "Entry-Level Focus",
                    "description": "Focus on entry-level positions or internships",
                    "priority": "high",
                    "actions": [
                        "Apply to junior developer positions",
                        "Consider internship opportunities",
                        "Build portfolio projects",
                        "Contribute to open source",
                    ],
                }
            )

        # Skill development recommendations
        skills = profile.get("skills", [])
        if len(skills) < 5:
            recommendations.append(
                {
                    "category": "skill_development",
                    "title": "Expand Technical Skills",
                    "description": "Develop broader technical skill set",
                    "priority": "high",
                    "actions": [
                        "Learn at least one new programming language",
                        "Gain experience with different frameworks",
                        "Build diverse projects",
                    ],
                }
            )

        return recommendations

    def _prioritize_skills(self, missing_skills: set[str]) -> List[Dict[str, Any]]:
        """
        Prioritize missing skills by market demand and importance.

        Args:
            missing_skills: Set of missing skill names to prioritize

        Returns:
            List of prioritized skills with priority levels and reasoning,
            sorted by priority (high first)
        """
        skill_priority = [
            "python",
            "javascript",
            "sql",
            "java",
            "react",
            "node.js",
            "machine learning",
            "data analysis",
            "cloud computing",
        ]

        prioritized = []
        for skill in missing_skills:
            priority_level = "high" if skill.lower() in skill_priority else "medium"
            prioritized.append(
                {
                    "skill": skill,
                    "priority": priority_level,
                    "reason": (
                        "High demand skill"
                        if priority_level == "high"
                        else "Good to have"
                    ),
                }
            )

        return sorted(prioritized, key=lambda x: x["priority"] == "high", reverse=True)

    def _generate_learning_paths(self, missing_skills: set) -> List[Dict[str, Any]]:
        """Generate learning paths for missing skills.

        Returns plain dicts (via ``asdict``) so the roadmap payload stays JSON
        serializable when the task result is returned by the API.
        """
        learning_paths = []

        for skill in missing_skills:
            learning_path = LearningPath(
                skill_name=skill,
                current_level="none",
                target_level="intermediate",
                estimated_weeks=8,
                difficulty="medium",
                resources=self._get_learning_resources_for_skill(skill),
                milestones=[
                    {"week": 2, "milestone": f"Complete {skill} basics"},
                    {"week": 4, "milestone": f"Build first {skill} project"},
                    {"week": 6, "milestone": f"Master intermediate {skill} concepts"},
                    {"week": 8, "milestone": f"Complete advanced {skill} project"},
                ],
                prerequisites=[],
            )

            learning_paths.append(asdict(learning_path))

        return learning_paths

    def _create_timeline(
        self, missing_skills: set, profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create realistic timeline for skill development."""
        experience_years = self._calculate_experience_years(profile)

        base_weeks = 4  # Base learning time per skill
        if experience_years < 1:
            base_weeks = 6  # More time for less experienced

        return {
            "total_weeks": len(missing_skills) * base_weeks,
            "phases": [
                {
                    "phase": "Foundation",
                    "duration_weeks": base_weeks,
                    "skills": list(missing_skills)[:3],
                },
                {
                    "phase": "Advanced",
                    "duration_weeks": base_weeks * 2,
                    "skills": list(missing_skills)[3:],
                },
            ],
        }

    def _recommend_learning_resources(
        self, missing_skills: set
    ) -> List[Dict[str, Any]]:
        """Recommend learning resources for missing skills."""
        resources = []

        for skill in missing_skills:
            skill_resources = self._get_learning_resources_for_skill(skill)
            resources.extend(skill_resources)

        return resources

    def _create_milestones(self, missing_skills: set) -> List[Dict[str, Any]]:
        """Create learning milestones."""
        milestones = []
        week = 0

        for skill in list(missing_skills)[:5]:  # Limit to top 5 skills
            week += 2
            milestones.append(
                {
                    "week": week,
                    "milestone": f"Complete {skill} fundamentals",
                    "skill": skill,
                }
            )

        return milestones

    def _get_learning_resources_for_skill(self, skill: str) -> List[Dict[str, Any]]:
        """Get learning resources for a specific skill."""
        skill_lower = skill.lower()

        # Map skills to resource categories
        resource_map = {
            "python": "programming",
            "javascript": "programming",
            "java": "programming",
            "machine learning": "machine_learning",
            "ml": "machine_learning",
            "data science": "machine_learning",
            "system design": "system_design",
            "architecture": "system_design",
        }

        category = resource_map.get(skill_lower, "programming")
        return self.learning_resources.get(category, [])

    def _get_learning_path_for_skill(
        self, skill_name: str, current_level: str
    ) -> List[str]:
        """Get learning path for a specific skill."""
        return [
            f"Learn {skill_name} fundamentals",
            f"Practice {skill_name} with projects",
            f"Master intermediate {skill_name} concepts",
            f"Build advanced {skill_name} applications",
        ]

    def _create_skill_milestones(
        self, skill_name: str, current_level: str
    ) -> List[Dict[str, Any]]:
        """Create milestones for skill development."""
        return [
            {"week": 2, "milestone": f"Learn {skill_name} basics"},
            {"week": 4, "milestone": f"Build first {skill_name} project"},
            {"week": 6, "milestone": "Master intermediate concepts"},
            {"week": 8, "milestone": "Complete advanced project"},
        ]

    def _recommend_practice_projects(self, skill_name: str) -> List[str]:
        """Recommend practice projects for skill development."""
        return [
            f"Build a {skill_name} calculator",
            f"Create a {skill_name} web scraper",
            f"Develop a {skill_name} API",
        ]

    def _define_assessment_criteria(self, skill_name: str) -> List[str]:
        """Define assessment criteria for skill mastery."""
        return [
            f"Explain {skill_name} concepts clearly",
            f"Solve {skill_name} problems independently",
            f"Build {skill_name} projects from scratch",
            f"Debug {skill_name} code effectively",
        ]

    def _calculate_experience_years(self, profile: Dict[str, Any]) -> float:
        """Calculate total years of experience."""
        experiences = profile.get("experience", [])
        total_years = 0.0

        for exp in experiences:
            start_date = exp.get("start_date")
            end_date = exp.get("end_date") or datetime.now()

            if start_date:
                try:
                    if isinstance(start_date, str):
                        start_date = datetime.fromisoformat(
                            start_date.replace("Z", "+00:00")
                        )
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(
                            end_date.replace("Z", "+00:00")
                        )

                    years = (end_date - start_date).days / 365.25
                    total_years += years

                except (ValueError, AttributeError) as e:
                    logger.warning(
                        f"Invalid date format in experience data: {start_date}, {end_date}. Error: {e}"
                    )
                    # Skip this experience entry
                    continue

        return total_years

    def _determine_experience_level(self, years: float) -> str:
        """Determine experience level from years."""
        if years < 1:
            return "entry"
        elif years < 3:
            return "junior"
        elif years < 5:
            return "mid"
        elif years < 8:
            return "senior"
        else:
            return "lead"

    def _determine_career_stage(self, years: float) -> str:
        """Determine career stage."""
        if years < 1:
            return "early_career"
        elif years < 5:
            return "growth"
        elif years < 10:
            return "established"
        else:
            return "senior_leadership"

    def _determine_next_stage(self, years: float) -> str:
        """Determine next career stage."""
        current = self._determine_career_stage(years)
        stages = ["early_career", "growth", "established", "senior_leadership"]

        try:
            current_index = stages.index(current)
            if current_index < len(stages) - 1:
                return stages[current_index + 1]
        except ValueError:
            pass

        return current

    def _estimate_promotion_timeline(self, years: float) -> str:
        """Estimate time until next promotion."""
        if years < 1:
            return "6-12 months"
        elif years < 3:
            return "1-2 years"
        elif years < 5:
            return "2-3 years"
        else:
            return "3-5 years"

    def _identify_advancement_requirements(self, profile: Dict[str, Any]) -> List[str]:
        """Identify requirements for career advancement."""
        return [
            "Develop leadership skills",
            "Master system design",
            "Build portfolio of successful projects",
            "Gain experience with larger systems",
            "Develop mentoring abilities",
        ]

    def _calculate_positioning_score(self, profile: Dict[str, Any]) -> float:
        """Calculate career positioning score."""
        score = 0.5  # Base score

        skills = profile.get("skills", [])
        experience = self._calculate_experience_years(profile)

        # Add points for skills
        score += min(len(skills) * 0.02, 0.3)

        # Add points for experience
        score += min(experience * 0.05, 0.2)

        return min(score, 1.0)
