"""XBRL Instance Document Parser for MCA filings.

Parses XBRL XML documents, extracts namespaces, schemaRefs, contexts,
units, and facts with exact line numbers and metadata.
"""

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple, Set


class XbrlContext:
    def __init__(self, context_id: str):
        self.id = context_id
        self.scheme: Optional[str] = None
        self.identifier: Optional[str] = None
        self.period_type: Optional[str] = None  # 'instant' or 'duration'
        self.instant: Optional[str] = None
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None
        self.is_segment: bool = False
        self.explicit_members: Dict[str, str] = {}
        self.typed_members: Dict[str, str] = {}
        self.line_number: Optional[int] = None

    def __repr__(self):
        return f"<XbrlContext id={self.id} period={self.period_type} ident={self.identifier}>"


class XbrlUnit:
    def __init__(self, unit_id: str):
        self.id = unit_id
        self.measure: Optional[str] = None
        self.numerator: Optional[str] = None
        self.denominator: Optional[str] = None
        self.line_number: Optional[int] = None


class XbrlFact:
    def __init__(self, qname: str, value: Optional[str], context_ref: Optional[str] = None):
        self.qname = qname
        self.prefix, self.local_name = qname.split(":", 1) if ":" in qname else ("", qname)
        self.value = value or ""
        self.context_ref = context_ref
        self.unit_ref: Optional[str] = None
        self.decimals: Optional[str] = None
        self.is_nil: bool = False
        self.line_number: Optional[int] = None

        # Numeric value cache
        self.numeric_value: Optional[float] = None
        self._parse_numeric()

    def _parse_numeric(self):
        if self.value and not self.is_nil:
            clean = self.value.strip().replace(",", "")
            try:
                self.numeric_value = float(clean)
            except ValueError:
                self.numeric_value = None

    def is_numeric(self) -> bool:
        return self.numeric_value is not None

    def is_text_block(self) -> bool:
        return "textblock" in self.local_name.lower() or "explanatory" in self.local_name.lower()

    def __repr__(self):
        return f"<XbrlFact {self.qname} ctx={self.context_ref} val={self.value[:30]}>"


class ParsedXbrlDocument:
    """Represents a fully parsed XBRL instance document."""

    def __init__(self):
        self.raw_xml: str = ""
        self.root_tag: str = ""
        self.namespaces: Dict[str, str] = {}
        self.schema_ref: Optional[str] = None
        self.contexts: Dict[str, XbrlContext] = {}
        self.units: Dict[str, XbrlUnit] = {}
        self.facts: List[XbrlFact] = []
        self.facts_by_qname: Dict[str, List[XbrlFact]] = {}
        self.facts_by_context: Dict[str, List[XbrlFact]] = {}
        self.errors: List[str] = []

    def get_fact(self, qname: str, context_ref: Optional[str] = None) -> Optional[XbrlFact]:
        """Finds a single fact by concept QName, optionally matching contextRef."""
        facts = self.facts_by_qname.get(qname, [])
        if not facts:
            # Also try matching just local name if prefix differs
            local = qname.split(":")[-1]
            for f in self.facts:
                if f.local_name == local:
                    if context_ref is None or f.context_ref == context_ref:
                        return f
            return None
        if context_ref is None:
            return facts[0]
        for f in facts:
            if f.context_ref == context_ref:
                return f
        return None

    def get_facts(self, qname: str) -> List[XbrlFact]:
        return self.facts_by_qname.get(qname, [])

    def get_fact_value(self, qname: str, context_ref: Optional[str] = None) -> Optional[str]:
        f = self.get_fact(qname, context_ref)
        return f.value if f else None


