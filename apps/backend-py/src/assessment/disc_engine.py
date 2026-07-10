"""
Job Raider - DISC Assessment Engine

Handles DISC personality assessment sessions including question loading,
Most/Least answer scoring, profile calculation, and job matching.

Author: Job Raider
Date: 2026-06-05
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from ..utils.logger import Components, get_logger
from src.models.assessment import DISCAnswer, DISCResult, DISCScore, DISCTrait

logger = get_logger(Components.GENERATION)


class DISCEngine:
    """Engine for DISC personality assessment sessions.

    Handles loading questions from configuration, generating sessions,
    scoring Most/Least answers, and calculating personality profiles.

    Attributes:
        questions_path: Path to DISC questions JSON file.
        results_path: Path to store DISC assessment results.
        questions: Cached loaded questions from configuration.
    """

    def __init__(
        self,
        questions_path: Optional[Path] = None,
        results_path: Optional[Path] = None,
    ) -> None:
        """Initialize the DISC assessment engine.

        Args:
            questions_path: Path to DISC questions JSON file.
                           Defaults to config/disc_questions.json.
            results_path: Path to store DISC assessment results.
                          Defaults to data/disc_results/.
        """
        self.questions_path = questions_path or Path("config/disc_questions.json")
        self.results_path = results_path or Path("data/disc_results/")
        self.questions: List[Dict[str, Any]] = []
        self._load_questions()

        # Ensure results directory exists
        self.results_path.mkdir(parents=True, exist_ok=True)

    def _load_questions(self) -> None:
        """Load DISC questions from configuration file.

        Raises:
            FileNotFoundError: If questions file doesn't exist.
            json.JSONDecodeError: If questions file is invalid JSON.
        """
        try:
            with open(self.questions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.questions = data.get("questions", [])
                logger.info(f"Loaded {len(self.questions)} DISC questions")
        except FileNotFoundError:
            logger.error(f"DISC questions file not found: {self.questions_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in DISC questions file: {e}")
            raise

    def generate_session(self) -> Dict[str, Any]:
        """Generate a new DISC assessment session.

        Returns:
            Dictionary containing:
                - session_id: Unique session identifier.
                - questions: List of DISC questions for the assessment.
        """
        session_id = str(uuid4())

        # Convert JSON questions to the format expected by frontend
        frontend_questions = []
        for q in self.questions:
            frontend_questions.append(
                {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "options": [
                        {
                            "label": opt["label"],
                            "text": opt["text"],
                            "scores": opt["scores"],
                        }
                        for opt in q["options"]
                    ],
                }
            )

        logger.info(
            f"Generated DISC session {session_id} with {len(frontend_questions)} questions"
        )

        return {
            "session_id": session_id,
            "questions": frontend_questions,
        }

    def calculate_scores(self, answers: List[DISCAnswer]) -> List[DISCScore]:
        """Calculate DISC trait scores from Most/Least answers.

        Scoring:
        - Most like: +3 points for that trait
        - Least like: -3 points for that trait

        Args:
            answers: List of DISC answers with most_like and least_like selections.

        Returns:
            List of DISCScore objects, one for each trait (D, I, S, C).
        """
        # Initialize raw scores for each trait
        raw_scores = {trait.value: 0 for trait in DISCTrait}

        # Build a lookup for question scores
        question_scores = {}
        for q in self.questions:
            question_scores[q["id"]] = {
                opt["label"]: opt["scores"] for opt in q["options"]
            }

        # Calculate scores based on answers
        for answer in answers:
            q_scores = question_scores.get(answer.question_id, {})

            # Most like: +3 points for the trait associated with that option
            if answer.most_like in q_scores:
                most_scores = q_scores[answer.most_like]
                for trait, score in most_scores.items():
                    raw_scores[trait] += score * 3

            # Least like: -3 points for the trait associated with that option
            if answer.least_like in q_scores:
                least_scores = q_scores[answer.least_like]
                for trait, score in least_scores.items():
                    raw_scores[trait] -= score * 3

        # Calculate percentages (normalized to 0-100)
        # Range of raw scores is roughly -18 to +18
        min_score = min(raw_scores.values())
        max_score = max(raw_scores.values())
        score_range = max_score - min_score if max_score != min_score else 1

        disc_scores = []
        for trait in DISCTrait:
            raw = raw_scores[trait.value]
            # Normalize to 0-100 based on the range
            percentage = ((raw - min_score) / score_range) * 100
            disc_scores.append(
                DISCScore(
                    trait=trait,
                    raw_score=raw,
                    percentage=round(percentage, 1),
                )
            )

        return disc_scores

    def determine_profile_type(
        self,
        scores: List[DISCScore],
    ) -> Tuple[DISCTrait, Optional[DISCTrait]]:
        """Determine primary and secondary DISC types from scores.

        Args:
            scores: List of DISC scores for all traits.

        Returns:
            Tuple of (primary_trait, secondary_trait).
            Secondary trait may be None if one trait dominates.
        """
        # Sort by percentage to find top traits
        sorted_scores = sorted(scores, key=lambda s: s.percentage, reverse=True)

        primary = sorted_scores[0].trait

        # Check if there's a clear secondary type
        # If second highest is within 15% of highest, consider it secondary
        if len(sorted_scores) > 1:
            second_highest = sorted_scores[1]
            if sorted_scores[0].percentage - second_highest.percentage < 15:
                secondary = second_highest.trait
            else:
                secondary = None
        else:
            secondary = None

        return primary, secondary

    def calculate_profile_percentages(
        self, scores: List[DISCScore]
    ) -> Dict[str, float]:
        """Calculate normalized D/I/S/C profile percentages.

        Ensures percentages sum to 100%.

        Args:
            scores: List of DISC scores.

        Returns:
            Dictionary with trait labels as keys and percentages as values.
        """
        total = sum(s.percentage for s in scores)
        if total == 0:
            return {trait.value: 25.0 for trait in DISCTrait}

        profile = {}
        for score in scores:
            profile[score.trait.value] = round((score.percentage / total) * 100, 1)

        # Ensure sum is exactly 100
        current_sum = sum(profile.values())
        if current_sum != 100:
            # Adjust the highest value
            highest_trait = max(profile, key=profile.get)
            profile[highest_trait] += round(100 - current_sum, 1)

        return profile

    def save_result(self, result: DISCResult) -> None:
        """Save DISC assessment result to file.

        Args:
            result: DISC result to save.
        """
        result_path = self.results_path / f"{result.session_id}.json"

        result_data = result.model_dump(mode="json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, default=str)

        logger.info(f"Saved DISC result to {result_path}")

    def load_latest_result(self) -> Optional[DISCResult]:
        """Load the most recent DISC assessment result.

        Returns:
            DISC result if found, None otherwise.
        """
        result_files = list(self.results_path.glob("*.json"))
        if not result_files:
            return None

        # Get most recent file by modification time
        latest_file = max(result_files, key=lambda f: f.stat().st_mtime)

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return DISCResult(**data)


class DISCJobMatcher:
    """Match DISC profiles to suitable job types.

    Analyzes personality profiles against job requirements to find
    suitable career matches.

    Attributes:
        profiles_path: Path to job profiles JSON configuration.
        job_profiles: Cached loaded job profiles.
    """

    def __init__(self, profiles_path: Optional[Path] = None) -> None:
        """Initialize the DISC job matcher.

        Args:
            profiles_path: Path to job profiles JSON file.
                          Defaults to config/disc_job_profiles.json.
        """
        self.profiles_path = profiles_path or Path("config/disc_job_profiles.json")
        self.job_profiles: List[Dict[str, Any]] = []
        self._load_job_profiles()

    def _load_job_profiles(self) -> None:
        """Load job profiles from configuration file.

        Creates a default file if it doesn't exist.
        """
        if not self.profiles_path.exists():
            logger.warning(
                f"Job profiles file not found, creating defaults: {self.profiles_path}"
            )
            self._create_default_profiles()
            return

        try:
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.job_profiles = data.get("job_profiles", [])
                logger.info(f"Loaded {len(self.job_profiles)} job profiles")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in job profiles file: {e}")
            self._create_default_profiles()

    def _create_default_profiles(self) -> None:
        """Create default job profiles configuration."""
        self.job_profiles = [
            {
                "job_type": "Software Engineer",
                "ideal_profile": {"D": 30, "I": 20, "S": 25, "C": 25},
                "acceptable_ranges": {
                    "D": [20, 40],
                    "I": [15, 30],
                    "S": [20, 35],
                    "C": [20, 40],
                },
                "description": "Balanced technical role with focus on problem-solving and precision",
            },
            {
                "job_type": "Sales / Business Development",
                "ideal_profile": {"D": 35, "I": 35, "S": 15, "C": 15},
                "acceptable_ranges": {
                    "D": [30, 45],
                    "I": [30, 45],
                    "S": [10, 25],
                    "C": [10, 25],
                },
                "description": "High-energy role requiring persuasion and relationship-building",
            },
            {
                "job_type": "Project Manager",
                "ideal_profile": {"D": 35, "I": 25, "S": 25, "C": 15},
                "acceptable_ranges": {
                    "D": [30, 45],
                    "I": [20, 35],
                    "S": [20, 35],
                    "C": [10, 25],
                },
                "description": "Leadership role coordinating teams and driving results",
            },
            {
                "job_type": "Data Analyst",
                "ideal_profile": {"D": 20, "I": 15, "S": 25, "C": 40},
                "acceptable_ranges": {
                    "D": [15, 30],
                    "I": [10, 25],
                    "S": [20, 35],
                    "C": [35, 50],
                },
                "description": "Analytical role requiring precision and systematic thinking",
            },
            {
                "job_type": "Team Lead / Engineering Manager",
                "ideal_profile": {"D": 30, "I": 25, "S": 30, "C": 15},
                "acceptable_ranges": {
                    "D": [25, 40],
                    "I": [20, 35],
                    "S": [25, 40],
                    "C": [10, 25],
                },
                "description": "Leadership role balancing technical guidance with team support",
            },
            {
                "job_type": "Product Manager",
                "ideal_profile": {"D": 30, "I": 30, "S": 20, "C": 20},
                "acceptable_ranges": {
                    "D": [25, 40],
                    "I": [25, 40],
                    "S": [15, 30],
                    "C": [15, 30],
                },
                "description": "Strategic role requiring vision and stakeholder coordination",
            },
            {
                "job_type": "DevOps Engineer",
                "ideal_profile": {"D": 25, "I": 20, "S": 25, "C": 30},
                "acceptable_ranges": {
                    "D": [20, 35],
                    "I": [15, 30],
                    "S": [20, 35],
                    "C": [25, 40],
                },
                "description": "Technical role balancing automation with stability",
            },
            {
                "job_type": "Customer Success Manager",
                "ideal_profile": {"D": 20, "I": 30, "S": 35, "C": 15},
                "acceptable_ranges": {
                    "D": [15, 30],
                    "I": [25, 40],
                    "S": [30, 45],
                    "C": [10, 25],
                },
                "description": "Support-focused role requiring relationship-building and patience",
            },
        ]

        # Save to file
        self.profiles_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profiles_path, "w", encoding="utf-8") as f:
            json.dump({"job_profiles": self.job_profiles}, f, indent=2)

        logger.info(f"Created default job profiles at {self.profiles_path}")

    def calculate_match_score(
        self,
        disc_profile: Dict[str, float],
        job_profile: Dict[str, Any],
    ) -> float:
        """Calculate match score between DISC profile and job.

        Uses Euclidean distance between profiles, converted to a percentage.

        Args:
            disc_profile: User's D/I/S/C percentages.
            job_profile: Job profile configuration.

        Returns:
            Match score from 0-100 (higher is better match).
        """
        ideal = job_profile["ideal_profile"]
        acceptable = job_profile["acceptable_ranges"]

        # Calculate Euclidean distance
        distance_squared = 0.0
        for trait in ["D", "I", "S", "C"]:
            user_value = disc_profile.get(trait, 25)
            ideal_value = ideal[trait]
            distance_squared += (user_value - ideal_value) ** 2

        distance = distance_squared**0.5

        # Maximum possible distance (roughly 50 for each trait)
        max_distance = 100.0

        # Convert to match percentage
        match_score = max(0, 100 - (distance / max_distance * 100))

        # Check if all traits are within acceptable ranges
        all_within_range = True
        for trait in ["D", "I", "S", "C"]:
            user_value = disc_profile.get(trait, 25)
            range_min, range_max = acceptable[trait]
            if not (range_min <= user_value <= range_max):
                all_within_range = False
                break

        # Boost score if within acceptable ranges
        if all_within_range:
            match_score = min(100, match_score + 10)

        return round(match_score, 1)

    def get_top_matches(
        self,
        disc_profile: Dict[str, float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get top job matches for a DISC profile.

        Args:
            disc_profile: User's D/I/S/C percentages.
            limit: Maximum number of matches to return.

        Returns:
            List of job matches sorted by match score.
        """
        matches = []

        for job in self.job_profiles:
            match_score = self.calculate_match_score(disc_profile, job)

            matches.append(
                {
                    "job_type": job["job_type"],
                    "match_score": match_score,
                    "description": job["description"],
                    "ideal_profile": job["ideal_profile"],
                }
            )

        # Sort by match score descending
        matches.sort(key=lambda m: m["match_score"], reverse=True)

        return matches[:limit]
