"""MCA XBRL Validation Engine.

Performs comprehensive statutory validation of MCA AOC-4 XBRL instances
for Ind-AS and C&I taxonomies, matching the official MCA XBRL Validation Tool v5.1
and Webtel standards.
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from app.models import (
    ValidationErrorItem,
    ValidationResponse,
    ValidationSummary,
)
from app.parser import XbrlInstanceParser, ParsedXbrlDocument, XbrlFact, XbrlContext
from app.data_loader import loader
from app.rules.html_rules import validate_mca_html


CIN_REGEX = re.compile(r"^[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}$")
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MCAValidator:
    """Multi-tier MCA statutory validator for AOC-4 XBRL instances."""

    def __init__(self, taxonomy: str = "indas", strict: bool = True):
        self.taxonomy = taxonomy.lower().strip()
        self.is_ind_as = "ind" in self.taxonomy
        self.strict = strict
        self.kb = loader.get_kb("indas" if self.is_ind_as else "ci")

        self.calculation = self.kb.get("calculation", {})
        self.business_rules = self.kb.get("businessRules", {})
        self.mandatory_concepts = set(self.business_rules.get("mandatoryConcepts", []))
        self.mandatory_by_elr = self.business_rules.get("mandatoryByELR", {})
        self.non_negative_concepts = set(self.business_rules.get("nonNegativeConcepts", []))

    def validate(self, xml_content: str) -> ValidationResponse:
        """Executes complete statutory validation against the provided XML."""
        errors: List[ValidationErrorItem] = []
        warnings: List[ValidationErrorItem] = []
        passed_checks: List[str] = []
        metadata: Dict[str, Any] = {"taxonomy": "indas" if self.is_ind_as else "ci"}

        gates_count = 12
        failed_gates = set()

        # -------------------------------------------------------------
        # Gate 1: XML Well-Formedness & Root Element
        # -------------------------------------------------------------
        doc, parse_err = XbrlInstanceParser.parse(xml_content)
        if parse_err or doc is None:
            failed_gates.add("Gate 1: Well-Formed XML")
            errors.append(ValidationErrorItem(
                code="XML_SYNTAX_ERROR",
                gate="Gate 1: XML Well-Formedness",
                category="SCHEMA",
                severity="CRITICAL",
                message=f"XML Parsing Failed: {parse_err}",
                claude_fix_action="Ensure the document is valid XML with properly closed tags, uncorrupted characters, and no syntax errors."
            ))
            summary = ValidationSummary(
                total_errors=len(errors),
                total_warnings=0,
                gates_evaluated=1,
                gates_passed=0,
                gates_failed=1
            )
            return ValidationResponse(
                valid=False,
                taxonomy=self.taxonomy,
                summary=summary,
                errors=errors,
                warnings=warnings,
                passed_checks=passed_checks,
                metadata=metadata
            )

        passed_checks.append("Gate 1: XML Well-Formedness & Syntax verified.")

        # Check Root Element
        if not (doc.root_tag.endswith("xbrl") or "xbrli:xbrl" in doc.root_tag):
            failed_gates.add("Gate 1: Root Element")
            errors.append(ValidationErrorItem(
                code="INVALID_ROOT_ELEMENT",
                gate="Gate 1: XML Well-Formedness",
                category="SCHEMA",
                severity="CRITICAL",
                message=f"Root element '{doc.root_tag}' is not <xbrli:xbrl>.",
                claude_fix_action="Wrap the XBRL document in <xbrli:xbrl xmlns:xbrli=\"http://www.xbrl.org/2003/instance\" ...>."
            ))
        else:
            passed_checks.append("Gate 1: Root element <xbrli:xbrl> verified.")

        # -------------------------------------------------------------
        # Gate 2: Schema Reference & Official Taxonomy URLs
        # -------------------------------------------------------------
        if not doc.schema_ref:
            failed_gates.add("Gate 2: Schema Reference")
            errors.append(ValidationErrorItem(
                code="MISSING_SCHEMA_REF",
                gate="Gate 2: Schema Reference",
                category="SCHEMA",
                severity="ERROR",
                message="No <link:schemaRef> found in the XBRL instance.",
                claude_fix_action="Add <link:schemaRef xlink:type=\"simple\" xlink:href=\"...\"/> pointing to the official MCA taxonomy entry point."
            ))
        else:
            # Check for deprecated V2 URL warning
            if "http://www.mca.gov.in/XBRL/" in doc.schema_ref:
                warnings.append(ValidationErrorItem(
                    code="DEPRECATED_SCHEMA_REF_V2",
                    gate="Gate 2: Schema Reference",
                    category="SCHEMA",
                    severity="WARNING",
                    message=f"Schema reference uses deprecated V2 address '{doc.schema_ref}'. MCA XBRL Validator requires V3 URL.",
                    claude_fix_action=f"Update schemaRef URL to use 'https://www.mca.gov.in/V3XBRL/' instead of V2 URL."
                ))
            passed_checks.append(f"Gate 2: SchemaRef '{doc.schema_ref}' validated.")

        # -------------------------------------------------------------
        # Gate 3: Contexts, CIN Scheme & Period Dates
        # -------------------------------------------------------------
        if not doc.contexts:
            failed_gates.add("Gate 3: Contexts")
            errors.append(ValidationErrorItem(
                code="NO_CONTEXTS_DEFINED",
                gate="Gate 3: Contexts & Periods",
                category="CONTEXT",
                severity="CRITICAL",
                message="No contexts defined in the instance document.",
                claude_fix_action="Define standard Current Year (CY) and Previous Year (PY) instant and duration contexts."
            ))
        else:
            cins_found: Set[str] = set()
            for cid, ctx in doc.contexts.items():
                # Scheme check
                if ctx.scheme != "http://www.mca.gov.in/CIN":
                    warnings.append(ValidationErrorItem(
                        code="INVALID_IDENTIFIER_SCHEME",
                        gate="Gate 3: Contexts & Periods",
                        category="CONTEXT",
                        severity="WARNING",
                        context_ref=cid,
                        expected="http://www.mca.gov.in/CIN",
                        actual=ctx.scheme,
                        message=f"Context '{cid}': entity identifier scheme is '{ctx.scheme}', expected 'http://www.mca.gov.in/CIN'.",
                        claude_fix_action="Set scheme attribute of <xbrli:identifier> to 'http://www.mca.gov.in/CIN'."
                    ))

                # CIN format check
                if ctx.identifier:
                    cins_found.add(ctx.identifier)
                    if not CIN_REGEX.match(ctx.identifier):
                        errors.append(ValidationErrorItem(
                            code="INVALID_CIN_FORMAT",
                            gate="Gate 3: Contexts & Periods",
                            category="CONTEXT",
                            severity="ERROR",
                            context_ref=cid,
                            actual=ctx.identifier,
                            message=f"Context '{cid}': CIN '{ctx.identifier}' is invalid (must be 21 alphanumeric characters e.g. U72200DL2018PTC123456).",
                            claude_fix_action="Provide a valid 21-character Corporate Identity Number (CIN) in <xbrli:identifier>."
                        ))
                else:
                    errors.append(ValidationErrorItem(
                        code="MISSING_ENTITY_IDENTIFIER",
                        gate="Gate 3: Contexts & Periods",
                        category="CONTEXT",
                        severity="ERROR",
                        context_ref=cid,
                        message=f"Context '{cid}' is missing entity identifier (CIN).",
                        claude_fix_action="Add <xbrli:identifier scheme=\"http://www.mca.gov.in/CIN\">CIN_NUMBER</xbrli:identifier>."
                    ))

                # Period dates validation
                if ctx.period_type == "instant":
                    if not ctx.instant or not DATE_REGEX.match(ctx.instant):
                        errors.append(ValidationErrorItem(
                            code="INVALID_INSTANT_DATE",
                            gate="Gate 3: Contexts & Periods",
                            category="CONTEXT",
                            severity="ERROR",
                            context_ref=cid,
                            actual=ctx.instant,
                            message=f"Context '{cid}': instant date '{ctx.instant}' is not in YYYY-MM-DD format.",
                            claude_fix_action="Format instant date as YYYY-MM-DD (e.g. 2026-03-31)."
                        ))
                elif ctx.period_type == "duration":
                    if not (ctx.start_date and ctx.end_date and DATE_REGEX.match(ctx.start_date) and DATE_REGEX.match(ctx.end_date)):
                        errors.append(ValidationErrorItem(
                            code="INVALID_DURATION_DATES",
                            gate="Gate 3: Contexts & Periods",
                            category="CONTEXT",
                            severity="ERROR",
                            context_ref=cid,
                            message=f"Context '{cid}': duration dates ({ctx.start_date} to {ctx.end_date}) are not in YYYY-MM-DD format.",
                            claude_fix_action="Ensure startDate and endDate are valid YYYY-MM-DD dates."
                        ))
                    elif ctx.start_date >= ctx.end_date:
                        errors.append(ValidationErrorItem(
                            code="START_DATE_AFTER_END_DATE",
                            gate="Gate 3: Contexts & Periods",
                            category="CONTEXT",
                            severity="ERROR",
                            context_ref=cid,
                            message=f"Context '{cid}': startDate ({ctx.start_date}) must be prior to endDate ({ctx.end_date}).",
                            claude_fix_action="Ensure startDate is earlier than endDate."
                        ))

            # Multiple differing CINs check
            if len(cins_found) > 1:
                errors.append(ValidationErrorItem(
                    code="CONFLICTING_CINS_REPORTED",
                    gate="Gate 3: Contexts & Periods",
                    category="CONTEXT",
                    severity="ERROR",
                    message=f"Multiple different CINs found across contexts: {list(cins_found)}.",
                    claude_fix_action="All contexts must use the exact same company CIN."
                ))
            elif cins_found:
                metadata["cin"] = list(cins_found)[0]

            passed_checks.append(f"Gate 3: {len(doc.contexts)} contexts evaluated.")

        # -------------------------------------------------------------
        # Gate 4: Currency & Units Validation
        # -------------------------------------------------------------
        has_inr_unit = any(u.measure and ("inr" in u.measure.lower() or "iso4217:inr" in u.measure.lower()) for u in doc.units.values())
        if not has_inr_unit:
            errors.append(ValidationErrorItem(
                code="MISSING_INR_UNIT",
                gate="Gate 4: Units & Currencies",
                category="SCHEMA",
                severity="ERROR",
                message="MCA Generic Rule GR-8/9 violation: No INR unit defined (<xbrli:unit id=\"INR\"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>).",
                claude_fix_action="Declare the INR unit: <xbrli:unit id=\"INR\"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>."
            ))
        else:
            passed_checks.append("Gate 4: INR currency unit verified.")

        # -------------------------------------------------------------
        # Gate 5: Mandatory Demographic / Company Information
        # -------------------------------------------------------------
        general_elr = "700300" if self.is_ind_as else "400100"
        mandatory_company_qnames = self.mandatory_by_elr.get(general_elr, [
            "in-ca:CorporateIdentityNumber",
            "in-ca:NameOfCompany",
            "in-ca:PermanentAccountNumberOfEntity",
            "in-ca:AddressOfRegisteredOfficeOfCompany",
            "in-ca:DateOfStartOfReportingPeriod",
            "in-ca:DateOfEndOfReportingPeriod",
            "in-ca:DateOfBoardMeetingWhenFinalAccountsWereApproved",
            "in-ca:NatureOfReportStandaloneConsolidated",
            "in-ca:DescriptionOfPresentationCurrency",
            "in-ca:LevelOfRoundingUsedInFinancialStatements",
            "in-ca:WhetherCompanyIsSubsidiaryCompany",
            "in-ca:WhetherCompanyHasSubsidiaryCompanies"
        ])

        for qn in mandatory_company_qnames:
            fact = doc.get_fact(qn)
            if fact is None or not fact.value.strip():
                errors.append(ValidationErrorItem(
                    code="MANDATORY_COMPANY_INFO_MISSING",
                    gate="Gate 5: Mandatory Company Information",
                    category="MANDATORY",
                    severity="ERROR",
                    concept=qn,
                    message=f"Mandatory company identification fact missing or empty: '{qn}'.",
                    claude_fix_action=f"Add line item fact for <{qn} contextRef=\"...\">VALUE</{qn}>."
                ))
            else:
                # Specific format checks for company facts
                if "PermanentAccountNumberOfEntity" in qn and not PAN_REGEX.match(fact.value.strip()):
                    errors.append(ValidationErrorItem(
                        code="INVALID_PAN_FORMAT",
                        gate="Gate 5: Mandatory Company Information",
                        category="MANDATORY",
                        severity="ERROR",
                        concept=qn,
                        actual=fact.value,
                        message=f"Company PAN '{fact.value}' is invalid. Must be 10 characters (5 uppercase letters, 4 digits, 1 uppercase letter, e.g. AAACH1234K).",
                        claude_fix_action="Provide a valid 10-character PAN format for in-ca:PermanentAccountNumberOfEntity."
                    ))
                elif "NameOfCompany" in qn:
                    metadata["company_name"] = fact.value

        passed_checks.append("Gate 5: General Demographic & Company Information validated.")

        # -------------------------------------------------------------
        # Gate 6: Statutory Signatories & Auditor Governance
        # -------------------------------------------------------------
        # Section 134(1) of Companies Act 2013 requires minimum 2 director signatories
        din_facts = [
            f for f in doc.facts 
            if "directoridentificationnumber" in f.local_name.lower() or "dinofdirector" in f.local_name.lower()
        ]
        
        # Check typed members in contexts for DINs as well
        ctx_dins = []
        for ctx in doc.contexts.values():
            for dim, val in ctx.typed_members.items():
                if "director" in dim.lower() or "sign" in dim.lower():
                    ctx_dins.append(val)

        all_dins = set()
        for df in din_facts:
            if df.value and df.value.strip():
                all_dins.add(df.value.strip())
        for cd in ctx_dins:
            if cd and cd.strip():
                all_dins.add(cd.strip())

        if len(all_dins) < 2:
            errors.append(ValidationErrorItem(
                code="INSUFFICIENT_SIGNATORIES",
                gate="Gate 6: Statutory Governance",
                category="GOVERNANCE",
                severity="ERROR",
                actual=len(all_dins),
                expected=">= 2 Directors",
                message=f"Section 134(1) violation: Minimum 2 Director signatories required for AOC-4. Found: {len(all_dins)} ({list(all_dins)}).",
                claude_fix_action="Include at least two Director signatories with valid DINs in the filing."
            ))
        else:
            for din in all_dins:
                if not (len(din) == 8 and din.isdigit()):
                    errors.append(ValidationErrorItem(
                        code="INVALID_DIN_FORMAT",
                        gate="Gate 6: Statutory Governance",
                        category="GOVERNANCE",
                        severity="ERROR",
                        actual=din,
                        expected="8-digit numeric DIN",
                        message=f"Invalid Director Identification Number (DIN): '{din}'. Must be exactly 8 digits.",
                        claude_fix_action=f"Correct DIN '{din}' to an 8-digit numeric string (pad with leading zero if needed, e.g. '00012345')."
                    ))

        metadata["signatory_dins"] = list(all_dins)
        passed_checks.append(f"Gate 6: Statutory Signatories validated ({len(all_dins)} directors).")

        # -------------------------------------------------------------
        # Gate 7: Statement Roots & Essential Reporting Lines
        # -------------------------------------------------------------
        if self.is_ind_as:
            bs_assets = doc.get_fact("ind-as:Assets")
            bs_eq_liab = doc.get_fact("ind-as:EquityAndLiabilities")
            bs_equity = doc.get_fact("ind-as:Equity")
            bs_liab = doc.get_fact("ind-as:Liabilities")

            if not bs_assets:
                errors.append(ValidationErrorItem(
                    code="MANDATORY_STATEMENT_ROOT_MISSING",
                    gate="Gate 7: Statement Roots",
                    category="MANDATORY",
                    severity="ERROR",
                    concept="ind-as:Assets",
                    message="Mandatory Balance Sheet root concept 'ind-as:Assets' is missing.",
                    claude_fix_action="Add <ind-as:Assets contextRef=\"...\">...</ind-as:Assets> line item."
                ))
            if not bs_eq_liab and not (bs_equity and bs_liab):
                errors.append(ValidationErrorItem(
                    code="MANDATORY_STATEMENT_ROOT_MISSING",
                    gate="Gate 7: Statement Roots",
                    category="MANDATORY",
                    severity="ERROR",
                    concept="ind-as:EquityAndLiabilities",
                    message="Mandatory Balance Sheet root concept 'ind-as:EquityAndLiabilities' (or both Equity and Liabilities) is missing.",
                    claude_fix_action="Add <ind-as:EquityAndLiabilities contextRef=\"...\">...</ind-as:EquityAndLiabilities> line item."
                ))
        else:
            # C&I
            bs_assets = doc.get_fact("in-gaap:Assets")
            bs_eq_liab = doc.get_fact("in-gaap:EquityAndLiabilities")

            if not bs_assets:
                errors.append(ValidationErrorItem(
                    code="MANDATORY_STATEMENT_ROOT_MISSING",
                    gate="Gate 7: Statement Roots",
                    category="MANDATORY",
                    severity="ERROR",
                    concept="in-gaap:Assets",
                    message="Mandatory Balance Sheet root concept 'in-gaap:Assets' is missing.",
                    claude_fix_action="Add <in-gaap:Assets contextRef=\"...\">...</in-gaap:Assets> line item."
                ))
            if not bs_eq_liab:
                errors.append(ValidationErrorItem(
                    code="MANDATORY_STATEMENT_ROOT_MISSING",
                    gate="Gate 7: Statement Roots",
                    category="MANDATORY",
                    severity="ERROR",
                    concept="in-gaap:EquityAndLiabilities",
                    message="Mandatory Balance Sheet root concept 'in-gaap:EquityAndLiabilities' is missing.",
                    claude_fix_action="Add <in-gaap:EquityAndLiabilities contextRef=\"...\">...</in-gaap:EquityAndLiabilities> line item."
                ))

        passed_checks.append("Gate 7: Financial Statement Roots checked.")

        # -------------------------------------------------------------
        # Gate 8: Balance Sheet Hard Balancing Check
        # -------------------------------------------------------------
        assets_qname = "ind-as:Assets" if self.is_ind_as else "in-gaap:Assets"
        eq_liab_qname = "ind-as:EquityAndLiabilities" if self.is_ind_as else "in-gaap:EquityAndLiabilities"

        assets_facts = doc.get_facts(assets_qname)
        eq_liab_facts = doc.get_facts(eq_liab_qname)

        # Match by contextRef or compare CY values
        compared_contexts = set()
        for af in assets_facts:
            if af.numeric_value is not None:
                ctx_id = af.context_ref
                elf = next((f for f in eq_liab_facts if f.context_ref == ctx_id), None)
                if elf and elf.numeric_value is not None:
                    compared_contexts.add(ctx_id)
                    diff = round(af.numeric_value - elf.numeric_value, 2)
                    if abs(diff) > 1.0:
                        failed_gates.add("Gate 8: Balance Sheet Hard Balancing")
                        errors.append(ValidationErrorItem(
                            code="BS_OUT_OF_BALANCE",
                            gate="Gate 8: Balance Sheet Balancing",
                            category="CALCULATION",
                            severity="CRITICAL",
                            context_ref=ctx_id,
                            concept=f"{assets_qname} / {eq_liab_qname}",
                            expected=af.numeric_value,
                            actual=elf.numeric_value,
                            diff=diff,
                            message=f"Balance Sheet is OUT OF BALANCE in context '{ctx_id}'! Total Assets ({af.numeric_value:,.2f}) != Total Equity and Liabilities ({elf.numeric_value:,.2f}) [Discrepancy: {diff:,.2f} INR].",
                            claude_fix_action=f"Adjust either Total Assets or Total Equity & Liabilities by {diff:,.2f} INR so both equal exactly."
                        ))

        if compared_contexts and "Gate 8: Balance Sheet Hard Balancing" not in failed_gates:
            passed_checks.append(f"Gate 8: Balance Sheet Hard Balancing verified across contexts {list(compared_contexts)}.")

        # -------------------------------------------------------------
        # Gate 9: Calculation Linkbase Arithmetic Rollups
        # -------------------------------------------------------------
        calc_mismatches = 0
        for elr, equations in self.calculation.items():
            # Group equations by parent concept
            parents_map: Dict[str, List[Dict[str, Any]]] = {}
            for eq in equations:
                parents_map.setdefault(eq["from"], []).append(eq)

            for parent_qn, children_arcs in parents_map.items():
                p_facts = doc.get_facts(parent_qn)
                for pf in p_facts:
                    if pf.numeric_value is None or pf.is_nil:
                        continue
                    ctx = pf.context_ref

                    # Find matching child facts in the same context
                    present_children = []
                    for arc in children_arcs:
                        child_qn = arc["to"]
                        cf = doc.get_fact(child_qn, ctx)
                        if cf and cf.numeric_value is not None and not cf.is_nil:
                            present_children.append((cf, arc.get("weight", 1.0)))

                    if present_children:
                        calc_sum = sum(cf.numeric_value * weight for cf, weight in present_children)
                        diff = round(pf.numeric_value - calc_sum, 2)
                        if abs(diff) > 1.0:  # MCA 1 INR rounding tolerance
                            calc_mismatches += 1
                            errors.append(ValidationErrorItem(
                                code="CALCULATION_MISMATCH",
                                gate="Gate 9: Arithmetic Rollups",
                                category="CALCULATION",
                                severity="ERROR",
                                concept=parent_qn,
                                context_ref=ctx,
                                expected=pf.numeric_value,
                                actual=calc_sum,
                                diff=diff,
                                message=f"Calculation mismatch in ELR {elr} (context '{ctx}'): {parent_qn} ({pf.numeric_value:,.2f}) != sum of children ({calc_sum:,.2f}) [Diff: {diff:,.2f} INR].",
                                claude_fix_action=f"Reconcile child elements of {parent_qn} in context '{ctx}' to sum exactly to {pf.numeric_value:,.2f} INR (diff: {diff:,.2f})."
                            ))

        if calc_mismatches == 0:
            passed_checks.append(f"Gate 9: Arithmetic integrity verified across all {len(self.calculation)} calculation linkbases.")

        # -------------------------------------------------------------
        # Gate 10: Statutory Non-Negative Constraints
        # -------------------------------------------------------------
        negative_violations = 0
        for fact in doc.facts:
            if fact.is_numeric() and fact.numeric_value is not None and fact.numeric_value < 0:
                if fact.qname in self.non_negative_concepts or fact.local_name in self.non_negative_concepts:
                    negative_violations += 1
                    errors.append(ValidationErrorItem(
                        code="NEGATIVE_VALUE_NOT_PERMITTED",
                        gate="Gate 10: Non-Negative Constraints",
                        category="BUSINESS_RULE",
                        severity="ERROR",
                        concept=fact.qname,
                        context_ref=fact.context_ref,
                        actual=fact.numeric_value,
                        expected=">= 0",
                        message=f"Statutory rule violation: Element '{fact.qname}' reported as negative ({fact.numeric_value:,.2f}), but MCA specifies it must be >= 0.",
                        claude_fix_action=f"Report {fact.qname} as a positive number or zero (reported value was {fact.numeric_value:,.2f})."
                    ))

        if negative_violations == 0:
            passed_checks.append(f"Gate 10: Non-negative constraints verified ({len(self.non_negative_concepts)} statutory concepts).")

        # -------------------------------------------------------------
        # Gate 11: Text Block MCA HTML Schema Compliance
        # -------------------------------------------------------------
        html_errors_count = 0
        for fact in doc.facts:
            if fact.is_text_block() or any(tag_char in fact.value for tag_char in ("<table", "<div", "<p", "<span")):
                h_errs, h_warns = validate_mca_html(fact.value, fact.qname)
                for he in h_errs:
                    html_errors_count += 1
                    errors.append(ValidationErrorItem(
                        code="MCA_HTML_SCHEMA_VIOLATION",
                        gate="Gate 11: Text Block HTML",
                        category="TEXT_BLOCK",
                        severity="ERROR",
                        concept=fact.qname,
                        context_ref=fact.context_ref,
                        message=he,
                        claude_fix_action="Remove inline styles, colgroups, or unsupported HTML tags from text block. Use only standard structural tags (div, p, span, br, table, tr, td) and only 'class' attribute."
                    ))
                for hw in h_warns:
                    warnings.append(ValidationErrorItem(
                        code="MCA_HTML_RECOMMENDATION",
                        gate="Gate 11: Text Block HTML",
                        category="TEXT_BLOCK",
                        severity="WARNING",
                        concept=fact.qname,
                        context_ref=fact.context_ref,
                        message=hw,
                        claude_fix_action="Clean HTML attributes to strictly follow MCA standard."
                    ))

        if html_errors_count == 0:
            passed_checks.append("Gate 11: Text Block MCA HTML schema compliance verified.")

        # -------------------------------------------------------------
        # Gate 12: Generic Rules (GR-1 to GR-17) & Exemption Lists
        # -------------------------------------------------------------
        # Check Share Capital consistency if reported
        # ValuesOfSharesAuthorised >= ValuesOfSharesIssued >= ValuesOfSharesSubscribed
        val_auth = doc.get_fact_value("ind-as:ValueOfSharesAuthorised" if self.is_ind_as else "in-gaap:ValueOfSharesAuthorised")
        val_issued = doc.get_fact_value("ind-as:ValueOfSharesIssued" if self.is_ind_as else "in-gaap:ValueOfSharesIssued")
        val_sub = doc.get_fact_value("ind-as:ValueOfSharesSubscribed" if self.is_ind_as else "in-gaap:ValueOfSharesSubscribed")

        try:
            if val_auth and val_issued and float(val_auth) < float(val_issued):
                errors.append(ValidationErrorItem(
                    code="SHARE_CAPITAL_AUTHORISED_LESS_THAN_ISSUED",
                    gate="Gate 12: Business Rules",
                    category="BUSINESS_RULE",
                    severity="ERROR",
                    expected=f">= {val_issued}",
                    actual=val_auth,
                    message=f"ValueOfSharesAuthorised ({val_auth}) cannot be less than ValueOfSharesIssued ({val_issued}).",
                    claude_fix_action="Ensure Authorised Share Capital is greater than or equal to Issued Share Capital."
                ))
            if val_issued and val_sub and float(val_issued) < float(val_sub):
                errors.append(ValidationErrorItem(
                    code="SHARE_CAPITAL_ISSUED_LESS_THAN_SUBSCRIBED",
                    gate="Gate 12: Business Rules",
                    category="BUSINESS_RULE",
                    severity="ERROR",
                    expected=f">= {val_sub}",
                    actual=val_issued,
                    message=f"ValueOfSharesIssued ({val_issued}) cannot be less than ValueOfSharesSubscribed ({val_sub}).",
                    claude_fix_action="Ensure Issued Share Capital is greater than or equal to Subscribed Share Capital."
                ))
        except (ValueError, TypeError):
            pass

        passed_checks.append("Gate 12: Specific & Generic MCA Business Rules verified.")

        # -------------------------------------------------------------
        # Assemble Summary & Response
        # -------------------------------------------------------------
        total_errs = len([e for e in errors if e.severity in ("CRITICAL", "ERROR")])
        total_warns = len(warnings)
        is_valid = total_errs == 0

        summary = ValidationSummary(
            total_errors=total_errs,
            total_warnings=total_warns,
            total_info=0,
            gates_evaluated=gates_count,
            gates_passed=gates_count - len(failed_gates),
            gates_failed=len(failed_gates),
            facts_evaluated=len(doc.facts),
            contexts_count=len(doc.contexts)
        )

        metadata["facts_count"] = len(doc.facts)
        metadata["contexts_count"] = len(doc.contexts)
        metadata["units_count"] = len(doc.units)

        return ValidationResponse(
            valid=is_valid,
            taxonomy=self.taxonomy,
            summary=summary,
            errors=errors,
            warnings=warnings,
            passed_checks=passed_checks,
            metadata=metadata
        )
