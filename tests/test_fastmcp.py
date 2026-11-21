"""Tests for FastMCP Server using in-process FastMCP Client.

Follows the FastMCP 4 testing conventions and the fastmcp-server skill guidelines:
1. Verify tool discovery and schemas.
2. Verify representative operations (validate_mca_xbrl, explain_mca_error, get_mca_filing_checklist).
3. Verify meaningful failures (ToolError on empty or invalid input).
4. Verify resource reading (checklist://mca/indas, rules://mca/html-schema).
5. Verify prompt retrieval (mca_filing_review).
"""

import pytest
import json
from pathlib import Path
from fastmcp import Client
from server import mcp

VALID_INDAS_XML = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:in-ca="http://www.mca.gov.in/XBRL/2017/02/in-ca"
            xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:link="http://www.xbrl.org/2003/linkbase"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <link:schemaRef xlink:type="simple" xlink:href="http://www.mca.gov.in/XBRL/2017/02/in-ca/in-ca-2017-02-28.xsd" />
  <xbrli:context id="FY_2023_24">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.mca.gov.in/CIN">U12345DL2020PTC123456</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2023-04-01</xbrli:startDate>
      <xbrli:endDate>2024-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="AsOf_2024_03_31">
    <xbrli:entity>
      <xbrli:identifier scheme="http://www.mca.gov.in/CIN">U12345DL2020PTC123456</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2024-03-31</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:unit id="INR">
    <xbrli:measure>iso4217:INR</xbrli:measure>
  </xbrli:unit>
  <in-ca:CorporateIdentityNumber contextRef="FY_2023_24">U12345DL2020PTC123456</in-ca:CorporateIdentityNumber>
  <in-ca:NameOfCompany contextRef="FY_2023_24">ACME TEST PRIVATE LIMITED</in-ca:NameOfCompany>
  <in-ca:PermanentAccountNumberOfEntity contextRef="FY_2023_24">AAACA1234A</in-ca:PermanentAccountNumberOfEntity>
  <in-ca:AddressOfRegisteredOfficeOfCompany contextRef="FY_2023_24">New Delhi, India</in-ca:AddressOfRegisteredOfficeOfCompany>
  <in-ca:DateOfStartOfReportingPeriod contextRef="FY_2023_24">2023-04-01</in-ca:DateOfStartOfReportingPeriod>
  <in-ca:DateOfEndOfReportingPeriod contextRef="FY_2023_24">2024-03-31</in-ca:DateOfEndOfReportingPeriod>
  <in-ca:NatureOfReportStandaloneConsolidated contextRef="FY_2023_24">Standalone</in-ca:NatureOfReportStandaloneConsolidated>
  <in-ca:DescriptionOfPresentationCurrency contextRef="FY_2023_24">INR</in-ca:DescriptionOfPresentationCurrency>
  <in-ca:LevelOfRoundingUsedInFinancialStatements contextRef="FY_2023_24">Exact</in-ca:LevelOfRoundingUsedInFinancialStatements>
  <in-ca:DateOfBoardMeetingWhenFinalAccountsWereApproved contextRef="FY_2023_24">2024-08-15</in-ca:DateOfBoardMeetingWhenFinalAccountsWereApproved>
  <in-ca:WhetherCompanyIsSubsidiaryCompany contextRef="FY_2023_24">false</in-ca:WhetherCompanyIsSubsidiaryCompany>
  <in-ca:TypeOfIndustry contextRef="FY_2023_24">Commercial &amp; Industrial</in-ca:TypeOfIndustry>
  <in-ca:ContentOfReport contextRef="FY_2023_24">Financial Statements and other reports</in-ca:ContentOfReport>
  <in-ca:WhetherCompanyIsMaintainingBooksOfAccountAndOtherRelevantBooksAndPapersInElectronicForm contextRef="FY_2023_24">true</in-ca:WhetherCompanyIsMaintainingBooksOfAccountAndOtherRelevantBooksAndPapersInElectronicForm>
  <in-ca:DirectorIdentificationNumberOfSignatory contextRef="FY_2023_24">00012345</in-ca:DirectorIdentificationNumberOfSignatory>
  <in-ca:DirectorIdentificationNumberOfSignatory contextRef="FY_2023_24">00067890</in-ca:DirectorIdentificationNumberOfSignatory>
  <in-ca:Assets unitRef="INR" contextRef="AsOf_2024_03_31" decimals="2">1000000.00</in-ca:Assets>
  <in-ca:EquityAndLiabilities unitRef="INR" contextRef="AsOf_2024_03_31" decimals="2">1000000.00</in-ca:EquityAndLiabilities>
</xbrli:xbrl>"""


@pytest.mark.asyncio
async def test_fastmcp_list_tools():
    """Verify tool discovery exposes all 3 required tools."""
    async with Client(transport=mcp) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "validate_mca_xbrl" in names
        assert "explain_mca_error" in names
        assert "get_mca_filing_checklist" in names


@pytest.mark.asyncio
async def test_fastmcp_validate_tool_success():
    """Verify validate_mca_xbrl returns structured JSON for valid XML."""
    async with Client(transport=mcp) as client:
        res = await client.call_tool("validate_mca_xbrl", {
            "xml_content": VALID_INDAS_XML,
            "taxonomy": "indas"
        })
        assert not res.is_error
        data = json.loads(res.data)
        assert data["valid"] is True
        assert data["taxonomy"] == "indas"
        assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_fastmcp_validate_tool_failure_handling():
    """Verify validate_mca_xbrl reports meaningful error on empty XML."""
    from fastmcp.exceptions import ToolError
    async with Client(transport=mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("validate_mca_xbrl", {
                "xml_content": "   ",
                "taxonomy": "indas"
            })
        assert "empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_fastmcp_explain_error_tool():
    """Verify explain_mca_error translates cvc-complex-type error."""
    async with Client(transport=mcp) as client:
        res = await client.call_tool("explain_mca_error", {
            "error_message": "cvc-complex-type.2.4.a: Invalid content was found starting with element 'foo'."
        })
        assert not res.is_error
        data = json.loads(res.data)
        assert "meaning" in data
        assert "claude_fix_action" in data


@pytest.mark.asyncio
async def test_fastmcp_checklist_tool():
    """Verify get_mca_filing_checklist returns required statutory gates."""
    async with Client(transport=mcp) as client:
        res = await client.call_tool("get_mca_filing_checklist", {
            "taxonomy": "indas"
        })
        assert not res.is_error
        data = json.loads(res.data)
        assert "mandatory_company_tags" in data
        assert data["taxonomy"] == "indas"


@pytest.mark.asyncio
async def test_fastmcp_read_resources():
    """Verify resources can be read via URI."""
    async with Client(transport=mcp) as client:
        # Read static HTML schema resource
        html_res = await client.read_resource("rules://mca/html-schema")
        assert html_res is not None
        html_data = json.loads(html_res[0].text)
        assert "allowed_tags" in html_data

        # Read dynamic checklist template resource
        chk_res = await client.read_resource("checklist://mca/indas")
        assert chk_res is not None
        chk_data = json.loads(chk_res[0].text)
        assert chk_data["taxonomy"] == "indas"


@pytest.mark.asyncio
async def test_fastmcp_get_prompt():
    """Verify prompt template retrieval."""
    async with Client(transport=mcp) as client:
        prompt = await client.get_prompt("mca_filing_review", {
            "company_cin": "U12345DL2020PTC123456",
            "taxonomy": "indas"
        })
        assert prompt is not None
        assert "U12345DL2020PTC123456" in prompt.messages[0].content.text
