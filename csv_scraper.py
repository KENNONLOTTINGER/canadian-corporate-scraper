"""
Canadian Corporate CSV Data Processor

Downloads and parses public Canadian business CSV datasets from government registries
(Statistics Canada, Corporations Canada, provincial registries) and exports the
results to CSV and JSON formats.

RBC scraping: use ``fetch_rbc_data()`` or the ``run_rbc()`` pipeline to download
fresh RBC (Royal Bank of Canada) corporate data directly from online sources without
needing a local CSV file.
"""

import csv
import io
import json
import logging
import os
import zipfile
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

# ---------------------------------------------------------------------------
# RBC open-data source configuration
# ---------------------------------------------------------------------------
# The Corporations Canada open-data portal publishes a CSV/ZIP of all federally
# registered corporations.  The API endpoint below returns JSON metadata for the
# dataset; the scraper resolves the actual CSV download URL from that metadata.
_CORPORATIONS_CANADA_PACKAGE_URL = (
    "https://open.canada.ca/data/en/api/3/action/package_show"
    "?id=c1b2a820-8e59-4f56-a84c-bb7e0a1c79d5"
)

# Fallback: the Corporations Canada dataset can also be reached via the CKAN
# resource-search endpoint.  We try the package API first.
_CORPORATIONS_CANADA_RESOURCE_SEARCH_URL = (
    "https://open.canada.ca/data/en/api/3/action/resource_search"
    "?query=name:Corporations+Canada+Active+Corporations&limit=5"
)

# Known direct CSV download URLs for the Corporations Canada active corporations
# dataset (updated periodically on open.canada.ca).  Used as hard-coded fallback
# if the CKAN API is unavailable.
_CORPORATIONS_CANADA_CSV_FALLBACKS: List[str] = [
    "https://www.ic.gc.ca/app/scr/cc/CorporationsCanada/fdrlCrpSrch.html",
]

