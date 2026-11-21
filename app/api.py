"""FastAPI Router for MCA XBRL Validation Engine.

Provides HTTP REST API endpoints:
- POST /api/v1/validate (JSON payload)
- POST /api/v1/validate/file (Multipart file upload)
- POST /api/v1/explain-error (Explain raw MCA/Xerces errors)
- GET  /api/v1/checklist/{taxonomy} (Get filing checklist)
- GET  /health (Service health)
- GET  / (Interactive Web UI for live XML validation)
"""

import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models import (
    ValidationRequest,
    ValidationResponse,
    ExplainErrorRequest,
    ExplainErrorResponse,
)
from app.validator import MCAValidator
from app.mca_error_rules import explain_mca_error
from app.mcp_server import get_mca_filing_checklist

app = FastAPI(
    title="MCA XBRL Validation MCP & Engine",
    description="Statutory MCA AOC-4 XBRL Validation API for Claude & Accountants (Ind-AS 2017 & C&I 2016)",
    version="1.0.0"
)

# Enable CORS for browser integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "mca_validation_mcp",
        "taxonomies_supported": ["indas", "ci"]
    }


@app.post(
    "/api/v1/validate",
    response_model=ValidationResponse,
    tags=["Validation"],
    summary="Validate XBRL XML Instance (JSON)"
)
async def validate_xml(req: ValidationRequest) -> ValidationResponse:
    """Validates an XBRL instance XML document for Ind-AS or C&I."""
    try:
        validator = MCAValidator(taxonomy=req.taxonomy, strict=req.strict)
        return validator.validate(req.xml)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )


@app.post(
    "/api/v1/validate/file",
    response_model=ValidationResponse,
    tags=["Validation"],
    summary="Validate XBRL XML File Upload"
)
async def validate_file(
    file: UploadFile = File(...),
    taxonomy: str = Form("indas"),
    strict: bool = Form(True)
) -> ValidationResponse:
    """Validates an uploaded .xml XBRL instance file."""
    try:
        content = await file.read()
        xml_text = content.decode("utf-8", errors="replace")
        validator = MCAValidator(taxonomy=taxonomy, strict=strict)
        return validator.validate(xml_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {str(e)}"
        )


@app.post(
    "/api/v1/explain-error",
    response_model=ExplainErrorResponse,
    tags=["Error Explainer"],
    summary="Explain raw MCA Tool / Xerces error"
)
async def explain_error_endpoint(req: ExplainErrorRequest) -> ExplainErrorResponse:
    """Explains raw Xerces/MCA errors and returns Claude fix guidelines."""
    return explain_mca_error(req.error_message)


@app.get("/api/v1/checklist/{taxonomy}", tags=["Checklist"])
async def get_checklist(taxonomy: str = "indas"):
    """Returns filing requirements and mandatory concepts checklist."""
    checklist_str = get_mca_filing_checklist(taxonomy)
    return json.loads(checklist_str)


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard():
    """Interactive Web UI for live XBRL XML testing and validation."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MCA XBRL Validation MCP Engine</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; }
    pre, code { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-sm">
        MCA
      </div>
      <div>
        <h1 class="text-base font-semibold leading-tight">MCA XBRL Validation MCP</h1>
        <p class="text-xs text-slate-400">Autonomous Statutory Gatekeeper for Claude & AOC-4 Filings</p>
      </div>
    </div>
    <div class="flex items-center gap-4 text-xs">
      <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition">Swagger API</a>
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
        Ind-AS & C&I Active
      </span>
    </div>
  </header>

  <main class="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Input Panel -->
    <div class="flex flex-col bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-xl">
      <div class="flex items-center justify-between mb-4">
        <label class="text-sm font-semibold text-slate-200">XBRL XML Instance Document</label>
        <div class="flex items-center gap-2">
          <label class="text-xs text-slate-400">Taxonomy:</label>
          <select id="taxonomy" class="bg-slate-900 border border-slate-700 text-xs rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500">
            <option value="indas">Ind-AS 2017</option>
            <option value="ci">C&I 2016 (AS)</option>
          </select>
        </div>
      </div>

      <textarea id="xmlInput" placeholder="Paste your generated <?xml ...?> XBRL document here..." class="flex-1 min-h-[420px] w-full bg-slate-900/90 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 font-mono focus:outline-none focus:border-emerald-500 resize-none leading-relaxed"></textarea>

      <div class="mt-4 flex items-center justify-between">
        <label class="cursor-pointer text-xs text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
          <span>Upload File</span>
          <input type="file" id="fileUpload" accept=".xml" class="hidden" onchange="handleFileUpload(event)">
        </label>
        <button onclick="runValidation()" id="validateBtn" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-2">
          <span>Validate XML</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
        </button>
      </div>
    </div>

    <!-- Results Panel -->
    <div class="flex flex-col bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-xl overflow-hidden">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-slate-200">Statutory Validation Ledger</h2>
        <span id="badgeStatus" class="px-2.5 py-0.5 rounded text-xs font-medium bg-slate-800 text-slate-400">Idle</span>
      </div>

      <div id="resultsContainer" class="flex-1 overflow-y-auto space-y-4 pr-1">
        <div class="h-full flex flex-col items-center justify-center text-center p-8 text-slate-500">
          <svg class="w-12 h-12 mb-3 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <p class="text-sm">Submit XBRL instance document to evaluate against 12 MCA Statutory Gates.</p>
        </div>
      </div>
    </div>
  </main>

  <script>
    async function handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        const text = await file.text();
        document.getElementById('xmlInput').value = text;
      }
    }

    async function runValidation() {
      const xml = document.getElementById('xmlInput').value.trim();
      const taxonomy = document.getElementById('taxonomy').value;
      const btn = document.getElementById('validateBtn');
      const badge = document.getElementById('badgeStatus');
      const container = document.getElementById('resultsContainer');

      if (!xml) {
        alert("Please paste or upload XBRL XML content first.");
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span class="animate-spin inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full mr-2"></span>Validating...`;
      badge.className = "px-2.5 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20";
      badge.textContent = "Processing Gates...";

      try {
        const res = await fetch("/api/v1/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ xml, taxonomy, strict: true })
        });
        const data = await res.json();
        renderResults(data);
      } catch (err) {
        alert("Validation error: " + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Validate XML</span><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>`;
      }
    }

    function renderResults(data) {
      const badge = document.getElementById('badgeStatus');
      const container = document.getElementById('resultsContainer');

      if (data.valid) {
        badge.className = "px-2.5 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
        badge.textContent = "PASSED (0 Errors)";
      } else {
        badge.className = "px-2.5 py-0.5 rounded text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30";
        badge.textContent = `FAILED (${data.summary.total_errors} Errors)`;
      }

      let html = `
        <div class="grid grid-cols-3 gap-2 mb-4 p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs">
          <div><span class="text-slate-400">Errors:</span> <span class="font-bold ${data.summary.total_errors > 0 ? 'text-rose-400' : 'text-emerald-400'}">${data.summary.total_errors}</span></div>
          <div><span class="text-slate-400">Warnings:</span> <span class="font-bold text-amber-400">${data.summary.total_warnings}</span></div>
          <div><span class="text-slate-400">Facts Parsed:</span> <span class="font-bold text-slate-200">${data.summary.facts_evaluated}</span></div>
        </div>
      `;

      if (data.errors && data.errors.length > 0) {
        html += `<h3 class="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-2">Blocking Statutory Errors:</h3>`;
        data.errors.forEach(err => {
          html += `
            <div class="border border-rose-500/30 bg-rose-950/20 rounded-lg p-3 text-xs space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-semibold text-rose-300 font-mono">${err.code}</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-rose-900/50 text-rose-300">${err.gate}</span>
              </div>
              <p class="text-slate-300">${err.message}</p>
              ${err.diff !== null && err.diff !== undefined ? `<div class="font-mono text-[11px] text-amber-300">Expected: ${err.expected} | Actual: ${err.actual} | Diff: ${err.diff}</div>` : ''}
              <div class="mt-2 p-2 bg-slate-900 border border-slate-800 rounded text-emerald-300 font-mono text-[11px]">
                <strong class="text-slate-400">Claude Fix:</strong> ${err.claude_fix_action}
              </div>
            </div>
          `;
        });
      }

      if (data.warnings && data.warnings.length > 0) {
        html += `<h3 class="text-xs font-semibold text-amber-400 uppercase tracking-wider mt-4 mb-2">Non-Blocking Statutory Warnings:</h3>`;
        data.warnings.forEach(w => {
          html += `
            <div class="border border-amber-500/30 bg-amber-950/20 rounded-lg p-3 text-xs space-y-1">
              <div class="font-mono text-amber-300 font-semibold">${w.code}</div>
              <p class="text-slate-300">${w.message}</p>
              <div class="text-[11px] text-slate-400 font-mono">${w.claude_fix_action}</div>
            </div>
          `;
        });
      }

      if (data.passed_checks && data.passed_checks.length > 0) {
        html += `<h3 class="text-xs font-semibold text-emerald-400 uppercase tracking-wider mt-4 mb-2">Passed Statutory Checks:</h3>`;
        html += `<ul class="list-disc list-inside space-y-1 text-xs text-slate-400">`;
        data.passed_checks.forEach(chk => {
          html += `<li>${chk}</li>`;
        });
        html += `</ul>`;
      }

      container.innerHTML = html;
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
