"""
Configuration module for Canadian Corporate Scraper
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Output configuration
OUTPUT_FORMAT = os.getenv('OUTPUT_FORMAT', 'csv')
OUTPUT_DIRECTORY = os.getenv('OUTPUT_DIRECTORY', './output')

# Database configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/companies.db')

# API configuration
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '0.5'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', './logs/scraper.log')

# Search configuration
MAX_RESULTS_PER_QUERY = int(os.getenv('MAX_RESULTS_PER_QUERY', '100'))
DEFAULT_PROVINCE = os.getenv('DEFAULT_PROVINCE', 'ON')

# Data validation
VALIDATE_DATA = os.getenv('VALIDATE_DATA', 'True').lower() == 'true'
CLEAN_DATA = os.getenv('CLEAN_DATA', 'True').lower() == 'true'

# Feature flags
ENABLE_BANK_LOOKUP = os.getenv('ENABLE_BANK_LOOKUP', 'True').lower() == 'true'
ENABLE_DIRECTOR_LOOKUP = os.getenv('ENABLE_DIRECTOR_LOOKUP', 'True').lower() == 'true'

# API endpoints
CORPORATIONS_CANADA_API = "https://www.ic.gc.ca/app/scr/ccrael/new-eng"
ONTARIO_REGISTRY_API = "https://www.onbis.gov.on.ca/oBIS/"

print(f"Configuration loaded:")
print(f"  Output Format: {OUTPUT_FORMAT}")
print(f"  Database: {DATABASE_PATH}")
print(f"  Log Level: {LOG_LEVEL}")
