"""
Tests for csv_scraper.py – Canadian Corporate CSV Data Processor
"""

import csv
import json
import os
from unittest.mock import MagicMock, patch
import pytest

from csv_scraper import (
    CSVDataScraper,
    RBC_NAME_KEYWORDS,
    _normalise_province,
    _normalise_status,
    _clean_text,
    OUTPUT_FIELDS,
    PROVINCE_CODES,
)


# ---------------------------------------------------------------------------
# Sample CSV fixture
# ---------------------------------------------------------------------------

SAMPLE_CSV = (
    "Corporation Name,Corporation Number,Status,Date of Incorporation,"
    "Province / Territory,Registered Office Address,Phone,Email,Industry,Directors,Bank Name\n"
    "Maple Tech Ltd.,1111111,Active,2015-06-22,ON,"
    "100 King St W Toronto ON,4165550100,info@mapletech.ca,"
    "Information Technology,Alice Brown,Royal Bank of Canada (RBC)\n"
    "Prairie Grain Co.,2222222,Active,2012-08-30,SK,"
    "1874 Scarth St Regina SK,3065550500,grain@prairie.ca,"
    "Agriculture & Fishing,Tom Wiebe,Scotiabank\n"
    "Quebec Labs Inc.,3333333,Active,2019-01-17,QC,"
    "1000 Rue de la Gauchetiere Montreal QC,5145550600,hello@qclabs.ca,"
    "Research & Development,Pierre Bouchard,National Bank of Canada\n"
    "Coastal Marine Corp.,4444444,Active,2006-09-05,British Columbia,"
    "200 Granville St Vancouver BC,6045550700,service@coastal.ca,"
    "Transportation,Kevin Hall,Toronto-Dominion Bank (TD)\n"
    "Rocky Realty Ltd.,5555555,Dissolved,2005-05-20,AB,"
    "630 8 Ave SW Calgary AB,,,Real Estate,George Hill,\n"
    ",6666666,Active,2020-01-01,ON,123 Fake St,,,,,\n"
)


@pytest.fixture
def sample_csv_path(tmp_path):
    """Write the sample CSV to a temp file and return its path."""
    p = tmp_path / "test_companies.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    return str(p)


@pytest.fixture
def scraper(tmp_path):
    """Return a CSVDataScraper with a temp output directory."""
    return CSVDataScraper(output_dir=str(tmp_path / "output"), max_records=2000)


# ---------------------------------------------------------------------------
# Helper / utility tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_clean_text_strips_whitespace(self):
        assert _clean_text("  hello  ") == "hello"

    def test_clean_text_empty_for_nan(self):
        assert _clean_text("nan") == ""
        assert _clean_text("NaN") == ""

    def test_clean_text_empty_for_none(self):
        assert _clean_text(None) == ""

    def test_clean_text_preserves_unicode(self):
        assert _clean_text("Montréal") == "Montréal"

    def test_normalise_province_code(self):
        assert _normalise_province("ON") == "ON"
        assert _normalise_province("bc") == "BC"

    def test_normalise_province_full_name(self):
        assert _normalise_province("Ontario") == "ON"
        assert _normalise_province("British Columbia") == "BC"
        assert _normalise_province("Quebec") == "QC"

    def test_normalise_province_unknown(self):
        assert _normalise_province("Unknown Province") == "Unknown Province"

    def test_normalise_province_empty(self):
        assert _normalise_province("") == ""

    def test_normalise_status_active_variants(self):
        assert _normalise_status("active") == "Active"
        assert _normalise_status("In Good Standing") == "Active"
        assert _normalise_status("registered") == "Active"

    def test_normalise_status_dissolved(self):
        assert _normalise_status("Dissolved") == "Dissolved"
        assert _normalise_status("cancelled") == "Dissolved"

    def test_normalise_status_inactive(self):
        assert _normalise_status("inactive") == "Inactive"

    def test_normalise_status_unknown(self):
        assert _normalise_status("") == "Unknown"
        assert _normalise_status(None) == "Unknown"


# ---------------------------------------------------------------------------
# load_csv tests
# ---------------------------------------------------------------------------

