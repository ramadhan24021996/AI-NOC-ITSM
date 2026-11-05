"""
Obsidian Vault Markdown & Frontmatter Parser for AI NOC ITSM System.
Provides production-ready, zero-crash parsing of Obsidian Markdown files (.md),
extracting YAML Frontmatter, Obsidian Bi-directional Backlinks [[Link]], and Markdown content.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ObsidianVaultParser")

try:
    import yaml
except ImportError:
    yaml = None


class ObsidianVaultParser:
    """
    Production-ready parser for Obsidian Vault files (.md).
    Guarantees isolated exception handling (0% server crash risk on malformed files).
    """

    # Obsidian Bi-directional Link Pattern: [[TargetDoc]] or [[TargetDoc|Display Name]]
    BACKLINK_PATTERN = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]")

    @classmethod
    def parse_frontmatter_fallback(cls, yaml_str: str) -> Dict[str, Any]:
        """
        Simple key-value string parser for YAML frontmatter if PyYAML is unavailable.
        Handles key: value, lists (- item), and strings safely.
        """
        result: Dict[str, Any] = {}
        lines = yaml_str.strip().splitlines()
        current_list_key = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if line.startswith("  - ") or line.startswith("- "):
                val = line.split("-", 1)[1].strip().strip("\"'")
                if current_list_key and isinstance(result.get(current_list_key), list):
                    result[current_list_key].append(val)
                continue

            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip("\"'")

                if not val:
                    # Might be start of list
                    result[key] = []
                    current_list_key = key
                else:
                    # Check for float / int / bool
                    if val.lower() == "true":
                        result[key] = True
                    elif val.lower() == "false":
                        result[key] = False
                    else:
                        try:
                            if "." in val:
                                result[key] = float(val)
                            else:
                                result[key] = int(val)
                        except ValueError:
                            result[key] = val
                    current_list_key = None

        return result

    @classmethod
    def parse_file(cls, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parses a single Obsidian Markdown file safely.
        Returns a structured dictionary or None if reading fails.
        """
        path = Path(file_path)
        if not path.is_file() or not path.name.endswith(".md"):
            logger.debug("Skipping non-markdown file: %s", file_path)
            return None

        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.error("Failed to read file '%s': %s", file_path, e)
            return None

        frontmatter: Dict[str, Any] = {}
        markdown_body = content

        # Check for YAML Frontmatter block bounded by ---
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                raw_yaml = parts[1]
                markdown_body = parts[2]
                try:
                    if yaml is not None:
                        parsed = yaml.safe_load(raw_yaml)
                        if isinstance(parsed, dict):
                            frontmatter = parsed
                        else:
                            frontmatter = cls.parse_frontmatter_fallback(raw_yaml)
                    else:
                        frontmatter = cls.parse_frontmatter_fallback(raw_yaml)
                except Exception as ye:
                    logger.warning("Malformed YAML frontmatter in '%s' (%s). Using fallback parser.", file_path, ye)
                    try:
                        frontmatter = cls.parse_frontmatter_fallback(raw_yaml)
                    except Exception as fe:
                        logger.error("Fallback YAML parser failed for '%s': %s", file_path, fe)
                        frontmatter = {}

        # Extract Obsidian Backlinks [[Link]]
        backlinks: List[str] = []
        for match in cls.BACKLINK_PATTERN.finditer(markdown_body):
            target = match.group(1).strip()
            if target and target not in backlinks:
                backlinks.append(target)

        # Categorize document type
        doc_type = "UNKNOWN"
        if "sop_id" in frontmatter:
            doc_type = "SOP"
        elif "incident_id" in frontmatter:
            doc_type = "INCIDENT"
        elif "title" in frontmatter:
            doc_type = "KNOWLEDGE"

        return {
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "doc_type": doc_type,
            "frontmatter": frontmatter,
            "markdown_body": markdown_body.strip(),
            "backlinks": backlinks
        }

    @classmethod
    def scan_vault(cls, vault_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Recursively scans an Obsidian Vault directory for .md files.
        Categorizes documents into 'sops', 'incidents', and 'knowledge'.
        """
        vault_path = Path(vault_dir)
        catalog: Dict[str, List[Dict[str, Any]]] = {
            "sops": [],
            "incidents": [],
            "knowledge": [],
            "all": []
        }

        if not vault_path.exists() or not vault_path.is_dir():
            logger.warning("Obsidian Vault directory does not exist: %s", vault_dir)
            return catalog

        for md_file in vault_path.rglob("*.md"):
            parsed = cls.parse_file(str(md_file))
            if not parsed:
                continue

            catalog["all"].append(parsed)
            doc_type = parsed["doc_type"]
            if doc_type == "SOP":
                catalog["sops"].append(parsed)
            elif doc_type == "INCIDENT":
                catalog["incidents"].append(parsed)
            else:
                catalog["knowledge"].append(parsed)

        logger.info("Scanned Obsidian Vault at '%s': Loaded %d SOPs, %d Incidents, %d Knowledge docs.",
                    vault_dir, len(catalog["sops"]), len(catalog["incidents"]), len(catalog["knowledge"]))
        return catalog


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample_vault = "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/obsidian_vault"
    res = ObsidianVaultParser.scan_vault(sample_vault)
    print("SOPs Found:", [s["frontmatter"].get("sop_id") for s in res["sops"]])
    print("Incidents Found:", [i["frontmatter"].get("incident_id") for i in res["incidents"]])
