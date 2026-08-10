"""
Canadian Corporate CSV Data Processor

Downloads and parses public Canadian business CSV datasets from government registries
(Statistics Canada, Corporations Canada, provincial registries) and exports the
results to CSV and JSON formats.
"""

import csv
import json
import logging
import os
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

import requests

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data source configuration
# ---------------------------------------------------------------------------

# Public Canadian government open-data CSV endpoints.
# These are real URLs; a local fallback file is used when downloads fail.
DATA_SOURCES = {
    "corporations_canada": {
        "url": (
            "https://open.canada.ca/data/en/dataset/"
            "c1b2a820-8e59-4f56-a84c-bb7e0a1c79d5"
        ),
        "description": "Corporations Canada – federal incorporations dataset",
        "column_map": {
            "company_name": "Corporation Name",
            "registration_number": "Corporation Number",
            "status": "Status",
            "incorporation_date": "Date of Incorporation",
            "province": "Province / Territory",
            "address": "Registered Office Address",
        },
    },
    "statistics_canada": {
        "url": "https://www150.statcan.gc.ca/n1/pub/71-607-x/71-607-x2018013-eng.htm",
        "description": "Statistics Canada Business Register – public extract",
        "column_map": {
            "company_name": "Business Name",
            "registration_number": "Business Number",
            "status": "Operating Status",
            "incorporation_date": "Start Date",
            "province": "Province",
            "industry": "NAICS Description",
        },
    },
}

# Canonical province mapping used for normalisation
PROVINCE_CODES: Dict[str, str] = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}

# Reverse map: full name → code
_PROVINCE_NAME_TO_CODE: Dict[str, str] = {v.lower(): k for k, v in PROVINCE_CODES.items()}

# Status values considered "active"
ACTIVE_STATUSES = {"active", "in good standing", "registered", "operating"}

