"""Corporations Canada API scraper."""

import argparse
import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


OUTPUT_FIELDS = [
    "company_name",
    "registration_number",
    "status",
    "incorporation_date",
    "address",
    "province",
    "phone",
    "email",
    "directors",
    "industry",
]


class CanadianCorporateScraper:
    """Scraper for real federal corporation data via Corporations Canada endpoints."""

    SEARCH_API = (
        "https://www.ic.gc.ca/app/scr/cc/CorporationsCanada/api/corporations/search.json"
    )
    DETAIL_API_TEMPLATE = (
        "https://www.ic.gc.ca/app/scr/cc/CorporationsCanada/api/corporations/{corp_id}.json"
    )

    def __init__(
        self,
        output_dir: str = "./output",
        request_timeout: int = 30,
        rate_limit_delay: float = 0.5,
        max_retries: int = 3,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.request_timeout = request_timeout
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.companies: List[Dict[str, str]] = []

    def _request_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """GET JSON with retry, timeout, and rate limiting."""
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.request_timeout)
                response.raise_for_status()
                time.sleep(self.rate_limit_delay)
                return response.json()
            except requests.RequestException as exc:
                logger.warning(
                    "Request failed (%s/%s) for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt == self.max_retries:
                    return None
                time.sleep(self.rate_limit_delay * attempt)
            except ValueError as exc:
                logger.error("Invalid JSON from %s: %s", url, exc)
                return None
        return None

    @staticmethod
    def _pluck(payload: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _flatten_name_entry(entry: Dict[str, Any]) -> str:
        corporation_name = entry.get("CorporationName") if isinstance(entry, dict) else None
        if isinstance(corporation_name, dict):
            name = corporation_name.get("name") or corporation_name.get("Name")
            if name:
                return str(name).strip()
        if isinstance(entry, dict):
            name = entry.get("name") or entry.get("Name")
            if name:
                return str(name).strip()
        return ""

    @classmethod
    def _extract_company_name(cls, payload: Dict[str, Any]) -> str:
        names = payload.get("corporationNames")
        if isinstance(names, list):
            for entry in names:
                name = cls._flatten_name_entry(entry)
                if name:
                    return name
        return cls._pluck(payload, ["companyName", "name", "corporationName"])

    @staticmethod
    def _extract_address(payload: Dict[str, Any]) -> str:
        address = payload.get("registeredOfficeAddress") or payload.get("address")
        if not isinstance(address, dict):
            return ""

        parts = [
            address.get("streetAddressLine1") or address.get("line1") or "",
            address.get("streetAddressLine2") or address.get("line2") or "",
            address.get("city") or "",
            address.get("province") or address.get("provinceTerritory") or "",
            address.get("postalCode") or "",
        ]
        cleaned = [str(part).strip() for part in parts if str(part).strip()]
        return ", ".join(cleaned)

    @staticmethod
    def _extract_province(payload: Dict[str, Any]) -> str:
        address = payload.get("registeredOfficeAddress") or payload.get("address")
        if isinstance(address, dict):
            province = address.get("province") or address.get("provinceTerritory")
            if province:
                return str(province).strip()
        return ""

    @staticmethod
    def _extract_directors(payload: Dict[str, Any]) -> str:
        directors = payload.get("directors")
        if not isinstance(directors, list):
            return ""

        names: List[str] = []
        for entry in directors:
            director = entry.get("Director") if isinstance(entry, dict) else None
            if not isinstance(director, dict):
                director = entry if isinstance(entry, dict) else {}
            first = str(director.get("firstName") or "").strip()
            last = str(director.get("lastName") or "").strip()
            full_name = f"{first} {last}".strip()
            if full_name:
                names.append(full_name)
        return "; ".join(names)

    @staticmethod
    def _normalize_date(date_value: str) -> str:
        if not date_value:
            return ""
        candidate = str(date_value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(candidate, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return candidate

    @staticmethod
    def _within_date_range(
        incorporation_date: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> bool:
        if not incorporation_date:
            return not start_date and not end_date
        try:
            value = datetime.strptime(incorporation_date, "%Y-%m-%d")
        except ValueError:
            return False

        if start_date:
            try:
                if value < datetime.strptime(start_date, "%Y-%m-%d"):
                    return False
            except ValueError:
                return False
        if end_date:
            try:
                if value > datetime.strptime(end_date, "%Y-%m-%d"):
                    return False
            except ValueError:
                return False
        return True

    def _extract_company(self, payload: Dict[str, Any]) -> Dict[str, str]:
        incorporation_date = self._normalize_date(
            self._pluck(payload, ["dateOfIncorporation", "incorporationDate", "createdDate"])
        )

        return {
            "company_name": self._extract_company_name(payload),
            "registration_number": self._pluck(
                payload,
                ["corporationId", "corporationNumber", "businessNumber", "registrationNumber"],
            ),
            "status": self._pluck(payload, ["status", "corporationStatus"]) or "Unknown",
            "incorporation_date": incorporation_date,
            "address": self._extract_address(payload),
            "province": self._extract_province(payload),
            "phone": self._pluck(payload, ["phone", "phoneNumber", "contactPhone"]),
            "email": self._pluck(payload, ["email", "contactEmail"]),
            "directors": self._extract_directors(payload),
            "industry": self._pluck(payload, ["industry", "businessType", "primaryActivity"]),
        }

    @staticmethod
    def _extract_search_results(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            for key in ("results", "corporations", "items", "data"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    return rows
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        return []

    @staticmethod
    def _extract_corporation_id(item: Dict[str, Any]) -> str:
        for key in (
            "corporationId",
            "corporation_id",
            "corporationNumber",
            "businessNumber",
            "id",
        ):
            value = item.get(key)
            if value:
                return str(value).strip()
        return ""

    def _fetch_company_detail(self, corporation_id: str) -> Optional[Dict[str, Any]]:
        url = self.DETAIL_API_TEMPLATE.format(corp_id=corporation_id)
        payload = self._request_json(url, params={"lang": "eng"})
        if payload is None:
            return None

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    return item
            return None

        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _matches_filters(
        company: Dict[str, str],
        province: Optional[str],
        business_type: Optional[str],
        status: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> bool:
        if province and company.get("province", "").upper() != province.upper():
            return False

        if business_type:
            industry = company.get("industry", "")
            if business_type.lower() not in industry.lower():
                return False

        if status and company.get("status", "").lower() != status.lower():
            return False

        if not CanadianCorporateScraper._within_date_range(
            company.get("incorporation_date", ""), start_date, end_date
        ):
            return False

        return True

    def search_companies(
        self,
        company_name: Optional[str] = None,
        province: Optional[str] = None,
        business_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 2000,
        page_size: int = 100,
    ) -> List[Dict[str, str]]:
        """Search Corporations Canada and collect up to *limit* company records."""
        logger.info("Starting company search for '%s' (limit=%s)", company_name or "*", limit)
        companies: List[Dict[str, str]] = []
        seen_ids = set()
        page = 1

        while len(companies) < limit:
            params = {"lang": "eng", "page": page, "size": page_size}
            if company_name:
                params["q"] = company_name
            if province:
                params["province"] = province.upper()
            if business_type:
                params["businessType"] = business_type
            if status:
                params["status"] = status
            if start_date:
                params["fromDate"] = start_date
            if end_date:
                params["toDate"] = end_date

            search_payload = self._request_json(self.SEARCH_API, params=params)
            if search_payload is None:
                logger.error("Search request failed; stopping collection.")
                break

            search_results = self._extract_search_results(search_payload)
            if not search_results:
                logger.info("No more search results at page %s", page)
                break

            for item in search_results:
                corp_id = self._extract_corporation_id(item)
                if not corp_id or corp_id in seen_ids:
                    continue
                seen_ids.add(corp_id)

                detail_payload = self._fetch_company_detail(corp_id)
                if not detail_payload:
                    continue

                company = self._extract_company(detail_payload)
                if not company.get("company_name"):
                    continue

                if not self._matches_filters(
                    company,
                    province=province,
                    business_type=business_type,
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                ):
                    continue

                companies.append(company)

                if len(companies) % 50 == 0 or len(companies) == limit:
                    logger.info("Collected %s/%s companies", len(companies), limit)

                if len(companies) >= limit:
                    break

            page += 1

        self.companies = companies
        logger.info("Finished. Collected %s companies.", len(companies))
        return companies

    # compatibility wrappers
    def search_by_name(self, company_name: str, province: Optional[str] = None) -> List[Dict[str, str]]:
        return self.search_companies(company_name=company_name, province=province, limit=2000)

    def search_by_province(self, province_code: str) -> List[Dict[str, str]]:
        return self.search_companies(company_name=None, province=province_code, limit=2000)

    def search_by_industry(self, industry: str) -> List[Dict[str, str]]:
        return self.search_companies(company_name=None, business_type=industry, limit=2000)

    def scrape_bulk_companies(self, limit: int = 2000) -> List[Dict[str, str]]:
        return self.search_companies(company_name=None, limit=limit)

    def export_to_csv(
        self, companies: Optional[List[Dict[str, str]]] = None, filename: str = "companies_2k.csv"
    ) -> str:
        data = companies if companies is not None else self.companies
        if not data:
            logger.warning("No companies to export to CSV")
            return ""

        out_path = self.output_dir / filename
        with open(out_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
        logger.info("Saved CSV: %s", out_path)
        return str(out_path)

    def export_to_json(
        self, companies: Optional[List[Dict[str, str]]] = None, filename: str = "companies_2k.json"
    ) -> str:
        data = companies if companies is not None else self.companies
        if not data:
            logger.warning("No companies to export to JSON")
            return ""

        out_path = self.output_dir / filename
        with open(out_path, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)
        logger.info("Saved JSON: %s", out_path)
        return str(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape real federal corporations from Corporations Canada API"
    )
    parser.add_argument(
        "company_name",
        nargs="?",
        default=None,
        help="Company name or keyword to search",
    )
    parser.add_argument("--province", help="Province filter (e.g. AB)")
    parser.add_argument("--business-type", help="Business type/industry filter")
    parser.add_argument("--status", help="Status filter (e.g. Active, Dissolved)")
    parser.add_argument("--start-date", help="Incorporation start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Incorporation end date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=2000, help="Number of records to collect")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--request-timeout", type=int, default=30, help="HTTP timeout seconds")
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.5,
        help="Delay between API calls in seconds",
    )

    args = parser.parse_args()

    scraper = CanadianCorporateScraper(
        output_dir=args.output_dir,
        request_timeout=args.request_timeout,
        rate_limit_delay=args.rate_limit_delay,
    )

    companies = scraper.search_companies(
        company_name=args.company_name,
        province=args.province,
        business_type=args.business_type,
        status=args.status,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )

    csv_path = scraper.export_to_csv(companies, "companies_2k.csv")
    json_path = scraper.export_to_json(companies, "companies_2k.json")

    print(f"Collected {len(companies)} companies")
    if csv_path:
        print(f"CSV: {csv_path}")
    if json_path:
        print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
