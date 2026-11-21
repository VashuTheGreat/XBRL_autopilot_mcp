"""Taxonomy & Knowledge Base data loader.

Loads official MCA taxonomies for:
1. Ind-AS (2017)
2. Commercial & Industrial / C&I (2016)
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TaxonomyDataLoader:
    """Manages loaded taxonomy rules, concepts, calculations, and constraints."""

    def __init__(self):
        self._ind_as_kb: Optional[Dict[str, Any]] = None
        self._ci_kb: Optional[Dict[str, Any]] = None

    def get_ind_as_kb(self) -> Dict[str, Any]:
        """Loads and returns Ind-AS knowledge base."""
        if self._ind_as_kb is None:
            path = DATA_DIR / "ind_as_knowledge_base.json"
            if not path.exists():
                raise FileNotFoundError(f"Ind-AS KB file not found at: {path}")
            with open(path, "r", encoding="utf-8") as f:
                self._ind_as_kb = json.load(f)
        return self._ind_as_kb

    def get_ci_kb(self) -> Dict[str, Any]:
        """Loads and returns C&I knowledge base."""
        if self._ci_kb is None:
            path = DATA_DIR / "ci_knowledge_base.json"
            if not path.exists():
                raise FileNotFoundError(f"C&I KB file not found at: {path}")
            with open(path, "r", encoding="utf-8") as f:
                self._ci_kb = json.load(f)
        return self._ci_kb

    def get_kb(self, taxonomy: str) -> Dict[str, Any]:
        """Returns the appropriate KB given taxonomy name ('indas' or 'ci')."""
        t = taxonomy.lower().replace("-", "").replace("_", "")
        if "indas" in t or "ind" in t:
            return self.get_ind_as_kb()
        elif "ci" in t or "cni" in t or "gaap" in t:
            return self.get_ci_kb()
        else:
            raise ValueError(f"Unsupported taxonomy: '{taxonomy}'. Must be 'indas' or 'ci'.")


loader = TaxonomyDataLoader()
