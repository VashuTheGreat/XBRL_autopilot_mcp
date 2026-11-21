"""MCA HTML Schema validator for XBRL Text Blocks.

Validates narrative disclosures (Notes, Auditor Report, Directors Report)
against the official MCA HTML schema (http://www.mca.gov.in/XBRL/HTML).
"""

import re
from typing import List, Dict, Any, Tuple

# MCA Filing Manual allowed tags
ALLOWED_TAGS = {'div', 'span', 'p', 'br', 'table', 'td', 'tr', 'thead', 'tfoot', 'tbody', 'th'}
SCHEMA_REJECTED_TAGS = {'col', 'colgroup', 'caption', 'script', 'img', 'style', 'iframe', 'frame', 'font', 'a', 'b', 'i', 'u'}
SCHEMA_REJECTED_ATTRS = {'colspan', 'rowspan', 'style', 'width', 'height', 'align', 'valign', 'border', 'cellpadding', 'cellspacing', 'bgcolor'}
ALLOWED_ENTITIES = {'&nbsp;', '&amp;', '&lt;', '&gt;'}


def validate_mca_html(text_content: str, concept_name: str) -> Tuple[List[str], List[str]]:
    """Validates HTML inside a text block concept against the MCA HTML schema.
    
    Returns:
        (errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not text_content or not any(ch in text_content for ch in ('<', '&')):
        return errors, warnings

    # Check for processing instructions (e.g., <?xml ...?> or <?mso-application ...?>)
    if '<?' in text_content:
        errors.append(f"Text block '{concept_name}' contains XML processing instructions (<?...?>), which are strictly forbidden.")

    # Find all tags
    tag_pattern = re.compile(r'<\s*(/?)\s*([A-Za-z][A-Za-z0-9]*)([^>]*)>')
    for match in tag_pattern.finditer(text_content):
        is_closing = bool(match.group(1))
        tag_name = match.group(2)
        tag_lc = tag_name.lower()
        attr_string = match.group(3)

        # Tag case sensitivity check
        if tag_name != tag_lc:
            errors.append(f"Tag <{tag_name}> must be lowercase <{tag_lc}> in '{concept_name}'.")

        # Disallowed / rejected tags
        if tag_lc in SCHEMA_REJECTED_TAGS:
            errors.append(
                f"Tag <{tag_lc}> in '{concept_name}' is rejected by the MCA HTML Schema. "
                f"Only structural tags (div, span, p, br, table, tr, td, thead, tbody, tfoot, th) are permitted."
            )
        elif tag_lc not in ALLOWED_TAGS:
            errors.append(
                f"Tag <{tag_name}> in '{concept_name}' is not in the MCA allowed tag list: {sorted(list(ALLOWED_TAGS))}."
            )

        if not is_closing and attr_string:
            # Check attributes
            attr_pattern = re.compile(r'([A-Za-z_:][-\w:.]*)\s*(?:=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?')
            for attr_match in attr_pattern.finditer(attr_string):
                attr_name = attr_match.group(1).lower()
                if attr_name == 'class':
                    continue  # Only class attribute is accepted in MCA text blocks
                if attr_name == 'style':
                    errors.append(
                        f"Inline style attribute on <{tag_lc}> in '{concept_name}' is forbidden by MCA. Use CSS class instead."
                    )
                elif attr_name in SCHEMA_REJECTED_ATTRS:
                    errors.append(
                        f"Attribute '{attr_name}' on <{tag_lc}> in '{concept_name}' is rejected by the MCA HTML Schema."
                    )
                elif attr_name != '/':
                    warnings.append(
                        f"Attribute '{attr_name}' on <{tag_lc}> in '{concept_name}' is not recommended (MCA validates only 'class')."
                    )

    # Check entities
    entity_pattern = re.compile(r'&[A-Za-z0-9#]+;')
    for ent in entity_pattern.findall(text_content):
        if ent not in ALLOWED_ENTITIES:
            errors.append(f"HTML entity '{ent}' in '{concept_name}' is not allowed. Only &nbsp;, &amp;, &lt;, &gt; are permitted.")

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))
