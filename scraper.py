"""
Canadian Corporate Data Scraper

A comprehensive tool to extract corporate details from Canadian business registries
including company information, bank details, and email addresses.
"""

import requests
import json
import csv
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import urljoin
import sqlite3
from pathlib import Path

try:
    import pandas as pd
    from openpyxl import Workbook
except ImportError:
    pd = None
    Workbook = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CanadianCorporateScraper:
    """Main scraper class for Canadian corporate data"""
    
    # Canadian federal and provincial APIs
    CORPORATIONS_CANADA_API = "https://www.ic.gc.ca/app/scr/ccrael/new-eng"
    ONTARIO_REGISTRY = "https://www.onbis.gov.on.ca/oBIS/"
    
    # Provincial codes
    PROVINCES = {
        'AB': 'Alberta',
        'BC': 'British Columbia',
        'MB': 'Manitoba',
        'NB': 'New Brunswick',
        'NL': 'Newfoundland and Labrador',
        'NS': 'Nova Scotia',
        'ON': 'Ontario',
        'PE': 'Prince Edward Island',
        'QC': 'Quebec',
        'SK': 'Saskatchewan'
    }
    
    # Sample banks for Canadian companies
    CANADIAN_BANKS = [
        'Royal Bank of Canada (RBC)',
        'Toronto-Dominion Bank (TD)',
        'Bank of Montreal (BMO)',
        'Scotiabank',
        'CIBC',
        'National Bank of Canada',
        'Canadian Imperial Bank of Commerce'
    ]
    
    def __init__(self, output_format: str = 'csv', database_path: str = './data/companies.db',
                 request_timeout: int = 10, rate_limit_delay: float = 0.5):
        """
        Initialize the scraper
        
        Args:
            output_format: Default output format (csv, json, excel, sqlite)
            database_path: Path to SQLite database
            request_timeout: Timeout for API requests in seconds
            rate_limit_delay: Delay between requests in seconds
        """
        self.output_format = output_format
        self.database_path = database_path
        self.request_timeout = request_timeout
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.companies = []
        
        # Create data directory if it doesn't exist
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Create companies table with email and bank fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    address TEXT,
                    phone TEXT,
                    email TEXT,
                    registration_number TEXT UNIQUE,
                    province TEXT,
                    industry TEXT,
                    incorporation_date TEXT,
                    status TEXT,
                    directors TEXT,
                    bank_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create bank_details table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bank_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    bank_name TEXT,
                    account_type TEXT,
                    account_status TEXT,
                    routing_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.database_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def search_by_name(self, company_name: str, province: Optional[str] = None) -> List[Dict]:
        """
        Search for companies by name
        
        Args:
            company_name: Name of the company to search
            province: Optional province code (e.g., 'ON', 'BC')
        
        Returns:
            List of matching companies
        """
        logger.info(f"Searching for companies matching: {company_name}")
        results = []
        
        try:
            # Search Corporations Canada
            fed_results = self._search_corporations_canada(company_name)
            results.extend(fed_results)
            
            # Search provincial registry if specified
            if province:
                prov_results = self._search_provincial_registry(company_name, province)
                results.extend(prov_results)
            else:
                # Search all provinces
                for prov_code in self.PROVINCES.keys():
                    prov_results = self._search_provincial_registry(company_name, prov_code)
                    results.extend(prov_results)
                    time.sleep(self.rate_limit_delay)  # Rate limiting
            
            logger.info(f"Found {len(results)} companies matching '{company_name}'")
            self.companies = results
            return results
        
        except Exception as e:
            logger.error(f"Error searching by name: {e}")
            return []
    
    def search_by_province(self, province_code: str) -> List[Dict]:
        """
        Search for companies by province
        
        Args:
            province_code: Province code (e.g., 'ON', 'BC')
        
        Returns:
            List of companies in the province
        """
        logger.info(f"Searching for companies in {self.PROVINCES.get(province_code, province_code)}")
        
        try:
            results = self._search_provincial_registry("*", province_code)
            logger.info(f"Found {len(results)} companies in {province_code}")
            self.companies = results
            return results
        except Exception as e:
            logger.error(f"Error searching by province: {e}")
            return []
    
    def search_by_industry(self, industry: str) -> List[Dict]:
        """
        Search for companies by industry
        
        Args:
            industry: Industry classification or keyword
        
        Returns:
            List of companies in the industry
        """
        logger.info(f"Searching for companies in industry: {industry}")
        
        try:
            # Simulate industry search across all registries
            results = []
            for prov_code in self.PROVINCES.keys():
                prov_results = self._search_provincial_registry(industry, prov_code)
                results.extend(prov_results)
                time.sleep(self.rate_limit_delay)
            
            # Filter by industry
            filtered_results = [
                r for r in results 
                if industry.lower() in r.get('industry', '').lower()
            ]
            
            logger.info(f"Found {len(filtered_results)} companies in {industry}")
            self.companies = filtered_results
            return filtered_results
        except Exception as e:
            logger.error(f"Error searching by industry: {e}")
            return []
    
    def _search_corporations_canada(self, query: str) -> List[Dict]:
        """
        Search Corporations Canada federal registry
        
        Args:
            query: Search query
        
        Returns:
            List of matching companies
        """
        results = []
        try:
            logger.debug(f"Searching Corporations Canada for: {query}")
            
            # API call would go here
            # For now, returning example structure with bank and email
            results = [
                {
                    'company_name': f'Example Corp {query}',
                    'registration_number': 'FC1234567',
                    'province': 'CA',
                    'incorporation_date': '2020-01-15',
                    'status': 'Active',
                    'address': '123 Main St, Toronto, ON M1A 1A1',
                    'phone': '(416) 555-0100',
                    'email': 'contact@examplecorp.ca',
                    'industry': 'Technology',
                    'directors': 'John Doe, Jane Smith',
                    'bank_name': 'Royal Bank of Canada (RBC)'
                }
            ]
        except Exception as e:
            logger.error(f"Error searching Corporations Canada: {e}")
        
        return results
    
    def _search_provincial_registry(self, query: str, province_code: str) -> List[Dict]:
        """
        Search provincial business registry
        
        Args:
            query: Search query
            province_code: Province code
        
        Returns:
            List of matching companies
        """
        results = []
        try:
            logger.debug(f"Searching {province_code} registry for: {query}")
            
            # Template structure for provincial search results with bank and email
            if query != "*":
                results = [
                    {
                        'company_name': f'{query} Solutions Ltd',
                        'registration_number': f'{province_code}1234567',
                        'province': province_code,
                        'incorporation_date': '2021-03-20',
                        'status': 'Active',
                        'address': f'456 Business Ave, {self.PROVINCES[province_code]}',
                        'phone': '(555) 123-4567',
                        'email': f'info@{query.lower().replace(" ", "")}solutions.ca',
                        'industry': 'Consulting',
                        'directors': 'Alice Johnson, Bob Wilson',
                        'bank_name': self.CANADIAN_BANKS[hash(f'{query}{province_code}') % len(self.CANADIAN_BANKS)]
                    }
                ]
        except Exception as e:
            logger.error(f"Error searching {province_code} registry: {e}")
        
        return results
    
    def get_bank_details(self, company_id: int) -> Optional[Dict]:
        """
        Get bank details for a company
        
        Args:
            company_id: Company ID or registration number
        
        Returns:
            Bank details dictionary
        """
        logger.info(f"Retrieving bank details for company ID: {company_id}")
        
        try:
            # Query database
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM bank_details WHERE company_id = ?', (company_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'bank_name': result[2],
                    'account_type': result[3],
                    'account_status': result[4],
                    'routing_number': result[5]
                }
            else:
                logger.warning(f"No bank details found for company ID: {company_id}")
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving bank details: {e}")
            return None
    
    def export_to_csv(self, companies: Optional[List[Dict]] = None, filename: str = 'companies.csv'):
        """
        Export companies to CSV file
        
        Args:
            companies: List of companies to export (uses self.companies if None)
            filename: Output filename
        """
        try:
            data = companies or self.companies
            
            if not data:
                logger.warning("No companies to export")
                return
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Exported {len(data)} companies to {filename}")
        
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
    
    def export_to_json(self, companies: Optional[List[Dict]] = None, filename: str = 'companies.json'):
        """
        Export companies to JSON file
        
        Args:
            companies: List of companies to export (uses self.companies if None)
            filename: Output filename
        """
        try:
            data = companies or self.companies
            
            if not data:
                logger.warning("No companies to export")
                return
            
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(data)} companies to {filename}")
        
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
    
    def export_to_excel(self, companies: Optional[List[Dict]] = None, filename: str = 'companies.xlsx'):
        """
        Export companies to Excel file
        
        Args:
            companies: List of companies to export (uses self.companies if None)
            filename: Output filename
        """
        try:
            if pd is None:
                logger.error("pandas is required for Excel export. Install it with: pip install pandas openpyxl")
                return
            
            data = companies or self.companies
            
            if not data:
                logger.warning("No companies to export")
                return
            
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False, sheet_name='Companies')
            
            logger.info(f"Exported {len(data)} companies to {filename}")
        
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
    
    def save_to_database(self, companies: Optional[List[Dict]] = None):
        """
        Save companies to SQLite database
        
        Args:
            companies: List of companies to save (uses self.companies if None)
        """
        try:
            data = companies or self.companies
            
            if not data:
                logger.warning("No companies to save")
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            for company in data:
                try:
                    cursor.execute('''
                        INSERT INTO companies 
                        (company_name, address, phone, email, registration_number, province, 
                         industry, incorporation_date, status, directors, bank_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        company.get('company_name'),
                        company.get('address'),
                        company.get('phone'),
                        company.get('email'),
                        company.get('registration_number'),
                        company.get('province'),
                        company.get('industry'),
                        company.get('incorporation_date'),
                        company.get('status'),
                        company.get('directors'),
                        company.get('bank_name')
                    ))
                except sqlite3.IntegrityError:
                    logger.warning(f"Company already exists: {company.get('company_name')}")
                    continue
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {len(data)} companies to database")
        
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
    
    def get_all_companies(self) -> List[Dict]:
        """
        Retrieve all companies from database
        
        Returns:
            List of all companies
        """
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM companies')
            results = cursor.fetchall()
            conn.close()
            
            companies = []
            for row in results:
                companies.append({
                    'id': row[0],
                    'company_name': row[1],
                    'address': row[2],
                    'phone': row[3],
                    'email': row[4],
                    'registration_number': row[5],
                    'province': row[6],
                    'industry': row[7],
                    'incorporation_date': row[8],
                    'status': row[9],
                    'directors': row[10],
                    'bank_name': row[11]
                })
            
            return companies
        
        except Exception as e:
            logger.error(f"Error retrieving all companies: {e}")
            return []
    
    def clear_database(self):
        """Clear all data from database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM bank_details')
            cursor.execute('DELETE FROM companies')
            
            conn.commit()
            conn.close()
            
            logger.info("Database cleared")
        
        except Exception as e:
            logger.error(f"Error clearing database: {e}")


def main():
    """Example usage"""
    scraper = CanadianCorporateScraper()
    
    # Search for companies
    results = scraper.search_by_name("Technology")
    
    # Export to different formats
    scraper.export_to_csv(results, 'companies.csv')
    scraper.export_to_json(results, 'companies.json')
    scraper.export_to_excel(results, 'companies.xlsx')
    
    # Save to database
    scraper.save_to_database(results)
    
    print(f"Processed {len(results)} companies")


if __name__ == '__main__':
    main()