class TestLoadCSV:
    def test_load_valid_csv(self, scraper, sample_csv_path):
        assert scraper.load_csv(sample_csv_path) is True
        assert scraper._raw_df is not None
        assert len(scraper._raw_df) > 0

    def test_load_missing_file(self, scraper, tmp_path):
        assert scraper.load_csv(str(tmp_path / "nonexistent.csv")) is False

    def test_load_from_string(self, scraper):
        assert scraper.load_from_string(SAMPLE_CSV) is True
        assert scraper._raw_df is not None


# ---------------------------------------------------------------------------
# parse_companies tests
# ---------------------------------------------------------------------------

class TestParseCompanies:
    def test_parse_returns_list(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        result = scraper.parse_companies()
        assert isinstance(result, list)

    def test_skips_rows_without_company_name(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        result = scraper.parse_companies()
        for company in result:
            assert company["company_name"] != ""

    def test_output_fields_present(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        result = scraper.parse_companies()
        assert len(result) > 0
        for field in OUTPUT_FIELDS:
            assert field in result[0], f"Missing field: {field}"

    def test_province_normalised(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        result = scraper.parse_companies()
        for company in result:
            prov = company["province"]
            if prov:
                assert len(prov) <= 2 or prov in PROVINCE_CODES.values(), (
                    f"Province not normalised: {prov}"
                )

    def test_status_normalised(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        result = scraper.parse_companies()
        statuses = {c["status"] for c in result}
        allowed = {"Active", "Dissolved", "Inactive", "Unknown"}
        for s in statuses:
            assert s in allowed, f"Unexpected status: {s}"

    def test_max_records_respected(self, tmp_path):
        limited = CSVDataScraper(output_dir=str(tmp_path), max_records=2)
        limited.load_from_string(SAMPLE_CSV)
        result = limited.parse_companies()
        assert len(result) <= 2

    def test_parse_without_load_returns_empty(self, scraper):
        assert scraper.parse_companies() == []

    def test_custom_column_map(self, scraper, tmp_path):
        custom_csv = "Name,RegNum,Prov,Stat\nAcme Ltd,ABC123,ON,Active\n"
        scraper.load_from_string(custom_csv)
        result = scraper.parse_companies(column_map={
            "company_name": "Name",
            "registration_number": "RegNum",
            "province": "Prov",
            "status": "Stat",
        })
        assert len(result) == 1
        assert result[0]["company_name"] == "Acme Ltd"
        assert result[0]["province"] == "ON"


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------

class TestFilters:
    @pytest.fixture(autouse=True)
    def _load(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        scraper.parse_companies()
        self.scraper = scraper

    def test_filter_by_province(self):
        result = self.scraper.filter_by_province("ON")
        assert all(c["province"] == "ON" for c in result)

    def test_filter_by_province_full_name(self):
        result = self.scraper.filter_by_province("Alberta")
        assert all(c["province"] == "AB" for c in result)

    def test_filter_by_province_empty_when_none_match(self):
        result = self.scraper.filter_by_province("PE")
        assert result == []

    def test_filter_by_industry(self):
        result = self.scraper.filter_by_industry("Technology")
        assert all("technology" in c["industry"].lower() for c in result)

    def test_filter_by_industry_case_insensitive(self):
        upper = self.scraper.filter_by_industry("AGRICULTURE")
        lower = self.scraper.filter_by_industry("agriculture")
        assert len(upper) == len(lower)

    def test_filter_by_status_active(self):
        result = self.scraper.filter_by_status("Active")
        assert all(c["status"] == "Active" for c in result)

    def test_filter_by_status_dissolved(self):
        result = self.scraper.filter_by_status("Dissolved")
        assert all(c["status"] == "Dissolved" for c in result)

    def test_filter_accepts_explicit_list(self):
        companies = [
            {"company_name": "A", "province": "ON", "industry": "Tech", "status": "Active"},
            {"company_name": "B", "province": "BC", "industry": "Tech", "status": "Active"},
        ]
        result = self.scraper.filter_by_province("ON", companies)
        assert len(result) == 1
        assert result[0]["company_name"] == "A"


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExports:
    @pytest.fixture(autouse=True)
    def _load(self, scraper):
        scraper.load_from_string(SAMPLE_CSV)
        scraper.parse_companies()
        self.scraper = scraper

    def test_export_to_csv_creates_file(self, tmp_path):
        out = self.scraper.export_to_csv(filename="out.csv")
        assert out != ""
        assert os.path.exists(out)

    def test_export_to_csv_content(self, tmp_path):
        out = self.scraper.export_to_csv(filename="out.csv")
        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) > 0
        assert "company_name" in rows[0]

    def test_export_to_json_creates_file(self):
        out = self.scraper.export_to_json(filename="out.json")
        assert out != ""
        assert os.path.exists(out)

    def test_export_to_json_valid(self):
        out = self.scraper.export_to_json(filename="out.json")
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_export_empty_returns_empty_string(self, tmp_path):
        empty_scraper = CSVDataScraper(output_dir=str(tmp_path / "empty_out"))
        result = empty_scraper.export_to_csv()
        assert result == ""

    def test_export_uses_output_fields(self):
        out = self.scraper.export_to_csv(filename="out.csv")
        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert header == OUTPUT_FIELDS

    def test_default_filenames(self):
        csv_out = self.scraper.export_to_csv()
        json_out = self.scraper.export_to_json()
        assert csv_out.endswith("companies_2k.csv")
        assert json_out.endswith("companies_2k.json")


# ---------------------------------------------------------------------------
# run() pipeline test
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def test_run_full_pipeline(self, sample_csv_path, tmp_path):
        scraper = CSVDataScraper(output_dir=str(tmp_path), max_records=2000)
        results = scraper.run(
            source_path=sample_csv_path,
            filter_status="Active",
        )
        assert len(results) > 0
        assert all(c["status"] == "Active" for c in results)
        assert os.path.exists(tmp_path / "companies_2k.csv")
        assert os.path.exists(tmp_path / "companies_2k.json")

    def test_run_missing_file_returns_empty(self, tmp_path):
        scraper = CSVDataScraper(output_dir=str(tmp_path))
        result = scraper.run(source_path="/nonexistent/path.csv")
        assert result == []

    def test_run_with_province_filter(self, sample_csv_path, tmp_path):
        scraper = CSVDataScraper(output_dir=str(tmp_path))
        results = scraper.run(source_path=sample_csv_path, filter_province="ON")
        assert all(c["province"] == "ON" for c in results)

    def test_run_outputs_sample_data(self, tmp_path):
        sample = str(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "sample_companies.csv",
            )
        )
        if not os.path.exists(sample):
            pytest.skip("sample_companies.csv not available")
        scraper = CSVDataScraper(output_dir=str(tmp_path))
        results = scraper.run(source_path=sample, filter_status="Active")
        assert len(results) > 0


# ---------------------------------------------------------------------------
# config module test
# ---------------------------------------------------------------------------

class TestConfig:
    def test_config_importable(self):
        import config
        assert hasattr(config, 'OUTPUT_DIRECTORY')
        assert hasattr(config, 'DATA_SOURCES')
        assert hasattr(config, 'SAMPLE_DATA_PATH')
        assert hasattr(config, 'MAX_COMPANIES')

    def test_data_sources_have_required_keys(self):
        import config
        for name, src in config.DATA_SOURCES.items():
            assert 'url' in src, f"Missing 'url' in {name}"
            assert 'description' in src, f"Missing 'description' in {name}"
            assert 'column_map' in src, f"Missing 'column_map' in {name}"


# ---------------------------------------------------------------------------
# RBC online fetch tests (network calls are mocked)
# ---------------------------------------------------------------------------

# Minimal CSV whose rows exercise RBC detection via company name and bank field
RBC_SAMPLE_CSV = (
    "Corporation Name,Corporation Number,Status,Date of Incorporation,"
    "Province / Territory,Registered Office Address,Phone,Email,Industry,Directors,Bank Name\n"
    "Royal Bank of Canada,1000001,Active,1869-01-01,ON,"
    "200 Bay St Toronto ON,4165550001,info@rbc.com,Banking,John Smith,\n"
    "RBC Capital Markets,1000002,Active,2001-03-15,ON,"
    "200 Bay St Toronto ON,4165550002,cm@rbc.com,Finance,Jane Doe,\n"
    "TD Bank Group,2000001,Active,1955-06-01,ON,"
    "66 Wellington St W Toronto ON,4165550003,info@td.com,Banking,Bob Lee,TD Bank\n"
)


class TestRBCFetch:
    """Tests for fetch_rbc_data() and run_rbc() using mocked HTTP calls."""

    @pytest.fixture
    def scraper(self, tmp_path):
        return CSVDataScraper(output_dir=str(tmp_path / "output"), max_records=2000)

    def _mock_ckan_response(self, csv_url: str) -> MagicMock:
        """Return a mock for the CKAN package API that points to *csv_url*."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "resources": [
                    {"format": "CSV", "url": csv_url},
                ]
            }
        }
        return mock_resp

    def _mock_csv_response(self, csv_text: str) -> MagicMock:
        """Return a mock for the CSV download response."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/csv"}
        mock_resp.text = csv_text
        return mock_resp

    def test_rbc_name_keywords_defined(self):
        assert "rbc" in RBC_NAME_KEYWORDS
        assert "royal bank of canada" in RBC_NAME_KEYWORDS

    def test_is_rbc_record_by_name(self, scraper):
        assert scraper._is_rbc_record({"company_name": "Royal Bank of Canada", "bank_name": ""})
        assert scraper._is_rbc_record({"company_name": "RBC Capital Markets", "bank_name": ""})

    def test_is_rbc_record_by_bank_field(self, scraper):
        assert scraper._is_rbc_record({"company_name": "Acme Corp", "bank_name": "RBC"})

    def test_is_rbc_record_false_for_others(self, scraper):
        assert not scraper._is_rbc_record({"company_name": "TD Bank Group", "bank_name": "TD"})

    def test_fetch_rbc_data_returns_only_rbc_records(self, scraper, tmp_path):
        fake_csv_url = "https://fake.example.com/corps.csv"

        def side_effect(url, **kwargs):
            if "package_show" in url:
                return self._mock_ckan_response(fake_csv_url)
            if url == fake_csv_url:
                return self._mock_csv_response(RBC_SAMPLE_CSV)
            raise ValueError(f"Unexpected URL: {url}")

        with patch("csv_scraper.requests.get", side_effect=side_effect):
            results = scraper.fetch_rbc_data(max_records=800)

        assert len(results) == 2  # Royal Bank + RBC Capital; TD excluded
        names = [r["company_name"] for r in results]
        assert "Royal Bank of Canada" in names
        assert "RBC Capital Markets" in names
        assert not any("TD" in n for n in names)

    def test_fetch_rbc_data_respects_max_records(self, scraper):
        fake_csv_url = "https://fake.example.com/corps.csv"

        def side_effect(url, **kwargs):
            if "package_show" in url:
                return self._mock_ckan_response(fake_csv_url)
            return self._mock_csv_response(RBC_SAMPLE_CSV)

        with patch("csv_scraper.requests.get", side_effect=side_effect):
            results = scraper.fetch_rbc_data(max_records=1)

        assert len(results) == 1

    def test_fetch_rbc_data_returns_empty_on_network_error(self, scraper):
        import requests as req_lib

        with patch("csv_scraper.requests.get", side_effect=req_lib.RequestException("timeout")):
            results = scraper.fetch_rbc_data()

        assert results == []

    def test_run_rbc_creates_output_files(self, scraper, tmp_path):
        fake_csv_url = "https://fake.example.com/corps.csv"

        def side_effect(url, **kwargs):
            if "package_show" in url:
                return self._mock_ckan_response(fake_csv_url)
            return self._mock_csv_response(RBC_SAMPLE_CSV)

        with patch("csv_scraper.requests.get", side_effect=side_effect):
            results = scraper.run_rbc(
                csv_filename="rbc_test.csv",
                json_filename="rbc_test.json",
            )

        assert len(results) > 0
        assert os.path.exists(scraper.output_dir / "rbc_test.csv")
        assert os.path.exists(scraper.output_dir / "rbc_test.json")

    def test_run_rbc_output_fields_correct(self, scraper, tmp_path):
        fake_csv_url = "https://fake.example.com/corps.csv"

        def side_effect(url, **kwargs):
            if "package_show" in url:
                return self._mock_ckan_response(fake_csv_url)
            return self._mock_csv_response(RBC_SAMPLE_CSV)

        with patch("csv_scraper.requests.get", side_effect=side_effect):
            results = scraper.run_rbc(csv_filename="rbc_out.csv", json_filename="rbc_out.json")

        assert len(results) > 0
        for field in OUTPUT_FIELDS:
            assert field in results[0]

    def test_resolve_csv_url_ckan_no_resources(self, scraper):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"result": {"resources": []}}

        with patch("csv_scraper.requests.get", return_value=mock_resp):
            url = scraper._resolve_csv_url_from_ckan()

        assert url is None
