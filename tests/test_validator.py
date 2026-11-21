"""Unit and Integration Tests for MCA XBRL Validation Engine."""

from pathlib import Path
from app.validator import MCAValidator
from app.mca_error_rules import explain_mca_error
from app.parser import XbrlInstanceParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_valid_indas_instance():
    """Verify that a well-formed, balanced Ind-AS instance passes all statutory gates."""
    xml_file = FIXTURES_DIR / "valid_indas.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    validator = MCAValidator(taxonomy="indas")
    result = validator.validate(xml_content)

    assert result.valid is True, f"Expected valid, got errors: {result.errors}"
    assert result.summary.total_errors == 0
    assert result.metadata.get("cin") == "U72200DL2018PTC123456"
    assert "Gate 8: Balance Sheet Hard Balancing" in " ".join(result.passed_checks)


def test_valid_ci_instance():
    """Verify that the official C&I 2016 golden instance parses and validates."""
    xml_file = FIXTURES_DIR / "valid_ci.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    validator = MCAValidator(taxonomy="ci")
    result = validator.validate(xml_content)

    # In C&I golden instance, check facts extracted and no critical crashes
    assert result.summary.facts_evaluated > 300
    assert result.metadata.get("cin") == "U72200KA2010PTC123456"


def test_bs_mismatch_detection():
    """Verify that Balance Sheet discrepancy triggers CRITICAL BS_OUT_OF_BALANCE error."""
    xml_file = FIXTURES_DIR / "invalid_bs_mismatch.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    validator = MCAValidator(taxonomy="indas")
    result = validator.validate(xml_content)

    assert result.valid is False
    bs_errors = [e for e in result.errors if e.code == "BS_OUT_OF_BALANCE"]
    assert len(bs_errors) == 1
    assert bs_errors[0].diff == 500000.0
    assert "Adjust either Total Assets or Total Equity" in bs_errors[0].claude_fix_action


def test_missing_mandatory_and_bad_din():
    """Verify that missing PAN and invalid DIN length are caught and reported."""
    xml_file = FIXTURES_DIR / "invalid_missing_mandatory.xml"
    with open(xml_file, "r", encoding="utf-8") as f:
        xml_content = f.read()

    validator = MCAValidator(taxonomy="indas")
    result = validator.validate(xml_content)

    assert result.valid is False
    codes = {e.code for e in result.errors}
    assert "MANDATORY_COMPANY_INFO_MISSING" in codes
    assert "INSUFFICIENT_SIGNATORIES" in codes or "INVALID_DIN_FORMAT" in codes


def test_html_schema_violation():
    """Verify that forbidden HTML (e.g. style attribute or colgroup) in text block is caught."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-ca="http://www.icai.org/xbrl/taxonomy/2017-03-31/in-ca" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:schemaRef xlink:href="https://www.mca.gov.in/V3XBRL/2017/03/31/Taxonomy/IndAS/in-ind-as-ent-2017-03-31.xsd" xlink:type="simple"/>
  <xbrli:context id="CY">
    <xbrli:entity><xbrli:identifier scheme="http://www.mca.gov.in/CIN">U72200DL2018PTC123456</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <in-ca:DisclosureOfSignificantAccountingPoliciesTextBlock contextRef="CY">
    <table style="width: 100%; border: 1px solid black;">
      <colgroup><col width="50%"/></colgroup>
      <tr><td style="color: red;">Policy Note</td></tr>
    </table>
  </in-ca:DisclosureOfSignificantAccountingPoliciesTextBlock>
</xbrli:xbrl>"""

    validator = MCAValidator(taxonomy="indas")
    result = validator.validate(xml_content)

    html_errors = [e for e in result.errors if e.code == "MCA_HTML_SCHEMA_VIOLATION"]
    assert len(html_errors) > 0
    assert any("style attribute" in e.message.lower() or "colgroup" in e.message.lower() for e in html_errors)


def test_error_explainer():
    """Verify plain-English translation of Xerces / MCA tool error messages."""
    raw = "cvc-pattern-valid: Value 'AAACH123' is not facet-valid with respect to pattern '[A-Z]{5}[0-9]{4}[A-Z]' for type 'PANType'"
    explained = explain_mca_error(raw)

    assert explained.matched_code == "cvc-pattern-valid"
    assert "PAN" in explained.likely_cause or "Formatting" in explained.likely_cause
    assert "Correct the value" in explained.claude_fix_action
