from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(
        description="The investigation claim being reviewed."
    )

    verdict: Literal[
        "supported",
        "partially_supported",
        "unsupported",
        "unverifiable"
    ] = Field(
        description="How strongly the supplied evidence supports the claim."
    )

    evidence_ids: list[str] = Field(
        description="Evidence IDs directly relevant to this assessment."
    )

    explanation: str = Field(
        description="A concise explanation grounded in the supplied records."
    )


class ForensicReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: Literal[
        "approved",
        "needs_revision",
        "inconclusive"
    ] = Field(
        description="Overall result of the independent forensic review."
    )

    overall_assessment: str = Field(
        description="Summary of the investigation's reliability and quality."
    )

    claim_assessments: list[ClaimAssessment] = Field(
        description="Evidence-based assessments of important investigation claims."
    )

    hypothesis_issues: list[str] = Field(
        description="Unsupported, contradictory, or weakly supported hypotheses."
    )

    timeline_issues: list[str] = Field(
        description="Timestamp conflicts, ordering problems, or missing time information."
    )

    missing_evidence: list[str] = Field(
        description="Additional evidence needed to validate important conclusions."
    )

    recommendations: list[str] = Field(
        description="Specific, non-destructive steps to improve the investigation."
    )

    limitations: list[str] = Field(
        description="Important limitations and uncertainties in the supplied data."
    )

    human_review_required: bool = Field(
        description="Whether an investigator must review the conclusions before relying on them."
    )