# Required output fields
OUTPUT_FIELDS = [
    "company_name",
    "registration_number",
    "status",
    "province",
    "incorporation_date",
    "address",
    "phone",
    "email",
    "industry",
    "directors",
    "bank_name",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _normalise_province(raw: str) -> str:
    """Return the two-letter province code for a raw province string."""
    if not raw:
        return ""
    cleaned = str(raw).strip()
    if cleaned.upper() in PROVINCE_CODES:
        return cleaned.upper()
    code = _PROVINCE_NAME_TO_CODE.get(cleaned.lower())
    return code if code else cleaned


def _normalise_status(raw: str) -> str:
    """Return a consistent status string."""
    if not raw:
        return "Unknown"
    cleaned = str(raw).strip().lower()
    if cleaned in ACTIVE_STATUSES:
        return "Active"
    if "dissolv" in cleaned or "cancel" in cleaned or "struck" in cleaned:
        return "Dissolved"
    if "suspend" in cleaned or "inactive" in cleaned:
        return "Inactive"
    return str(raw).strip().title()


def _clean_text(value) -> str:
    """Return a stripped string, or empty string for missing values."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "n/a", "na", "") else text


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class CSVDataScraper:
    """
    Processes public Canadian business CSV datasets.

    Workflow:
        1. Load CSV data from a URL or a local file path.
        2. Parse and normalise the rows into a canonical schema.
        3. Optionally filter by province, industry, status, or company name.
        4. Export the results to CSV and/or JSON.
    """

    def __init__(
        self,
        output_dir: str = "./output",
        max_records: int = 2000,
    ):
        """
        Args:
            output_dir:   Directory where output files are written.
            max_records:  Maximum number of records to retain after parsing.
        """
        self.output_dir = Path(output_dir)
        self.max_records = max_records
        self.companies: List[Dict] = []
        self._raw_df = None  # type: ignore[assignment]

        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def download_dataset(self, url: str, local_path: str) -> bool:
        """
        Download a CSV file from *url* and save it to *local_path*.

        Returns True on success, False on failure.
        """
        try:
            logger.info("Downloading dataset from %s …", url)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(response.text)
            logger.info("Saved dataset to %s", local_path)
            return True
        except Exception as exc:
            logger.warning("Could not download dataset from %s: %s", url, exc)
            return False

    def load_csv(self, path: str) -> bool:
        """
        Load a CSV file from disk into an internal DataFrame.

        Returns True on success, False on failure.
        """
        if pd is None:
            logger.error("pandas is required. Install it with: pip install pandas")
            return False
        try:
            logger.info("Loading CSV from %s", path)
            self._raw_df = pd.read_csv(path, dtype=str, keep_default_na=False)
            logger.info(
                "Loaded %d rows with columns: %s",
                len(self._raw_df),
                list(self._raw_df.columns),
            )
            return True
        except Exception as exc:
            logger.error("Failed to load CSV from %s: %s", path, exc)
            return False

    def load_from_string(self, csv_text: str) -> bool:
        """Load CSV data directly from a string (useful for testing)."""
        if pd is None:
            logger.error("pandas is required.")
            return False
        try:
            self._raw_df = pd.read_csv(
                StringIO(csv_text), dtype=str, keep_default_na=False
            )
            return True
        except Exception as exc:
            logger.error("Failed to parse CSV string: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Parsing / transformation
    # ------------------------------------------------------------------

    def parse_companies(
        self, column_map: Optional[Dict[str, str]] = None
    ) -> List[Dict]:
        """
        Transform the raw DataFrame into the canonical company schema.

        Args:
            column_map: Mapping of canonical field names to actual CSV column
                        headers. When omitted the scraper tries common aliases.

        Returns:
            List of company dicts in the canonical schema.
        """
        if pd is None or self._raw_df is None:
            logger.error("No data loaded. Call load_csv() or load_from_string() first.")
            return []

        df = self._raw_df.copy()
        df.columns = [c.strip() for c in df.columns]

        col_map = column_map or self._guess_column_map(df.columns.tolist())
        logger.debug("Using column map: %s", col_map)

        companies: List[Dict] = []

        for _, row in df.iterrows():
            if len(companies) >= self.max_records:
                break

            company = self._map_row(row, col_map)
            if not company.get("company_name"):
                continue
            if self._validate(company):
                companies.append(company)
            else:
                logger.debug("Skipping invalid row: %s", dict(row))

        self.companies = companies
        logger.info("Parsed %d valid companies from dataset.", len(companies))
        return companies

    def _guess_column_map(self, columns: List[str]) -> Dict[str, str]:
        """Build a best-effort column map from known aliases."""
        aliases: Dict[str, List[str]] = {
            "company_name": [
                "corporation name", "business name", "company name", "name",
                "legal name", "registered name",
            ],
            "registration_number": [
                "corporation number", "business number", "registration number",
                "reg number", "reg_number", "corp number",
            ],
            "status": ["status", "operating status", "corporation status"],
            "province": [
                "province", "province / territory", "province/territory",
                "prov", "jurisdiction",
            ],
            "incorporation_date": [
                "date of incorporation", "incorporation date", "start date",
                "registration date", "date incorporated",
            ],
            "address": [
                "registered office address", "address", "street address",
                "mailing address", "office address",
            ],
            "phone": ["phone", "telephone", "phone number", "tel"],
            "email": ["email", "e-mail", "email address", "contact email"],
            "industry": [
                "industry", "naics description", "sector", "industry sector",
                "business type",
            ],
            "directors": [
                "directors", "director names", "officers", "key officers",
            ],
            "bank_name": ["bank", "bank name", "financial institution"],
        }

        lower_cols = {c.lower(): c for c in columns}
        col_map: Dict[str, str] = {}

        for field, candidates in aliases.items():
            for candidate in candidates:
                if candidate in lower_cols:
                    col_map[field] = lower_cols[candidate]
                    break

        return col_map

    def _map_row(self, row, col_map: Dict[str, str]) -> Dict:
        """Map a single DataFrame row to the canonical schema."""
        def get(field: str) -> str:
            col = col_map.get(field)
            if col and col in row.index:
                return _clean_text(row[col])
            return ""

        company = {
            "company_name": get("company_name"),
            "registration_number": get("registration_number"),
            "status": _normalise_status(get("status")),
            "province": _normalise_province(get("province")),
            "incorporation_date": get("incorporation_date"),
            "address": get("address"),
            "phone": get("phone"),
            "email": get("email"),
            "industry": get("industry"),
            "directors": get("directors"),
            "bank_name": get("bank_name"),
        }
        return company

    @staticmethod
    def _validate(company: Dict) -> bool:
        """Return True if the company record passes basic validation."""
        if not company.get("company_name"):
            return False
        name = company["company_name"]
        if len(name) < 2 or len(name) > 300:
            return False
        return True

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_by_province(
        self, province: str, companies: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Filter companies by province code (e.g. 'ON') or full name."""
        data = companies if companies is not None else self.companies
        code = _normalise_province(province)
        filtered = [c for c in data if c.get("province") == code]
        logger.info(
            "filter_by_province('%s'): %d → %d records", province, len(data), len(filtered)
        )
        return filtered

    def filter_by_industry(
        self, industry: str, companies: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Filter companies whose industry field contains *industry* (case-insensitive)."""
        data = companies if companies is not None else self.companies
        needle = industry.lower()
        filtered = [c for c in data if needle in c.get("industry", "").lower()]
        logger.info(
            "filter_by_industry('%s'): %d → %d records", industry, len(data), len(filtered)
        )
        return filtered

    def filter_by_status(
        self, status: str, companies: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Filter companies by normalised status (e.g. 'Active', 'Dissolved')."""
        data = companies if companies is not None else self.companies
        needle = status.lower()
        filtered = [c for c in data if c.get("status", "").lower() == needle]
        logger.info(
            "filter_by_status('%s'): %d → %d records", status, len(data), len(filtered)
        )
        return filtered

    def filter_by_company_name(
        self, company_name: str, companies: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Filter companies by exact or partial company name match (case-insensitive)."""
        data = companies if companies is not None else self.companies
        needle = company_name.lower()
        filtered = [c for c in data if needle in c.get("company_name", "").lower()]
        logger.info(
            "filter_by_company_name('%s'): %d → %d records", company_name, len(data), len(filtered)
        )
        return filtered

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_to_csv(
        self,
        companies: Optional[List[Dict]] = None,
        filename: str = "companies_2k.csv",
    ) -> str:
        """
        Write companies to a CSV file in the output directory.

        Returns the full path of the written file.
        """
        data = companies if companies is not None else self.companies
        if not data:
            logger.warning("No companies to export to CSV.")
            return ""

        out_path = self.output_dir / filename
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(data)
            logger.info("Exported %d companies to %s", len(data), out_path)
            return str(out_path)
        except Exception as exc:
            logger.error("Failed to write CSV: %s", exc)
            return ""

    def export_to_json(
        self,
        companies: Optional[List[Dict]] = None,
        filename: str = "companies_2k.json",
    ) -> str:
        """
        Write companies to a JSON file in the output directory.

        Returns the full path of the written file.
        """
        data = companies if companies is not None else self.companies
        if not data:
            logger.warning("No companies to export to JSON.")
            return ""

        out_path = self.output_dir / filename
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            logger.info("Exported %d companies to %s", len(data), out_path)
            return str(out_path)
        except Exception as exc:
            logger.error("Failed to write JSON: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # High-level pipeline
    # ------------------------------------------------------------------

    def run(
        self,
        source_path: str,
        column_map: Optional[Dict[str, str]] = None,
        filter_province: Optional[str] = None,
        filter_industry: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_company_name: Optional[str] = None,
        csv_filename: str = "companies_2k.csv",
        json_filename: str = "companies_2k.json",
    ) -> List[Dict]:
        """
        Full pipeline: load → parse → filter → export.

        Args:
            source_path:         Path to the input CSV file.
            column_map:          Optional column mapping override.
            filter_province:     If set, keep only this province.
            filter_industry:     If set, keep only records matching this industry.
            filter_status:       If set, keep only records with this status.
            filter_company_name: If set, keep only records matching this company name.
            csv_filename:        Output CSV filename.
            json_filename:       Output JSON filename.

        Returns:
            List of processed company dicts.
        """
        if not self.load_csv(source_path):
            return []

        companies = self.parse_companies(column_map)

        if filter_company_name:
            companies = self.filter_by_company_name(filter_company_name, companies)
        if filter_province:
            companies = self.filter_by_province(filter_province, companies)
        if filter_industry:
            companies = self.filter_by_industry(filter_industry, companies)
        if filter_status:
            companies = self.filter_by_status(filter_status, companies)

        self.companies = companies[: self.max_records]

        self.export_to_csv(self.companies, csv_filename)
        self.export_to_json(self.companies, json_filename)

        return self.companies


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Parse public Canadian business CSV datasets."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "data", "sample_companies.csv"),
        help="Path to the input CSV file (default: data/sample_companies.csv)",
    )
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--company", help="Filter by company name (e.g. RBC)")
    parser.add_argument("--province", help="Filter by province code (e.g. ON)")
    parser.add_argument("--industry", help="Filter by industry keyword")
    parser.add_argument("--status", default="Active", help="Filter by status (default: Active)")
    parser.add_argument("--max", type=int, default=2000, help="Maximum records (default: 2000)")
    parser.add_argument(
        "--csv-out", default="companies_2k.csv", help="Output CSV filename"
    )
    parser.add_argument(
        "--json-out", default="companies_2k.json", help="Output JSON filename"
    )

    args = parser.parse_args()

    scraper = CSVDataScraper(output_dir=args.output_dir, max_records=args.max)
    results = scraper.run(
        source_path=args.source,
        filter_company_name=args.company,
        filter_province=args.province,
        filter_industry=args.industry,
        filter_status=args.status,
        csv_filename=args.csv_out,
        json_filename=args.json_out,
    )

    print(f"\n✓ Processed {len(results)} companies.")
    print(f"  CSV  → {args.output_dir}/{args.csv_out}")
    print(f"  JSON → {args.output_dir}/{args.json_out}")


if __name__ == "__main__":
    main()
