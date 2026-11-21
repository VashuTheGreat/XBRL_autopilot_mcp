# MCA XBRL Validation Engine & MCP Server

An autonomous statutory **MCA AOC-4 XBRL Validation Engine** and **Model Context Protocol (MCP)** server built for **Claude** (and Chartered Accountants). It validates generated XBRL XML files just like the official **MCA XBRL Validation Tool v5.1** and **Webtel webXBRL**, catching statutory errors, math calculation mismatches, Balance Sheet discrepancies, missing mandatory company info, and HTML schema violations before filing.

When Claude generates XBRL XML, it calls this MCP tool. If errors exist, it receives structured diffs, exact concept names, contexts, line numbers, and actionable remediation instructions. Claude repairs the XML and re-validates in an autonomous closed loop until the instance passes 100% cleanly.

---

## 🚀 Key Capabilities

- **Dual Taxonomy Support (Zero Costing)**:
  - **Indian Accounting Standards (Ind-AS 2017)**: 5,647 concepts, 37 calculation linkbase ELRs, 225 mandatory concepts, 211 non-negative concepts.
  - **Commercial & Industrial (C&I 2016 / AS)**: 23 calculation linkbases, 245 mandatory concepts, 197 non-negative rules.
- **12 MCA Statutory Validation Gates**:
  1. **Gate 1: Well-Formed XML & Root Tag**: Validates `<xbrli:xbrl>` root and XML syntax.
  2. **Gate 2: Taxonomy Schema Reference**: Verifies official MCA V3 `schemaRef` URL.
  3. **Gate 3: Contexts, CIN Scheme & Period Dates**: Scheme `http://www.mca.gov.in/CIN`, 21-character alphanumeric CIN format (`^[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}$`), valid `YYYY-MM-DD` dates, CY/PY pairing.
  4. **Gate 4: Units & Currencies**: Validates standard `iso4217:INR` currency unit and decimal attributes (no disallowed scale/precision).
  5. **Gate 5: Mandatory Demographic Information**: Enforces corporate CIN, Name, PAN (10-char), Registered Office, Board approval date, Reporting period start/end, Rounding level, and Subsidiary flags.
  6. **Gate 6: Statutory Signatories & Auditor Governance**: Section 134(1) Companies Act rule requiring **minimum 2 Director signatories** with valid 8-digit numeric DINs.
  7. **Gate 7: Statement Roots**: Verifies mandatory statement roots (`Assets`, `EquityAndLiabilities`, `ProfitLossForPeriod`).
  8. **Gate 8: Balance Sheet Hard Balancing**: Enforces $\text{Total Assets} == \text{Total Equity and Liabilities}$ within $\pm 1.0$ INR MCA tolerance.
  9. **Gate 9: Arithmetic & Calculation Linkbase Rollups**: Evaluates $\sum (\text{child} \times \text{weight}) == \text{parent}$ across all calculation linkbases.
  10. **Gate 10: Non-Negative Constraints**: Validates statutory non-negative concepts ($\ge 0$).
  11. **Gate 11: Text Block MCA HTML Schema**: Enforces official MCA HTML schema (`http://www.mca.gov.in/XBRL/HTML`): allows only clean structural tags (`div`, `p`, `span`, `br`, `table`, `tr`, `td`), strictly rejects inline styles, colgroups, scripts, images, and non-whitelisted attributes.
  12. **Gate 12: Specific & Generic MCA Rules**: Enforces share capital hierarchy ($\text{Authorised} \ge \text{Issued} \ge \text{Subscribed}$) and corporate reporting rules.
- **Claude Fix Guidance**:
  Every error returns a concrete `claude_fix_action` instructing Claude exactly what tag to add, edit, or reconcile.
- **Xerces / MCA Error Explainer**:
  Translates cryptic schema errors (`cvc-complex-type.2.4.a`, `cvc-pattern-valid`, `cvc-type.3.1.3`, `Element '...' the contained HTML has the following errors`) into plain-English cause and fix steps.

---

## 🛠️ MCP Tools Exposed to Claude

### 1. `validate_mca_xbrl(xml_content: str, taxonomy: str = "indas")`
Accepts the generated XBRL XML string and returns validation results with status, error list, line numbers, expected vs actual values, diffs, and Claude fix guidelines.

### 2. `explain_mca_error(error_message: str)`
Takes raw error output from MCA Tool, Xerces, or Webtel and explains it in plain language with remediation steps.

### 3. `get_mca_filing_checklist(taxonomy: str = "indas")`
Returns mandatory tags, DIN format requirements, and HTML guidelines for Claude to construct compliant filings.

---

## 🌐 FastAPI REST Endpoints & Web Dashboard

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/validate` | Validates XBRL XML string (JSON payload) |
| `POST` | `/api/v1/validate/file` | Validates uploaded `.xml` file (multipart/form-data) |
| `POST` | `/api/v1/explain-error` | Explains raw MCA / Xerces error string |
| `GET` | `/api/v1/checklist/{taxonomy}`| Returns filing requirements checklist |
| `GET` | `/health` | Service health status |
| `GET` | `/` | **Interactive Web UI Dashboard** for live XML testing |
| `GET` | `/docs` | Interactive Swagger API documentation |

---

## 📦 Claude Desktop / Agent Configuration

To use this with Claude Desktop or Claude CLI, add it to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mca-validation": {
      "command": "python3",
      "args": [
        "-m",
        "app.main",
        "--mcp"
      ],
      "cwd": "/home/vanshsharma/projects/mca_validation_mcp"
    }
  }
}
```

---

## 🏃 Running the Server

### 1. Start FastAPI Web Server & UI:
```bash
cd /home/vanshsharma/projects/mca_validation_mcp
chmod +x run.sh
./run.sh
```
Open [http://localhost:8000/](http://localhost:8000/) in your browser.

### 2. Start MCP stdio Server:
```bash
./run.sh --mcp
```

### 3. Run the Test Suite:
```bash
python3 -c "
import tests.test_validator as tv
import tests.test_api as ta
tv.test_valid_indas_instance()
tv.test_valid_ci_instance()
tv.test_bs_mismatch_detection()
tv.test_missing_mandatory_and_bad_din()
tv.test_html_schema_violation()
tv.test_error_explainer()
ta.test_health()
ta.test_validate_endpoint()
ta.test_explain_error_endpoint()
ta.test_checklist_endpoint()
print('All tests passed successfully!')
"
```
