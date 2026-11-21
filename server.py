"""FastMCP 4 Server for Statutory MCA AOC-4 XBRL Validation.

Exposes tools, resources, and prompts to Claude & AI Agents using the standalone FastMCP framework:
- Tools: validate_mca_xbrl, explain_mca_error, get_mca_filing_checklist
- Resources: checklist://mca/{taxonomy}, rules://mca/html-schema
- Prompts: mca_filing_review
"""

import os
import sys
import json
from pathlib import Path
from typing import Literal
from pydantic import Field

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, ResourceError
from app.validator import MCAValidator
from app.mca_error_rules import explain_mca_error as explain_err_func
from app.data_loader import TaxonomyDataLoader

# Initialize FastMCP Server
mcp = FastMCP(
    "mca-validation-mcp",
    instructions=(
        "Statutory MCA AOC-4 XBRL Validation Server. Validates Ind-AS (2017) and C&I (2016) "
        "XBRL instances against official MCA Validation Tool v5.1 rules and returns structured "
        "errors with exact tags, diffs, line numbers, and actionable Claude self-correction instructions."
    )
)


@mcp.tool(
    name="validate_mca_xbrl",
    description="Validates an MCA AOC-4 XBRL XML instance document for Ind-AS or C&I against statutory MCA rules."
)
def validate_mca_xbrl(
    xml_content: str = Field(description="The full XBRL instance XML string to validate."),
    taxonomy: Literal["indas", "ci"] = Field(
        default="indas",
        description="Taxonomy standard: 'indas' (Ind-AS 2017) or 'ci' (C&I 2016)."
    ),
    strict: bool = Field(
        default=True,
        description="Enforce strict statutory checking including calculation linkbases and non-negatives."
    )
) -> str:
    """Validates an MCA AOC-4 XBRL XML instance document for Ind-AS or C&I.

    Returns:
        Structured JSON report containing validation status (valid: true/false), errors list
        with exact concepts, diffs, line numbers, and actionable Claude fix instructions.
    """
    if not xml_content or not xml_content.strip():
        raise ToolError("XML content cannot be empty.")

    try:
        validator = MCAValidator(taxonomy=taxonomy, strict=strict)
        res = validator.validate(xml_content)
        return json.dumps(res.model_dump(), indent=2)
    except Exception as e:
        raise ToolError(f"Validation engine encountered an error: {str(e)}")


@mcp.tool(
    name="explain_mca_error",
    description="Translates cryptic Xerces XML schema or MCA Validation Tool error messages into plain English with Claude fix steps."
)
def explain_mca_error(
    error_message: str = Field(
        description="Raw error text from MCA Tool, Xerces ('cvc-...'), or Webtel."
    )
) -> str:
    """Translates raw Xerces or MCA errors into plain English with actionable fix instructions."""
    if not error_message or not error_message.strip():
        raise ToolError("Error message cannot be empty.")

    try:
        res = explain_err_func(error_message)
        return json.dumps(res.model_dump(), indent=2)
    except Exception as e:
        raise ToolError(f"Error parsing failure: {str(e)}")


@mcp.tool(
    name="get_mca_filing_checklist",
    description="Returns the MCA statutory filing checklist and mandatory concepts for Ind-AS or C&I."
)
def get_mca_filing_checklist(
    taxonomy: Literal["indas", "ci"] = Field(
        default="indas",
        description="Statutory taxonomy standard ('indas' or 'ci')."
    )
) -> str:
    """Returns the MCA statutory filing checklist and mandatory concepts for Claude."""
    checklist = _build_checklist(taxonomy)
    return json.dumps(checklist, indent=2)


@mcp.resource("checklist://mca/{taxonomy}")
def mca_checklist_resource(taxonomy: str) -> str:
    """Provides statutory filing checklist and mandatory concept rules for the requested taxonomy."""
    norm = taxonomy.lower().strip()
    if norm not in ("indas", "ci"):
        raise ResourceError(f"Unsupported taxonomy '{taxonomy}'. Expected 'indas' or 'ci'.")
    return json.dumps(_build_checklist(norm), indent=2)


