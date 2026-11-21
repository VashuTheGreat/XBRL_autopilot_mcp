"""Data models and schemas for MCA XBRL Validation Engine."""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ValidationRequest(BaseModel):
    """Request payload for XBRL XML validation."""
    xml: str = Field(..., description="The XBRL instance XML document content to validate.")
    taxonomy: str = Field(
        default="indas",
        description="Taxonomy type: 'indas' (Ind-AS 2017) or 'ci' / 'cni' (C&I 2016)."
    )
    strict: bool = Field(
        default=True,
        description="Whether to perform strict statutory validation gates."
    )


class ValidationErrorItem(BaseModel):
    """Detailed validation error/warning item."""
    code: str = Field(..., description="Machine-readable error code (e.g. BS_OUT_OF_BALANCE, INVALID_DIN)")
    gate: str = Field(..., description="The validation gate that flagged this error")
    category: str = Field(..., description="Category: SCHEMA, CONTEXT, MANDATORY, CALCULATION, GOVERNANCE, TEXT_BLOCK, BUSINESS_RULE")
    severity: str = Field(default="ERROR", description="Severity level: CRITICAL, ERROR, WARNING, INFO")
    concept: Optional[str] = Field(default=None, description="Affected XBRL concept QName if applicable")
    context_ref: Optional[str] = Field(default=None, description="Context identifier if applicable")
    line_number: Optional[int] = Field(default=None, description="Line number in XML where issue occurs if detectable")
    message: str = Field(..., description="Human-readable description of the error")
    expected: Optional[Any] = Field(default=None, description="Expected value or format")
    actual: Optional[Any] = Field(default=None, description="Reported or actual value")
    diff: Optional[float] = Field(default=None, description="Numeric discrepancy in calculations if applicable")
    claude_fix_action: str = Field(..., description="Clear, concrete instructions for Claude on how to edit and fix the XML")


class ValidationSummary(BaseModel):
    """Summary of validation results."""
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    gates_evaluated: int = 0
    gates_passed: int = 0
    gates_failed: int = 0
    facts_evaluated: int = 0
    contexts_count: int = 0


class ValidationResponse(BaseModel):
    """Full validation response returned to Claude or the API client."""
    valid: bool = Field(..., description="True if no CRITICAL or ERROR severity issues exist; False otherwise.")
    taxonomy: str = Field(..., description="Validated taxonomy ('indas' or 'ci')")
    summary: ValidationSummary
    errors: List[ValidationErrorItem] = Field(default_factory=list, description="Blocking errors that reject filing")
    warnings: List[ValidationErrorItem] = Field(default_factory=list, description="Non-blocking statutory warnings")
    passed_checks: List[str] = Field(default_factory=list, description="List of validation checks that passed successfully")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata extracted from instance (CIN, period, etc.)")


class ExplainErrorRequest(BaseModel):
    """Request to explain a raw MCA or Xerces validation tool error message."""
    error_message: str = Field(..., description="Raw error string from MCA Tool, Xerces, or Webtel")


class ExplainErrorResponse(BaseModel):
    """Structured explanation of the error with Claude fix guidelines."""
    matched_code: Optional[str] = None
    title: str
    meaning: str
    likely_cause: str
    element: Optional[str] = None
    claude_fix_action: str
