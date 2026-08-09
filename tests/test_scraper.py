import csv
import json

from scraper import CanadianCorporateScraper, OUTPUT_FIELDS


class MockResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class MockSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=30):
        self.calls.append((url, params, timeout))

        if "search.json" in url:
            page = int((params or {}).get("page", 1))
            if page == 1:
                return MockResponse(
                    {
                        "results": [
                            {"corporationId": "1001"},
                            {"corporationId": "1002"},
                        ]
                    }
                )
            return MockResponse({"results": []})

        if "/1001.json" in url:
            return MockResponse(
                [
                    {
                        "corporationId": "1001",
                        "status": "Active",
                        "dateOfIncorporation": "2020-06-01",
                        "corporationNames": [
                            {"CorporationName": {"name": "Maple Analytics Inc."}}
                        ],
                        "registeredOfficeAddress": {
                            "streetAddressLine1": "123 Main St",
                            "city": "Calgary",
                            "province": "AB",
                            "postalCode": "T2P 1J9",
                        },
                        "phone": "403-555-1234",
                        "email": "hello@mapleanalytics.ca",
                        "directors": [
                            {"Director": {"firstName": "Alex", "lastName": "Wong"}}
                        ],
                        "industry": "Technology",
                    },
                    None,
                ]
            )

        if "/1002.json" in url:
            return MockResponse(
                {
                    "corporationId": "1002",
                    "status": "Dissolved",
                    "dateOfIncorporation": "2010-01-01",
                    "corporationNames": [
                        {"CorporationName": {"name": "Legacy Industries Ltd."}}
                    ],
                    "registeredOfficeAddress": {
                        "streetAddressLine1": "456 Old Rd",
                        "city": "Edmonton",
                        "province": "AB",
                    },
                }
            )

        return MockResponse({}, status_code=404)


def test_search_companies_applies_filters_and_collects_records(tmp_path):
    scraper = CanadianCorporateScraper(output_dir=str(tmp_path), rate_limit_delay=0)
    scraper.session = MockSession()

    companies = scraper.search_companies(
        company_name="Maple",
        province="AB",
        business_type="tech",
        status="active",
        start_date="2020-01-01",
        end_date="2022-12-31",
        limit=2000,
    )

    assert len(companies) == 1
    company = companies[0]
    assert company["company_name"] == "Maple Analytics Inc."
    assert company["registration_number"] == "1001"
    assert company["province"] == "AB"
    assert company["directors"] == "Alex Wong"

    search_calls = [call for call in scraper.session.calls if "search.json" in call[0]]
    assert search_calls, "Expected at least one search API call"
    _, params, _ = search_calls[0]
    assert params["q"] == "Maple"
    assert params["province"] == "AB"
    assert params["status"] == "active"


def test_export_to_csv_and_json_default_filenames(tmp_path):
    scraper = CanadianCorporateScraper(output_dir=str(tmp_path), rate_limit_delay=0)
    scraper.companies = [
        {
            "company_name": "Maple Analytics Inc.",
            "registration_number": "1001",
            "status": "Active",
            "incorporation_date": "2020-06-01",
            "address": "123 Main St, Calgary, AB, T2P 1J9",
            "province": "AB",
            "phone": "403-555-1234",
            "email": "hello@mapleanalytics.ca",
            "directors": "Alex Wong",
            "industry": "Technology",
        }
    ]

    csv_path = scraper.export_to_csv()
    json_path = scraper.export_to_json()

    assert csv_path.endswith("companies_2k.csv")
    assert json_path.endswith("companies_2k.json")

    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert rows[0]["company_name"] == "Maple Analytics Inc."
    assert reader.fieldnames == OUTPUT_FIELDS

    with open(json_path, encoding="utf-8") as json_file:
        data = json.load(json_file)
    assert data[0]["registration_number"] == "1001"
