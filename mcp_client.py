"""MCP Client Proxy for Hosted MCA Validation on Vercel.

Connects Claude Desktop (via stdio) to the hosted Vercel deployment:
https://xbrlautopilotmcp.vercel.app

Allows any Claude Desktop user anywhere to validate MCA XBRL instances
without needing local taxonomy files.
"""

import sys
import os
import json
import httpx
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP

VERCEL_BASE_URL = os.environ.get("MCA_MCP_URL", "https://xbrlautopilotmcp.vercel.app").rstrip("/")

mcp = FastMCP("mca-validation-hosted")


@mcp.tool()
def validate_mca_xbrl(xml_content: str, taxonomy: str = "indas") -> str:
    """Validates an MCA AOC-4 XBRL XML instance document for Ind-AS or C&I via the hosted engine.
    
    Args:
        xml_content: The full XBRL instance XML string to validate.
        taxonomy: Taxonomy standard: 'indas' (Ind-AS 2017) or 'ci' / 'cni' (C&I 2016).
        
    Returns:
        Structured JSON report containing validation status (PASS/FAIL), errors list
        with exact concepts, diffs, line numbers, and actionable Claude fix instructions.
    """
    url = f"{VERCEL_BASE_URL}/api/v1/validate"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json={"xml": xml_content, "taxonomy": taxonomy, "strict": True})
            if resp.status_code == 200:
                return json.dumps(resp.json(), indent=2)
            else:
                return json.dumps({
                    "valid": False,
                    "error": f"API returned status {resp.status_code}: {resp.text}"
                }, indent=2)
    except Exception as e:
        return json.dumps({
            "valid": False,
            "error": f"Failed to connect to hosted MCA validator at {url}: {str(e)}"
        }, indent=2)


@mcp.tool()
def explain_mca_error(error_message: str) -> str:
    """Translates cryptic Xerces XML schema or MCA Validation Tool error messages into plain English with Claude fix steps.
    
    Args:
        error_message: Raw error text from MCA Tool, Xerces ('cvc-...'), or Webtel.
        
    Returns:
        Structured JSON explanation with root cause and actionable fix instructions.
    """
    url = f"{VERCEL_BASE_URL}/api/v1/explain-error"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json={"error_message": error_message})
            if resp.status_code == 200:
                return json.dumps(resp.json(), indent=2)
            else:
                return json.dumps({"error": resp.text}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_mca_filing_checklist(taxonomy: str = "indas") -> str:
    """Returns the MCA statutory filing checklist and mandatory concepts for Claude.
    
    Args:
        taxonomy: 'indas' or 'ci'
        
    Returns:
        Checklist of mandatory tags, DIN requirements, Balance Sheet balancing equations, and text block HTML rules.
    """
    url = f"{VERCEL_BASE_URL}/api/v1/checklist/{taxonomy}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return json.dumps(resp.json(), indent=2)
            else:
                return json.dumps({"error": resp.text}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


if __name__ == "__main__":
    mcp.run()
