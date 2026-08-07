# Canadian Corporate Data Scraper

A comprehensive Python tool to extract corporate details from Canadian federal and provincial business registries, including company information and bank details.

## Features

- 🔍 Search Canadian companies by name, industry, province, and incorporation date
- 📊 Extract company details: name, address, phone, registration number, industry classification
- 🏦 Retrieve bank details (where available)
- 📁 Multiple output formats: CSV, JSON, Excel, SQLite database
- ✅ Data validation and cleaning
- ⚡ Rate limiting and error handling
- 📝 Comprehensive logging

## Data Sources

- **Corporations Canada** - Federal business registry API
- **Provincial Registries** - Ontario, British Columbia, Alberta, Manitoba, etc.
- **Business Information Services** - Additional corporate data

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/canadian-corporate-scraper.git
cd canadian-corporate-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file for configuration:
```
OUTPUT_FORMAT=csv
DATABASE_PATH=./data/companies.db
LOG_LEVEL=INFO
```

## Usage

### Basic Search

```python
from scraper import CanadianCorporateScraper

scraper = CanadianCorporateScraper()

# Search by company name
results = scraper.search_by_name("Acme Corporation")

# Search by province
results = scraper.search_by_province("ON")

# Search by industry
results = scraper.search_by_industry("Technology")
```

### Export Data

```python
# Export to CSV
scraper.export_to_csv(results, "companies.csv")

# Export to Excel
scraper.export_to_excel(results, "companies.xlsx")

# Export to JSON
scraper.export_to_json(results, "companies.json")

# Save to SQLite database
scraper.save_to_database(results, "companies.db")
```

### Get Bank Details

```python
# Retrieve bank information for a company
bank_details = scraper.get_bank_details(company_id)
print(bank_details)
```

## Output Fields

### Company Information
- Company Name
- Address
- Phone Number
- Registration/Incorporation Number
- Province
- Industry Classification
- Incorporation Date
- Company Status (Active/Inactive)
- Directors/Officers (where available)

### Bank Details
- Bank Name
- Account Type
- Account Status
- Routing Number (where available)

## Configuration

Edit `.env` to customize:
- `OUTPUT_FORMAT` - Default output format (csv, json, excel, sqlite)
- `DATABASE_PATH` - SQLite database location
- `LOG_LEVEL` - Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `REQUEST_TIMEOUT` - API request timeout in seconds
- `RATE_LIMIT_DELAY` - Delay between requests in seconds

## Examples

See `examples/` directory for complete usage examples.

## Legal & Compliance

- This tool uses public data sources
- Ensure compliance with Canadian data protection laws (PIPEDA)
- Respect terms of service for each data provider
- Data is for informational purposes

## Limitations

- Bank details availability varies by province and data source
- Some private companies may have limited public information
- API rate limits apply

## Contributing

Contributions welcome! Please submit pull requests with:
- Clear description of changes
- Test coverage
- Updated documentation

## License

MIT License - See LICENSE file for details

## Support

For issues or questions, please open a GitHub issue.