# RBC keyword variants used when filtering corporation names
RBC_NAME_KEYWORDS: List[str] = [
    "royal bank of canada",
    "rbc",
]

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
    # Online RBC data fetch
    # ------------------------------------------------------------------

    def _resolve_csv_url_from_ckan(self) -> Optional[str]:
        """
        Query the CKAN API on open.canada.ca to obtain the direct CSV download
        URL for the Corporations Canada active-corporations dataset.

        Returns the URL string, or None when the API is unavailable.
        """
        try:
            logger.info("Resolving CSV URL via CKAN package API …")
            resp = requests.get(_CORPORATIONS_CANADA_PACKAGE_URL, timeout=20)
            resp.raise_for_status()
            pkg = resp.json()
            resources = pkg.get("result", {}).get("resources", [])
            for resource in resources:
                fmt = resource.get("format", "").lower()
                url = resource.get("url", "")
                if fmt in ("csv", "csv / zip") and url:
                    logger.info("Found CSV resource: %s", url)
                    return url
            # Fallback: accept any resource URL that ends with .csv
            for resource in resources:
                url = resource.get("url", "")
                if url.lower().endswith(".csv"):
                    return url
        except Exception as exc:
            logger.warning("CKAN package API unavailable: %s", exc)
        return None

    def _download_csv_text(self, url: str) -> Optional[str]:
        """
        Download the CSV (or ZIP containing a CSV) at *url* and return its
        text content, or None on failure.
        """
        try:
            logger.info("Downloading CSV from %s …", url)
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")

            # Handle ZIP archives that wrap the CSV
            if "zip" in content_type or url.lower().endswith(".zip"):
                data = resp.content
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                        if csv_names:
                            with zf.open(csv_names[0]) as f:
                                return f.read().decode("utf-8", errors="replace")
                except zipfile.BadZipFile:
                    pass

            return resp.text
        except Exception as exc:
            logger.warning("Failed to download CSV from %s: %s", url, exc)
            return None

    def _is_rbc_record(self, company: Dict) -> bool:
        """Return True when the company record appears to be an RBC entity."""
        name = company.get("company_name", "").lower()
        bank = company.get("bank_name", "").lower()
        for kw in RBC_NAME_KEYWORDS:
            if kw in name or kw in bank:
                return True
        return False

    def fetch_rbc_data(
        self,
        max_records: int = 800,
        filter_status: Optional[str] = None,
        filter_province: Optional[str] = None,
    ) -> List[Dict]:
        """
        Download fresh RBC corporate data directly from Canadian government
        open-data sources and return a list of normalised company dicts.

        Steps:
          1. Resolve the Corporations Canada CSV download URL via the CKAN API.
          2. Download and parse the CSV.
          3. Filter for RBC-related records (company name or bank field contains
             "rbc" or "royal bank of canada").
          4. Optionally filter further by status / province.
          5. Cap the result at *max_records* (default 800).

        Args:
            max_records:     Maximum number of RBC records to return (default 800).
            filter_status:   Optional status filter (e.g. "Active").
            filter_province: Optional province filter (e.g. "ON").

        Returns:
            List of company dicts in the canonical schema.
        """
        source_cfg = DATA_SOURCES["corporations_canada"]
        column_map = source_cfg["column_map"]

        # 1. Resolve CSV URL
        csv_url = self._resolve_csv_url_from_ckan()

        # 2. Download CSV text
        csv_text: Optional[str] = None
        if csv_url:
            csv_text = self._download_csv_text(csv_url)

        if not csv_text:
            logger.error(
                "Could not download Corporations Canada dataset. "
                "Ensure internet access is available."
            )
            return []

        # 3. Load into DataFrame and parse
        if not self.load_from_string(csv_text):
            return []

        companies = self.parse_companies(column_map)
        logger.info("Total corporations parsed: %d", len(companies))

        # 4. Filter for RBC entities
        rbc_companies = [c for c in companies if self._is_rbc_record(c)]
        logger.info("RBC records found: %d", len(rbc_companies))

        # 5. Optional further filters
        if filter_province:
            rbc_companies = self.filter_by_province(filter_province, rbc_companies)
        if filter_status:
            rbc_companies = self.filter_by_status(filter_status, rbc_companies)

        # 6. Cap and store
        self.companies = rbc_companies[:max_records]
        logger.info("Returning %d RBC records (cap: %d).", len(self.companies), max_records)
        return self.companies

    def run_rbc(
        self,
        max_records: int = 800,
        filter_status: Optional[str] = None,
        filter_province: Optional[str] = None,
        csv_filename: str = "rbc_companies.csv",
        json_filename: str = "rbc_companies.json",
    ) -> List[Dict]:
        """
        Full online pipeline for RBC data: fetch → filter → export.

        Downloads fresh RBC corporate data from the Corporations Canada open-data
        portal without requiring any local CSV file.

        Args:
            max_records:     Maximum RBC records (default 800).
            filter_status:   Optional status filter (e.g. "Active").
            filter_province: Optional province filter (e.g. "ON").
            csv_filename:    Output CSV filename (default: rbc_companies.csv).
            json_filename:   Output JSON filename (default: rbc_companies.json).

        Returns:
            List of processed RBC company dicts.
        """
        companies = self.fetch_rbc_data(
            max_records=max_records,
            filter_status=filter_status,
            filter_province=filter_province,
        )

        if companies:
            self.export_to_csv(companies, csv_filename)
            self.export_to_json(companies, json_filename)

        return companies

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
    parser.add_argument(
        "--rbc",
        action="store_true",
        help=(
            "Fetch fresh RBC data directly from the Corporations Canada open-data "
            "portal instead of loading a local CSV file. Outputs ~800 records."
        ),
    )
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

    if args.rbc:
        rbc_max = min(args.max, 800)
        results = scraper.run_rbc(
            max_records=rbc_max,
            filter_status=args.status if args.status else None,
            filter_province=args.province,
            csv_filename=args.csv_out if args.csv_out != "companies_2k.csv" else "rbc_companies.csv",
            json_filename=args.json_out if args.json_out != "companies_2k.json" else "rbc_companies.json",
        )
        csv_name = args.csv_out if args.csv_out != "companies_2k.csv" else "rbc_companies.csv"
        json_name = args.json_out if args.json_out != "companies_2k.json" else "rbc_companies.json"
    else:
        results = scraper.run(
            source_path=args.source,
            filter_company_name=args.company,
            filter_province=args.province,
            filter_industry=args.industry,
            filter_status=args.status,
            csv_filename=args.csv_out,
            json_filename=args.json_out,
        )
        csv_name = args.csv_out
        json_name = args.json_out

    print(f"\n✓ Processed {len(results)} companies.")
    print(f"  CSV  → {args.output_dir}/{csv_name}")
    print(f"  JSON → {args.output_dir}/{json_name}")


if __name__ == "__main__":
    main()