@mcp.resource("rules://mca/html-schema")
def mca_html_schema_resource() -> str:
    """Official MCA HTML schema and permitted formatting tags for text blocks."""
    return json.dumps({
        "namespace": "http://www.mca.gov.in/XBRL/HTML",
        "allowed_tags": [
            "html", "body", "p", "div", "span", "table", "thead", "tbody", "tr", "th", "td",
            "b", "i", "u", "strong", "em", "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li", "br", "hr"
        ],
        "strictly_forbidden_tags": ["script", "iframe", "embed", "object", "form", "input", "button", "link"],
        "rules": [
            "All tags must be properly nested and closed (<br/>, <hr/>).",
            "Inline styles should avoid executable javascript expressions.",
            "Tables must have matching opening and closing structure."
        ]
    }, indent=2)


@mcp.prompt(
    name="mca_filing_review",
    description="Standard prompt template for reviewing and auditing an MCA AOC-4 XBRL instance document."
)
def mca_filing_review(
    company_cin: str = Field(description="21-character Corporate Identity Number of the company."),
    taxonomy: Literal["indas", "ci"] = Field(default="indas", description="Taxonomy standard ('indas' or 'ci').")
) -> str:
    """Generates a comprehensive review prompt for an MCA AOC-4 filing."""
    return (
        f"You are the Lead MCA Statutory Filing Auditor. Review the AOC-4 XBRL filing for CIN: {company_cin} "
        f"under the {taxonomy.upper()} taxonomy standard.\n\n"
        "Follow these strict statutory verification steps:\n"
        "1. Verify that CIN matches the 21-character alphanumeric format: [LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\n"
        "2. Ensure at least 2 Director signatories are present with valid 8-digit DINs as per Section 134(1).\n"
        "3. Confirm that Total Assets exactly equals Total Equity and Liabilities (diff <= 1.0 INR).\n"
        "4. Validate all calculation linkbase rollups and verify all non-negative concepts have positive values.\n"
        "5. Check all text blocks against the official MCA HTML schema (no script or iframe tags).\n\n"
        "Run the `validate_mca_xbrl` tool with the XBRL instance XML and report any statutory errors."
    )


def _build_checklist(taxonomy: str) -> dict:
    """Helper to compile statutory checklist."""
    is_ind_as = "ind" in taxonomy.lower()
    return {
        "taxonomy": "indas" if is_ind_as else "ci",
        "mandatory_company_tags": [
            "in-ca:CorporateIdentityNumber (21-char CIN)",
            "in-ca:NameOfCompany",
            "in-ca:PermanentAccountNumberOfEntity (10-char PAN)",
            "in-ca:AddressOfRegisteredOfficeOfCompany",
            "in-ca:DateOfStartOfReportingPeriod (YYYY-MM-DD)",
            "in-ca:DateOfEndOfReportingPeriod (YYYY-MM-DD)",
            "in-ca:DateOfBoardMeetingWhenFinalAccountsWereApproved (YYYY-MM-DD)",
            "in-ca:NatureOfReportStandaloneConsolidated ('Standalone' or 'Consolidated')",
            "in-ca:DescriptionOfPresentationCurrency ('INR')",
            "in-ca:LevelOfRoundingUsedInFinancialStatements ('Exact', 'Thousands', 'Lakhs', 'Crores')",
            "in-ca:WhetherCompanyIsSubsidiaryCompany ('true' / 'false' or 'Yes' / 'No')",
            "in-ca:TypeOfIndustry ('Commercial & Industrial')",
            "in-ca:ContentOfReport ('Financial Statements and other reports')"
        ],
        "mandatory_signatory_requirements": {
            "minimum_director_count": 2,
            "din_format": "8 digits numeric (e.g., 00123456)",
            "section": "Section 134(1) of Companies Act, 2013"
        },
        "balance_sheet_equation": (
            "TotalAssets == TotalEquityAndLiabilities (diff <= 1.0 INR)"
            if is_ind_as else
            "Assets == EquityAndLiabilities (diff <= 1.0 INR)"
        ),
        "text_block_html_rule": "Must comply with http://www.mca.gov.in/XBRL/HTML (No <script>, <style>, <iframe>)"
    }


# ASGI application instance for HTTP deployment / FastMCP Gateway
app = mcp.http_app()

if __name__ == "__main__":
    # Supports running via: python server.py or fastmcp run
    mcp.run()
