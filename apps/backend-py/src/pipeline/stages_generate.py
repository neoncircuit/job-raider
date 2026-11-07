"""
Job Raider - Generate Stage

This module defines the stage that writes the resumes and cover letters.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing
from .stage_base import StageBase, StageResult


class GenerateStages(StageBase):
    """Stage that writes the resumes and cover letters."""

    def stage_generate_resumes(
        self,
        selected_listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 8: Generate tailored resumes for selected jobs.

        Args:
            selected_listings: User-selected job listings

        Returns:
            StageResult with generated resumes
        """
        stage_name = "generate_resumes"
        start_time = datetime.now()

        try:
            self.logger.info(f"Generating resumes for {len(selected_listings)} jobs")

            generated: List[Dict[str, Any]] = []
            validation_results = []

            for job in selected_listings:
                self.logger.info(f"Generating resume for {job.title} at {job.company}")

                try:
                    # Stage 1: Selection (small model)
                    selection_output = self.resume_selector.select(
                        job=job,
                        profile=self.context.user_profile,
                    )

                    # Stage 2: Write resume (large model)
                    generated_resume = self.resume_writer.write(
                        job=job,
                        profile=self.context.user_profile,
                        selection=selection_output,
                    )

                    # Stage 3: Validate
                    validation = self.resume_validator.validate(
                        resume=generated_resume,
                        job=job,
                        profile=self.context.user_profile,
                        selection=selection_output,
                    )

                    validation_results.append((job, validation))

                    if not validation.is_valid:
                        self.logger.warning(
                            f"Validation failed for {job.title}: {validation.issues}"
                        )
                        continue

                    # Stage 2b: Cover letter through the same service as the
                    # app: write, validate, and one grounding rewrite.
                    letter = self._generate_cover_letter(job, selection_output)

                    # Stage 4: Format and save
                    resume_dir = self.context.results_dir / "resumes"
                    resume_dir.mkdir(parents=True, exist_ok=True)

                    self.resume_formatter.output_dir = resume_dir
                    formatted = self.resume_formatter.format_resume(
                        resume=generated_resume,
                        filename=str(job.job_id),
                        formats=["pdf", "docx"],
                    )
                    if not formatted.success:
                        raise RuntimeError(
                            f"Resume formatting failed: {formatted.errors}"
                        )
                    pdf_path = formatted.pdf_path
                    docx_path = formatted.docx_path

                    # Save the cover letter only when it has no hard-fail
                    # grounding issue after the repair rewrite.
                    cover_letter_path: Optional[str] = None
                    if letter["status"] == "saved":
                        cover_letter_dir = self.context.results_dir / "cover_letters"
                        cover_letter_dir.mkdir(parents=True, exist_ok=True)
                        letter_file = cover_letter_dir / f"{job.job_id}.txt"
                        letter_file.write_text(letter["content"], encoding="utf-8")
                        cover_letter_path = str(letter_file)

                    generated.append(
                        {
                            "job": job,
                            "resume": generated_resume,
                            "cover_letter": letter["content"],
                            "pdf_path": str(pdf_path),
                            "docx_path": str(docx_path),
                            "cover_letter_path": cover_letter_path,
                            "validation": validation,
                            "cover_letter_validation": letter["validation"],
                            "cover_letter_status": letter["status"],
                            "cover_letter_issues": letter["issues"],
                            "cover_letter_provider_used": letter.get("provider_used"),
                        }
                    )

                    self.logger.info(
                        f"Resume generated: {pdf_path} (validation: {validation.overall_score}/100)"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to generate resume for {job.title}: {str(e)}"
                    )
                    continue

            # Calculate validation statistics
            scores = [r["validation"].overall_score for r in generated]

            def _is_cloud_provider(provider: Any) -> bool:
                """Return True when a document used a non-Ollama provider.

                Args:
                    provider: Provider string from an LLM response, or None.

                Returns:
                    True when provider is set and is not ``ollama``.
                """
                return bool(provider) and str(provider).lower() != "ollama"

            cloud_documents = sum(
                1
                for r in generated
                if _is_cloud_provider(getattr(r["resume"], "provider_used", None))
            ) + sum(
                1
                for r in generated
                if _is_cloud_provider(r.get("cover_letter_provider_used"))
            )
            metadata = {
                "attempted_count": len(selected_listings),
                "generated_count": len(generated),
                "validation_failed": len(selected_listings) - len(generated),
                "avg_validation_score": sum(scores) / len(scores) if scores else 0,
                "all_valid": all(r["validation"].is_valid for r in generated),
                "cover_letters_saved": sum(
                    1 for r in generated if r["cover_letter_status"] == "saved"
                ),
                "cover_letters_needs_review": sum(
                    1 for r in generated if r["cover_letter_status"] == "needs_review"
                ),
                "cover_letters_failed": sum(
                    1 for r in generated if r["cover_letter_status"] == "error"
                ),
                "cloud_documents": cloud_documents,
            }

            self.logger.info(
                f"Resume generation complete: {len(generated)}/{len(selected_listings)} successful"
            )

            # No selected jobs is not an error; every selected job failing is.
            success = not selected_listings or len(generated) > 0
            return StageResult(
                stage_name=stage_name,
                success=success,
                data=generated,
                metadata=metadata,
                timestamp=start_time,
                error_message=(
                    None
                    if success
                    else (
                        "No resume was generated for the "
                        f"{len(selected_listings)} selected jobs"
                    )
                ),
            )

        except Exception as e:
            self.logger.error(f"Resume generation stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )
