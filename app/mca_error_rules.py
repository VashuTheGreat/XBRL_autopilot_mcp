"""MCA & Xerces Error Explainer and Fix Recommender for Claude.

Turns cryptic XML Schema / Xerces ('cvc-...') and MCA Validation Tool messages
into structured explanations with actionable fix steps for Claude.
"""

import re
from typing import Dict, Any, Optional
from app.models import ExplainErrorResponse

PATTERNS = [
    {
        "code": "html",
        "regex": re.compile(r"Element '([^']+)' the contained HTML has the following errors:\s*(.*)$"),
        "title": "Invalid HTML inside Text Block",
        "meaning": lambda m: f"The text block '{m.group(1)}' contains HTML formatting that the MCA HTML schema rejects: {m.group(2)}",
        "cause": "Disallowed tags (<colgroup>, <col>, <caption>, <script>, <img>) or forbidden attributes (style=, colspan=, rowspan=, width=, align=).",
        "fix": lambda m: f"In text block '{m.group(1)}', strip out inline 'style' and table formatting attributes (colspan/rowspan). Keep only standard structural tags (<div>, <p>, <span>, <br>, <table>, <tr>, <td>) and use only the 'class' attribute if needed."
    },
    {
        "code": "cvc-complex-type.3.2.2",
        "regex": re.compile(r"cvc-complex-type\.3\.2\.2: Attribute '([^']+)' is not allowed to appear in element '([^']+)'"),
        "title": "Attribute Not Allowed on Element",
        "meaning": lambda m: f"The XML schema of '{m.group(2)}' does not declare or permit the attribute '{m.group(1)}'.",
        "cause": "Often 'xml:lang' placed on a restricted type (PAN, CIN, DIN), or inline HTML attributes like 'style' or 'colspan'.",
        "fix": lambda m: f"Remove attribute '{m.group(1)}' from element <{m.group(2)}> in the XML."
    },
    {
        "code": "cvc-complex-type.2.4.a",
        "regex": re.compile(r"cvc-complex-type\.2\.4\.a: Invalid content was found starting with element '([^']+)'\. One of '\{?(.*?)\}?' is expected"),
        "title": "Element Out of Order or Disallowed",
        "meaning": lambda m: f"Element '{m.group(1)}' appears in a position where the schema expects: {m.group(2)}.",
        "cause": "Wrong element sequence or misplaced child tags.",
        "fix": lambda m: f"Reorder or remove element <{m.group(1)}>. Check the schema presentation order."
    },
    {
        "code": "cvc-complex-type.2.4.b",
        "regex": re.compile(r"cvc-complex-type\.2\.4\.b: The content of element '([^']+)' is not complete\. One of '\{?(.*?)\}?' is expected"),
        "title": "Required Child Element Missing",
        "meaning": lambda m: f"Element '{m.group(1)}' is incomplete. One of '{m.group(2)}' is required inside it.",
        "cause": "Empty context, incomplete tuple, or empty table row in text block.",
        "fix": lambda m: f"Provide the missing required child element ({m.group(2)}) inside <{m.group(1)}>."
    },
    {
        "code": "cvc-complex-type.4",
        "regex": re.compile(r"cvc-complex-type\.4: Attribute '([^']+)' must appear on element '([^']+)'"),
        "title": "Required Attribute Missing",
        "meaning": lambda m: f"Element '{m.group(2)}' is missing the mandatory attribute '{m.group(1)}'.",
        "cause": "Fact missing contextRef, unitRef, or decimals attribute.",
        "fix": lambda m: f"Add the required attribute '{m.group(1)}' to <{m.group(2)}> (e.g. contextRef=\"CY_Instant\" unitRef=\"INR\" decimals=\"0\")."
    },
    {
        "code": "cvc-pattern-valid",
        "regex": re.compile(r"cvc-pattern-valid: Value '([^']*)' is not facet-valid with respect to pattern '([^']*)' for type '([^']+)'"),
        "title": "Format Pattern Mismatch (CIN, PAN, DIN)",
        "meaning": lambda m: f"Value '{m.group(1)}' does not match the required regex pattern '{m.group(2)}' for type '{m.group(3)}'.",
        "cause": "Formatting error in CIN (must be 21 chars), PAN (10 chars: 5 letters, 4 digits, 1 letter), or DIN (8 digits).",
        "fix": lambda m: f"Correct the value '{m.group(1)}' to match pattern '{m.group(2)}'. Ensure uppercase letters with no extra whitespace."
    },
    {
        "code": "cvc-enumeration-valid",
        "regex": re.compile(r"cvc-enumeration-valid: Value '([^']*)' is not facet-valid with respect to enumeration '\[(.*)\]'"),
        "title": "Value Not in Allowed Enumeration",
        "meaning": lambda m: f"Value '{m.group(1)}' is not one of the allowed taxonomy choices: {m.group(2)}.",
        "cause": "Spelling or case mismatch in dropdown/enum field (e.g. 'standalone' vs 'Standalone', 'Exact' vs 'None').",
        "fix": lambda m: f"Change the element value '{m.group(1)}' to exactly one of the valid options: {m.group(2)}."
    },
    {
        "code": "cvc-length-valid",
        "regex": re.compile(r"cvc-(length|minLength|maxLength)-valid: Value '([^']*)' with length = '(\d+)' is not facet-valid with respect to (?:length|minLength|maxLength) '(\d+)'"),
        "title": "Value Length Incorrect",
        "meaning": lambda m: f"Value '{m.group(2)}' has {m.group(3)} characters, but the schema requires length of {m.group(4)}.",
        "cause": "Code value with wrong character count (e.g. 7-digit DIN instead of 8 digits, or 9-character PAN).",
        "fix": lambda m: f"Update the field value to exactly {m.group(4)} characters."
    },
    {
        "code": "cvc-datatype-valid",
        "regex": re.compile(r"cvc-datatype-valid\.1\.2\.1: '([^']*)' is not a valid value for '([^']+)'"),
        "title": "Invalid Datatype",
        "meaning": lambda m: f"Value '{m.group(1)}' is not a valid {m.group(2)}.",
        "cause": "Formatting error: commas in numbers, date in dd-mm-yyyy instead of yyyy-mm-dd, or non-boolean value.",
        "fix": lambda m: f"Reformat '{m.group(1)}': numbers must have no commas or currency symbols; dates must be 'YYYY-MM-DD'; booleans must be 'true' or 'false'."
    },
    {
        "code": "cvc-type.3.1.3",
        "regex": re.compile(r"cvc-type\.3\.1\.3: The value '([^']*)' of element '([^']+)' is not valid"),
        "title": "Invalid Value for Element",
        "meaning": lambda m: f"Element '{m.group(2)}' has an invalid value '{m.group(1)}'.",
        "cause": "Refer to the accompanying pattern or datatype message.",
        "fix": lambda m: f"Check element <{m.group(2)}> and replace '{m.group(1)}' with a valid value."
    },
    {
        "code": "cvc-elt.3.1",
        "regex": re.compile(r"cvc-elt\.3\.1: Attribute '[^']*nil' must not appear on element '([^']+)'"),
        "title": "Element Cannot Be Nil",
        "meaning": lambda m: f"Element '{m.group(1)}' is marked with xsi:nil='true', but its schema definition is not nillable.",
        "cause": "Empty or omitted fact explicitly marked nil.",
        "fix": lambda m: f"Provide a non-empty value for <{m.group(1)}> or omit the element if optional."
    },
    {
        "code": "cvc-elt.1",
        "regex": re.compile(r"cvc-elt\.1(?:\.a)?: Cannot find the declaration of element '([^']+)'"),
        "title": "Unknown Concept / Element Declaration",
        "meaning": lambda m: f"Element '{m.group(1)}' does not exist in the taxonomy.",
        "cause": "Typo in element name or incorrect XML namespace prefix.",
        "fix": lambda m: f"Verify the tag name '{m.group(1)}' against official taxonomy concepts. Check namespace prefix (e.g. ind-as: vs in-ca: vs in-gaap:)."
    }
]


