"""MCP Server for MCA XBRL Validation.

Exposes tools to Claude via the Model Context Protocol (FastMCP):
1. validate_mca_xbrl
2. explain_mca_error
3. get_mca_filing_checklist
"""

import json
from typing import Dict, Any, Optional
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP
from app.validator import MCAValidator
from app.mca_error_rules import explain_mca_error as explain_err_func

# Initialize FastMCP Server
mcp = FastMCP("mca-validation-mcp")


@mcp.tool()
def validate_mca_xbrl(xml_content: str, taxonomy: str = "indas") -> str:
    """Validates an MCA AOC-4 XBRL XML instance document for Ind-AS or C&I.
    
    Args:
        xml_content: The full XBRL instance XML string to validate.
        taxonomy: Taxonomy standard: 'indas' (Ind-AS 2017) or 'ci' / 'cni' (C&I 2016).
        
    Returns:
        Structured JSON report containing validation status (PASS/FAIL), errors list
        with exact concepts, diffs, line numbers, and actionable Claude fix instructions.
    """
    try:
        validator = MCAValidator(taxonomy=taxonomy)
        res = validator.validate(xml_content)
        return json.dumps(res.model_dump(), indent=2)
    except Exception as e:
        return json.dumps({
            "valid": False,
            "taxonomy": taxonomy,
            "summary": {
                "total_errors": 1,
                "total_warnings": 0,
                "gates_evaluated": 0,
                "gates_passed": 0,
                "gates_failed": 1
            },
            "errors": [{
                "code": "VALIDATOR_EXCEPTION",
                "gate": "Execution",
                "category": "INTERNAL",
                "severity": "CRITICAL",
                "message": f"Validator encountered an internal exception: {str(e)}",
                "claude_fix_action": "Check XML well-formedness and parameters."
            }],
            "warnings": [],
            "passed_checks": []
        }, indent=2)


@mcp.tool()
def explain_mca_error(error_message: str) -> str:
    """Translates cryptic Xerces XML schema or MCA Validation Tool error messages into plain English with Claude fix steps.
    
    Args:
        error_message: Raw error text from MCA Tool, Xerces ('cvc-...'), or Webtel.
        
    Returns:
        Structured JSON explanation with root cause and actionable fix instructions.
    """
    res = explain_err_func(error_message)
    return json.dumps(res.model_dump(), indent=2)


@mcp.tool()
def get_mca_filing_checklist(taxonomy: str = "indas") -> str:
    """Returns the MCA statutory filing checklist and mandatory concepts for Claude.
    
    Args:
        taxonomy: 'indas' or 'ci'
        
    Returns:
        Checklist of mandatory tags, DIN requirements, Balance Sheet balancing equations, and text block HTML rules.
    """
    is_ind_as = "ind" in taxonomy.lower()
    checklist = {
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
            "in-ca:WhetherCompanyHasSubsidiaryCompanies ('true' / 'false' or 'Yes' / 'No')"
        ],
        "statutory_signatories_rule": "Section 134(1) Companies Act: Minimum 2 Director signatories with valid 8-digit numeric DINs.",
        "financial_balance_sheet_rule": "Total Assets == Total Equity and Liabilities (+/- 1.0 INR tolerance).",
        "statement_roots": [
            "ind-as:Assets" if is_ind_as else "in-gaap:Assets",
            "ind-as:EquityAndLiabilities" if is_ind_as else "in-gaap:EquityAndLiabilities"
        ],
        "currency_and_units": "Monetary elements must have unitRef='INR' with iso4217:INR. No scale factors.",
        "text_block_html_rules": [
            "Allowed tags: div, span, p, br, table, tr, td, thead, tbody, tfoot, th.",
            "Forbidden tags: colgroup, col, caption, script, img, style, iframe.",
            "Allowed attributes: ONLY class attribute. No inline styles, colspan, rowspan, border, or align.",
            "Allowed entities: &nbsp;, &amp;, &lt;, &gt;."
        ]
    }
    return json.dumps(checklist, indent=2)


if __name__ == "__main__":
    mcp.run()
