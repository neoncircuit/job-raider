"""
Job Raider - A/B Testing Module

This module provides A/B testing capability for comparing different
scoring heuristics, model configurations, and pipeline parameters.

Author: Job Raider
Date: 2026-04-21
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..scoring.matcher import JobMatcher
from ..utils.logger import Components, get_logger


class ExperimentStatus(str, Enum):
    """Status of an A/B test experiment."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment."""

    name: str
    description: str
    # Scoring weights to test
    weights_a: Dict[str, int]
    weights_b: Dict[str, int]
    # Other parameters
    min_score_a: int = 60
    min_score_b: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Results from an A/B test experiment."""

    experiment_name: str
    variant_a: Dict[str, Any]
    variant_b: Dict[str, Any]
    winner: Optional[str]  # "A", "B", or None (tie)
    significance: float  # 0-1, confidence in winner
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class ABTester:
    """
    Perform A/B testing on scoring heuristics.

    Compares different scoring configurations to determine which
    produces better outcomes.
    """

    def __init__(self, storage_dir: str = "data/experiments"):
        """
        Initialize A/B tester.

        Args:
            storage_dir: Directory to store experiment results
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(Components.SCRAPERS)

    def create_experiment(
        self,
        config: ExperimentConfig,
    ) -> str:
        """
        Create a new A/B test experiment.

        Args:
            config: Experiment configuration

        Returns:
            Experiment ID
        """
        experiment_id = self._generate_experiment_id(config.name)

        experiment_data = {
            "experiment_id": experiment_id,
            "name": config.name,
            "description": config.description,
            "status": ExperimentStatus.PENDING.value,
            "config": {
                "weights_a": config.weights_a,
                "weights_b": config.weights_b,
                "min_score_a": config.min_score_a,
                "min_score_b": config.min_score_b,
            },
            "created_at": datetime.now().isoformat(),
            "metadata": config.metadata,
        }

        # Save experiment
        filepath = self.storage_dir / f"{experiment_id}.json"
        with open(filepath, "w") as f:
            json.dump(experiment_data, f, indent=2)

        self.logger.info(f"Created experiment: {experiment_id}")

        return experiment_id

    def run_experiment(
        self,
        experiment_id: str,
        jobs: List[JobListing],
        profile: UserProfile,
    ) -> ExperimentResult:
        """
        Run an A/B test experiment.

        Args:
            experiment_id: Experiment ID
            jobs: Job listings to test with
            profile: User profile

        Returns:
            ExperimentResult with comparison
        """
        # Load experiment config
        filepath = self.storage_dir / f"{experiment_id}.json"
        with open(filepath, "r") as f:
            experiment_data = json.load(f)

        config = experiment_data["config"]

        # Update status
        experiment_data["status"] = ExperimentStatus.RUNNING.value
        experiment_data["started_at"] = datetime.now().isoformat()

        with open(filepath, "w") as f:
            json.dump(experiment_data, f, indent=2, default=str)

        # Run variant A
        results_a = self._run_variant(
            jobs=jobs,
            profile=profile,
            weights=config["weights_a"],
            min_score=config["min_score_a"],
            variant_name="A",
        )

        # Run variant B
        results_b = self._run_variant(
            jobs=jobs,
            profile=profile,
            weights=config["weights_b"],
            min_score=config["min_score_b"],
            variant_name="B",
        )

        # Compare results
        comparison = self._compare_variants(results_a, results_b)

        result = ExperimentResult(
            experiment_name=experiment_data["name"],
            variant_a=results_a,
            variant_b=results_b,
            winner=comparison["winner"],
            significance=comparison["significance"],
            timestamp=datetime.now(),
            metadata={
                "experiment_id": experiment_id,
                "comparison": comparison,
            },
        )

        # Save results
        self._save_results(experiment_id, result)

        # Update experiment status
        experiment_data["status"] = ExperimentStatus.COMPLETED.value
        experiment_data["completed_at"] = datetime.now().isoformat()
        experiment_data["result"] = {
            "winner": result.winner,
            "significance": result.significance,
        }

        with open(filepath, "w") as f:
            json.dump(experiment_data, f, indent=2, default=str)

        self.logger.info(
            f"Experiment {experiment_id} complete: Winner={result.winner}, "
            f"Significance={result.significance:.2f}"
        )

        return result

    def _run_variant(
        self,
        jobs: List[JobListing],
        profile: UserProfile,
        weights: Dict[str, int],
        min_score: int,
        variant_name: str,
    ) -> Dict[str, Any]:
        """Run a single variant."""
        # Create matcher with custom weights
        matcher = JobMatcher()

        # Temporarily modify weights (this would need to be implemented in JobMatcher)
        # For now, we'll score with default and adjust

        scored_jobs = []
        for job in jobs:
            score = matcher.match_and_score(job, profile)
            if score.total_score >= min_score:
                scored_jobs.append((job, score))

        # Calculate metrics
        total_scored = len(scored_jobs)
        avg_score = (
            sum(s.total_score for _, s in scored_jobs) / total_scored
            if total_scored > 0
            else 0
        )

        return {
            "variant": variant_name,
            "weights": weights,
            "min_score": min_score,
            "total_jobs": len(jobs),
            "jobs_above_threshold": total_scored,
            "avg_score": avg_score,
            "pass_rate": total_scored / len(jobs) if jobs else 0,
        }

    def _compare_variants(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two variants and determine winner."""
        # Primary metric: pass rate (jobs above threshold / total jobs)
        pass_rate_a = variant_a["pass_rate"]
        pass_rate_b = variant_b["pass_rate"]

        # Secondary metrics
        avg_score_a = variant_a["avg_score"]
        avg_score_b = variant_b["avg_score"]

        # Calculate significance (simple difference-based)
        rate_diff = abs(pass_rate_a - pass_rate_b)
        significance = min(rate_diff * 10, 1.0)  # Convert to 0-1 scale

        # Determine winner
        winner = None
        if pass_rate_a > pass_rate_b:
            winner = "A"
        elif pass_rate_b > pass_rate_a:
            winner = "B"
        # If equal, check avg score
        elif avg_score_a > avg_score_b:
            winner = "A"
        elif avg_score_b > avg_score_a:
            winner = "B"

        # If still equal, it's a tie
        if pass_rate_a == pass_rate_b and avg_score_a == avg_score_b:
            winner = None
            significance = 0.0

        return {
            "winner": winner,
            "significance": significance,
            "metrics": {
                "pass_rate_diff": pass_rate_a - pass_rate_b,
                "avg_score_diff": avg_score_a - avg_score_b,
                "winner_pass_rate": max(pass_rate_a, pass_rate_b),
                "winner_avg_score": max(avg_score_a, avg_score_b),
            },
        }

    def _save_results(self, experiment_id: str, result: ExperimentResult) -> None:
        """Save experiment results."""
        filepath = self.storage_dir / f"{experiment_id}_result.json"

        result_data = {
            "experiment_name": result.experiment_name,
            "variant_a": result.variant_a,
            "variant_b": result.variant_b,
            "winner": result.winner,
            "significance": result.significance,
            "timestamp": result.timestamp.isoformat(),
            "metadata": result.metadata,
        }

        with open(filepath, "w") as f:
            json.dump(result_data, f, indent=2, default=str)

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get experiment details."""
        filepath = self.storage_dir / f"{experiment_id}.json"

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List all experiments."""
        experiments = []

        for filepath in self.storage_dir.glob("*.json"):
            if "_result" in filepath.name:
                continue

            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                if status is None or data["status"] == status.value:
                    experiments.append(data)
            except Exception:
                continue

        return sorted(experiments, key=lambda x: x["created_at"], reverse=True)

    def get_best_config(self) -> Optional[Dict[str, Any]]:
        """Get the best scoring configuration from all experiments."""
        results = []

        for filepath in self.storage_dir.glob("*_result.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    results.append(data)
            except Exception:
                continue

        if not results:
            return None

        # Find result with highest significance
        best = max(results, key=lambda r: r["significance"])

        if best["winner"] == "A":
            return {
                "experiment": best["experiment_name"],
                "weights": best["variant_a"]["weights"],
                "min_score": best["variant_a"]["min_score"],
                "significance": best["significance"],
            }
        elif best["winner"] == "B":
            return {
                "experiment": best["experiment_name"],
                "weights": best["variant_b"]["weights"],
                "min_score": best["variant_b"]["min_score"],
                "significance": best["significance"],
            }
        else:
            return None

    def _generate_experiment_id(self, name: str) -> str:
        """Generate unique experiment ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_input = f"{name}_{timestamp}".encode()
        hash_suffix = hashlib.md5(hash_input).hexdigest()[:8]
        return f"exp_{timestamp}_{hash_suffix}"


class ScoringExperimentBuilder:
    """Builder for creating scoring experiments."""

    def __init__(self):
        self.experiments: List[ExperimentConfig] = []

    def add_experiment(
        self,
        name: str,
        description: str,
        keywords_weight_a: int = 30,
        skills_weight_a: int = 40,
        experience_weight_a: int = 20,
        location_weight_a: int = 10,
        keywords_weight_b: int = 30,
        skills_weight_b: int = 40,
        experience_weight_b: int = 20,
        location_weight_b: int = 10,
        min_score_a: int = 60,
        min_score_b: int = 60,
    ) -> "ScoringExperimentBuilder":
        """Add an experiment to compare."""
        config = ExperimentConfig(
            name=name,
            description=description,
            weights_a={
                "keywords": keywords_weight_a,
                "skills": skills_weight_a,
                "experience": experience_weight_a,
                "location": location_weight_a,
            },
            weights_b={
                "keywords": keywords_weight_b,
                "skills": skills_weight_b,
                "experience": experience_weight_b,
                "location": location_weight_b,
            },
            min_score_a=min_score_a,
            min_score_b=min_score_b,
        )

        self.experiments.append(config)
        return self

    def build(self) -> List[ExperimentConfig]:
        """Build all experiments."""
        return self.experiments


# Preset experiments
def get_preset_experiments() -> List[ExperimentConfig]:
    """Get common preset experiments."""
    return [
        ExperimentConfig(
            name="skills_vs_keywords",
            description="Test if weighting skills higher than keywords improves outcomes",
            weights_a={"keywords": 30, "skills": 40, "experience": 20, "location": 10},
            weights_b={"keywords": 40, "skills": 30, "experience": 20, "location": 10},
        ),
        ExperimentConfig(
            name="lower_threshold",
            description="Test if lower score threshold increases applications",
            weights_a={"keywords": 30, "skills": 40, "experience": 20, "location": 10},
            weights_b={"keywords": 30, "skills": 40, "experience": 20, "location": 10},
            min_score_a=60,
            min_score_b=50,
        ),
        ExperimentConfig(
            name="experience_focus",
            description="Test if weighting experience higher improves quality",
            weights_a={"keywords": 30, "skills": 40, "experience": 20, "location": 10},
            weights_b={"keywords": 20, "skills": 30, "experience": 40, "location": 10},
        ),
    ]


# Convenience functions
def run_scoring_experiment(
    name: str,
    weights_a: Dict[str, int],
    weights_b: Dict[str, int],
    jobs: List[JobListing],
    profile: UserProfile,
) -> ExperimentResult:
    """Run a quick scoring A/B test."""
    tester = ABTester()

    config = ExperimentConfig(
        name=name,
        description=f"Compare {weights_a} vs {weights_b}",
        weights_a=weights_a,
        weights_b=weights_b,
    )

    experiment_id = tester.create_experiment(config)
    return tester.run_experiment(experiment_id, jobs, profile)
