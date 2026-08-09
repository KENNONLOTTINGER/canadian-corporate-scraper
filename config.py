"""
Configuration module for Canadian Corporate Scraper
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Output configuration
# ---------------------------------------------------------------------------
OUTPUT_FORMAT = os.getenv('OUTPUT_FORMAT', 'csv')
OUTPUT_DIRECTORY = os.getenv('OUTPUT_DIRECTORY', './output')
CSV_OUTPUT_FILENAME = os.getenv('CSV_OUTPUT_FILENAME', 'companies_2k.csv')
JSON_OUTPUT_FILENAME = os.getenv('JSON_OUTPUT_FILENAME', 'companies_2k.json')

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/companies.db')

# ---------------------------------------------------------------------------
# Request / rate-limit configuration
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '0.5'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', './logs/scraper.log')

# ---------------------------------------------------------------------------
# Search / filter configuration
# ---------------------------------------------------------------------------
MAX_RESULTS_PER_QUERY = int(os.getenv('MAX_RESULTS_PER_QUERY', '100'))
MAX_COMPANIES = int(os.getenv('MAX_COMPANIES', '2000'))
DEFAULT_PROVINCE = os.getenv('DEFAULT_PROVINCE', '')   # empty = all provinces
DEFAULT_INDUSTRY = os.getenv('DEFAULT_INDUSTRY', '')   # empty = all industries
DEFAULT_STATUS = os.getenv('DEFAULT_STATUS', 'Active')

# ---------------------------------------------------------------------------
# Data validation / cleaning
# ---------------------------------------------------------------------------
VALIDATE_DATA = os.getenv('VALIDATE_DATA', 'True').lower() == 'true'
CLEAN_DATA = os.getenv('CLEAN_DATA', 'True').lower() == 'true'

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
ENABLE_BANK_LOOKUP = os.getenv('ENABLE_BANK_LOOKUP', 'True').lower() == 'true'
ENABLE_DIRECTOR_LOOKUP = os.getenv('ENABLE_DIRECTOR_LOOKUP', 'True').lower() == 'true'

# ---------------------------------------------------------------------------
# CSV data source configuration
# ---------------------------------------------------------------------------

# Default local sample dataset shipped with the package
SAMPLE_DATA_PATH = os.getenv(
    'SAMPLE_DATA_PATH',
    str(Path(__file__).parent / 'data' / 'sample_companies.csv'),
)

# Public Canadian government open-data sources
# These URLs point to real dataset landing pages; the actual downloadable CSV
# link may change. Set CSV_SOURCE_URL in your .env to override.
DATA_SOURCES = {
    'corporations_canada': {
        'url': os.getenv(
            'CORPORATIONS_CANADA_CSV_URL',
            'https://open.canada.ca/data/en/dataset/'
            'c1b2a820-8e59-4f56-a84c-bb7e0a1c79d5',
        ),
        'description': 'Corporations Canada – federal incorporations dataset',
        'column_map': {
            'company_name': 'Corporation Name',
            'registration_number': 'Corporation Number',
            'status': 'Status',
            'incorporation_date': 'Date of Incorporation',
            'province': 'Province / Territory',
            'address': 'Registered Office Address',
        },
    },
    'statistics_canada': {
        'url': os.getenv(
            'STATISTICS_CANADA_CSV_URL',
            'https://www150.statcan.gc.ca/n1/pub/71-607-x/71-607-x2018013-eng.htm',
        ),
        'description': 'Statistics Canada Business Register – public extract',
        'column_map': {
            'company_name': 'Business Name',
            'registration_number': 'Business Number',
            'status': 'Operating Status',
            'incorporation_date': 'Start Date',
            'province': 'Province',
            'industry': 'NAICS Description',
        },
    },
}

# Active data source key (must be a key in DATA_SOURCES or 'local')
ACTIVE_DATA_SOURCE = os.getenv('ACTIVE_DATA_SOURCE', 'local')

# ---------------------------------------------------------------------------
# Province / industry filter lists (comma-separated in env vars)
# ---------------------------------------------------------------------------
FILTER_PROVINCES = [
    p.strip() for p in os.getenv('FILTER_PROVINCES', '').split(',') if p.strip()
]
FILTER_INDUSTRIES = [
    i.strip() for i in os.getenv('FILTER_INDUSTRIES', '').split(',') if i.strip()
]

# ---------------------------------------------------------------------------
# Legacy API endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------
CORPORATIONS_CANADA_API = "https://www.ic.gc.ca/app/scr/ccrael/new-eng"
ONTARIO_REGISTRY_API = "https://www.onbis.gov.on.ca/oBIS/"