def explain_mca_error(error_str: str) -> ExplainErrorResponse:
    """Explains a raw MCA / Xerces validation error string."""
    raw = error_str.strip()
    for entry in PATTERNS:
        match = entry["regex"].search(raw)
        if match:
            elem = None
            try:
                # Try finding element if regex captured it
                if match.re.groups >= 2:
                    elem = match.group(2) if 'element' in entry['title'].lower() else match.group(1)
                elif match.re.groups >= 1:
                    elem = match.group(1)
            except Exception:
                elem = None

            return ExplainErrorResponse(
                matched_code=entry["code"],
                title=entry["title"],
                meaning=entry["meaning"](match) if callable(entry["meaning"]) else entry["meaning"],
                likely_cause=entry["cause"],
                element=elem,
                claude_fix_action=entry["fix"](match) if callable(entry["fix"]) else entry["fix"]
            )

    # General fallback if unrecognized
    return ExplainErrorResponse(
        matched_code="UNKNOWN_MCA_ERROR",
        title="Unclassified MCA Validation Notice",
        meaning=f"Raw validation output: {raw}",
        likely_cause="The MCA validator reported a custom business constraint or unmapped warning.",
        element=None,
        claude_fix_action="Inspect the concept and value referenced in the error text, verify taxonomy schema types, and ensure all math balances."
    )