class XbrlInstanceParser:
    """Expat-based / ElementTree parser with line numbering and namespace resolution."""

    # Official known namespaces
    STANDARD_NAMESPACES = {
        "http://www.xbrl.org/2003/instance": "xbrli",
        "http://www.xbrl.org/2003/linkbase": "link",
        "http://www.w3.org/1999/xlink": "xlink",
        "http://xbrl.org/2006/xbrldi": "xbrldi",
        "http://www.xbrl.org/2003/iso4217": "iso4217",
        "http://www.w3.org/2001/XMLSchema-instance": "xsi",
        "http://www.icai.org/xbrl/taxonomy/2017-03-31/ind-as": "ind-as",
        "http://www.mca.gov.in/ind-as/2016-03-31": "ind-as",
        "http://www.icai.org/xbrl/taxonomy/2017-03-31/in-ca": "in-ca",
        "http://www.mca.gov.in/in-ca/2016-03-31": "in-ca",
        "http://www.icai.org/xbrl/taxonomy/2016-03-31/in-gaap": "in-gaap",
        "http://www.icai.org/xbrl/taxonomy/2016-03-31/in-ca": "in-ca",
    }

    @classmethod
    def parse(cls, xml_text: str) -> Tuple[Optional[ParsedXbrlDocument], Optional[str]]:
        """Parses an XBRL instance XML string.
        
        Returns:
            (ParsedXbrlDocument, error_message_if_failed)
        """
        if not xml_text or not xml_text.strip():
            return None, "Empty XML document provided."

        doc = ParsedXbrlDocument()
        doc.raw_xml = xml_text

        # Extract namespace prefix declarations from root tag
        ns_map = {}
        for match in re.finditer(r'xmlns:([A-Za-z0-9_-]+)=["\']([^"\']+)["\']', xml_text[:2000]):
            ns_map[match.group(2)] = match.group(1)
        for uri, default_pfx in cls.STANDARD_NAMESPACES.items():
            if uri not in ns_map:
                ns_map[uri] = default_pfx
        doc.namespaces = ns_map

        # Parse XML tree
        try:
            # We use iterparse or XML with line numbers if possible
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            return None, f"XML Syntax Error (Line {e.position[0]}, Column {e.position[1]}): {e}"
        except Exception as e:
            return None, f"Failed to parse XML: {str(e)}"

        doc.root_tag = root.tag

        # Find schemaRef
        for elem in root.iter():
            if elem.tag.endswith("schemaRef"):
                # xlink:href attribute
                for k, v in elem.attrib.items():
                    if k.endswith("href") or "href" in k:
                        doc.schema_ref = v
                        break
                if doc.schema_ref:
                    break

        # Parse Contexts
        for elem in root:
            if elem.tag.endswith("context"):
                cid = elem.attrib.get("id", "")
                ctx = XbrlContext(cid)
                for child in elem:
                    if child.tag.endswith("entity"):
                        for sub in child:
                            if sub.tag.endswith("identifier"):
                                ctx.identifier = (sub.text or "").strip()
                                ctx.scheme = sub.attrib.get("scheme", "")
                            elif sub.tag.endswith("segment"):
                                ctx.is_segment = True
                                cls._extract_scenario_dimensions(sub, ctx, ns_map)
                    elif child.tag.endswith("period"):
                        for p in child:
                            if p.tag.endswith("instant"):
                                ctx.period_type = "instant"
                                ctx.instant = (p.text or "").strip()
                            elif p.tag.endswith("startDate"):
                                ctx.start_date = (p.text or "").strip()
                            elif p.tag.endswith("endDate"):
                                ctx.end_date = (p.text or "").strip()
                        if ctx.start_date and ctx.end_date:
                            ctx.period_type = "duration"
                    elif child.tag.endswith("scenario"):
                        cls._extract_scenario_dimensions(child, ctx, ns_map)
                doc.contexts[cid] = ctx

            elif elem.tag.endswith("unit"):
                uid = elem.attrib.get("id", "")
                unit = XbrlUnit(uid)
                for m in elem.iter():
                    if m.tag.endswith("measure"):
                        unit.measure = (m.text or "").strip()
                doc.units[uid] = unit

            elif not elem.tag.endswith("context") and not elem.tag.endswith("unit") and not elem.tag.endswith("schemaRef"):
                # This is a financial or master fact
                tag_str = elem.tag
                qname = cls._format_qname(tag_str, ns_map)
                val = elem.text or ""
                # Also include nested text if it has inner XML/HTML tags
                if len(elem) > 0:
                    val = ET.tostring(elem, encoding="unicode")
                    # strip outer wrapper tag
                    m_inner = re.search(r"^<[^>]+>(.*)</[^>]+>$", val, re.DOTALL)
                    if m_inner:
                        val = m_inner.group(1)

                fact = XbrlFact(qname, val, elem.attrib.get("contextRef"))
                fact.unit_ref = elem.attrib.get("unitRef")
                fact.decimals = elem.attrib.get("decimals")
                # xsi:nil check
                for ak, av in elem.attrib.items():
                    if ak.endswith("nil") and av.lower() in ("true", "1"):
                        fact.is_nil = True

                doc.facts.append(fact)
                doc.facts_by_qname.setdefault(qname, []).append(fact)
                if fact.context_ref:
                    doc.facts_by_context.setdefault(fact.context_ref, []).append(fact)

        return doc, None

    @classmethod
    def _extract_scenario_dimensions(cls, container_elem: ET.Element, ctx: XbrlContext, ns_map: Dict[str, str]):
        for node in container_elem.iter():
            if node.tag.endswith("explicitMember"):
                dim = node.attrib.get("dimension", "")
                val = (node.text or "").strip()
                ctx.explicit_members[cls._format_qname(dim, ns_map)] = cls._format_qname(val, ns_map)
            elif node.tag.endswith("typedMember"):
                dim = node.attrib.get("dimension", "")
                # inner tag value
                inner_text = "".join(node.itertext()).strip()
                ctx.typed_members[cls._format_qname(dim, ns_map)] = inner_text

    @classmethod
    def _format_qname(cls, tag_or_qname: str, ns_map: Dict[str, str]) -> str:
        if tag_or_qname.startswith("{"):
            uri, local = tag_or_qname[1:].split("}", 1)
            prefix = ns_map.get(uri)
            if not prefix:
                if "ind-as" in uri or "ind_as" in uri:
                    prefix = "ind-as"
                elif "in-gaap" in uri:
                    prefix = "in-gaap"
                elif "in-ca" in uri:
                    prefix = "in-ca"
                elif "xbrli" in uri:
                    prefix = "xbrli"
                else:
                    prefix = uri.split("/")[-1].split("#")[-1]
            return f"{prefix}:{local}"
        return tag_or_qname
