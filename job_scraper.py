#!/usr/bin/env python3
"""
Canadian Job Listings Scraper
Scrapes job postings from SimplyHired Canada and extracts company/address data
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import logging
import time
import argparse
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlencode
from pathlib import Path
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplyHiredJobScraper:
    """Scraper for SimplyHired Canada job listings"""
    
    BASE_URL = "https://www.simplyhired.ca"
    SEARCH_URL = "https://www.simplyhired.ca/search"
    
    def __init__(self, output_dir: str = 'output', rate_limit_delay: float = 1.0,
                 request_timeout: int = 10, max_jobs: int = 2000):
        """
        Initialize the job scraper
        
        Args:
            output_dir: Directory to save output files
            rate_limit_delay: Delay between requests (seconds)
            request_timeout: Request timeout (seconds)
            max_jobs: Maximum jobs to scrape
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.rate_limit_delay = rate_limit_delay
        self.request_timeout = request_timeout
        self.max_jobs = max_jobs
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.jobs = []
    
    def scrape_jobs(self, job_title: str = "Driver", location: str = "Canada", 
                   limit: Optional[int] = None) -> List[Dict]:
        """
        Scrape job listings from SimplyHired
        
        Args:
            job_title: Job title to search (e.g., "Driver", "Software Engineer")
            location: Location (e.g., "Canada", "Ontario", "Toronto")
            limit: Maximum jobs to scrape
            
        Returns:
            List of job postings with company info
        """
        limit = limit or self.max_jobs
        jobs = []
        
        logger.info(f"Scraping SimplyHired Canada for: {job_title} in {location}")
        
        try:
            # Build search parameters
            params = {
                'q': job_title,
                'l': location
            }
            
            page = 0
            jobs_collected = 0
            
            while jobs_collected < limit:
                # SimplyHired uses pagination
                search_params = params.copy()
                search_params['pn'] = page + 1
                
                url = f"{self.SEARCH_URL}?{urlencode(search_params)}"
                logger.info(f"Fetching page {page + 1}... (Total so far: {jobs_collected})")
                
                try:
                    response = self.session.get(url, timeout=self.request_timeout)
                    response.raise_for_status()
                    
                    # Parse the page
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find job cards - SimplyHired uses various selectors
                    job_cards = soup.find_all(['div', 'article'], class_=re.compile('job|card|result', re.I))
                    
                    if not job_cards:
                        logger.warning(f"No job cards found on page {page + 1}")
                        # Try alternative selectors
                        job_cards = soup.find_all('div', class_=re.compile('Card_container|jobCard', re.I))
                    
                    if not job_cards:
                        logger.info("No more jobs found, stopping scrape")
                        break
                    
                    for card in job_cards:
                        if jobs_collected >= limit:
                            break
                        
                        try:
                            job_data = self._parse_job_card(card)
                            if job_data and job_data.get('company_name'):
                                jobs.append(job_data)
                                jobs_collected += 1
                                logger.info(f"Found: {job_data['company_name']} - {job_data['job_title']}")
                        
                        except Exception as e:
                            logger.debug(f"Error parsing job card: {e}")
                            continue
                    
                    page += 1
                    time.sleep(self.rate_limit_delay)
                    
                except Exception as e:
                    logger.error(f"Error fetching page {page + 1}: {e}")
                    break
            
            self.jobs = jobs
            logger.info(f"Successfully scraped {len(jobs)} jobs")
            return jobs
        
        except Exception as e:
            logger.error(f"Error during job scrape: {e}")
            return jobs
    
    def _parse_job_card(self, card) -> Optional[Dict]:
        """
        Parse a job card/listing to extract company and job info
        
        Args:
            card: BeautifulSoup element representing a job listing
            
        Returns:
            Dictionary with job and company data, or None
        """
        try:
            job_data = {}
            
            # Extract job title
            title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile('title|job.*title', re.I))
            if title_elem:
                job_data['job_title'] = title_elem.get_text(strip=True)
            else:
                # Try finding by text content
                title_text = card.get_text(strip=True)[:100]
                job_data['job_title'] = title_text or "Unknown"
            
            # Extract company name
            company_elem = card.find(['span', 'a', 'div'], class_=re.compile('company|employer', re.I))
            if company_elem:
                job_data['company_name'] = company_elem.get_text(strip=True)
            else:
                job_data['company_name'] = "Unknown Company"
            
            # Extract location/address
            location_elem = card.find(['span', 'div'], class_=re.compile('location|place|address', re.I))
            if location_elem:
                job_data['address'] = location_elem.get_text(strip=True)
            else:
                job_data['address'] = "Not specified"
            
            # Extract salary if available
            salary_elem = card.find(['span', 'div'], class_=re.compile('salary|pay|wage', re.I))
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                job_data['salary'] = salary_text
            else:
                job_data['salary'] = "Not specified"
            
            # Extract job description snippet
            desc_elem = card.find(['p', 'div'], class_=re.compile('summary|description|snippet', re.I))
            if desc_elem:
                job_data['description'] = desc_elem.get_text(strip=True)[:200]
            else:
                job_data['description'] = ""
            
            # Extract job posting date
            date_elem = card.find(['span', 'time'], class_=re.compile('date|posted|time', re.I))
            if date_elem:
                job_data['posted_date'] = date_elem.get_text(strip=True)
            else:
                job_data['posted_date'] = "Recently"
            
            # Extract job URL if available
            link_elem = card.find('a', href=True)
            if link_elem:
                job_url = link_elem['href']
                if not job_url.startswith('http'):
                    job_url = urljoin(self.BASE_URL, job_url)
                job_data['job_url'] = job_url
            else:
                job_data['job_url'] = ""
            
            # Add metadata
            job_data['province'] = self._extract_province(job_data.get('address', ''))
            job_data['country'] = 'Canada'
            job_data['source'] = 'SimplyHired Canada'
            
            return job_data
        
        except Exception as e:
            logger.debug(f"Error parsing job card: {e}")
            return None
    
    def _extract_province(self, address: str) -> str:
        """Extract province from address string"""
        provinces = {
            'AB': ['Alberta', 'AB'],
            'BC': ['British Columbia', 'BC'],
            'MB': ['Manitoba', 'MB'],
            'NB': ['New Brunswick', 'NB'],
            'NL': ['Newfoundland', 'NL'],
            'NS': ['Nova Scotia', 'NS'],
            'ON': ['Ontario', 'ON'],
            'PE': ['Prince Edward Island', 'PE', 'PEI'],
            'QC': ['Quebec', 'QC'],
            'SK': ['Saskatchewan', 'SK']
        }
        
        for prov_code, province_names in provinces.items():
            for name in province_names:
                if name.lower() in address.lower():
                    return prov_code
        
        return 'ON'  # Default to Ontario if not found
    
    def export_to_csv(self, jobs: Optional[List[Dict]] = None, 
                     filename: str = 'jobs_listing.csv'):
        """Export jobs to CSV"""
        try:
            data = jobs or self.jobs
            filepath = self.output_dir / filename
            
            if not data:
                logger.warning("No jobs to export")
                return
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Exported {len(data)} jobs to {filepath}")
        
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
    
    def export_to_json(self, jobs: Optional[List[Dict]] = None, 
                      filename: str = 'jobs_listing.json'):
        """Export jobs to JSON"""
        try:
            data = jobs or self.jobs
            filepath = self.output_dir / filename
            
            if not data:
                logger.warning("No jobs to export")
                return
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(data)} jobs to {filepath}")
        
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
    
    def get_companies_from_jobs(self, jobs: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Extract unique companies from job listings
        
        Args:
            jobs: Job listings
            
        Returns:
            List of unique companies with addresses
        """
        data = jobs or self.jobs
        companies_by_key = {}
        
        for job in data:
            company_name = job.get('company_name')
            if not company_name:
                continue
            
            address = job.get('address') or ''
            key = (company_name, address)
            
            if key not in companies_by_key:
                companies_by_key[key] = {
                    'company_name': company_name,
                    'address': address,
                    'province': job.get('province', 'ON'),
                    'country': 'Canada',
                    'open_positions': 1,
                    'last_posting_date': job.get('posted_date'),
                    'industries': 'Transportation/Logistics',
                    'source': 'SimplyHired Canada'
                }
            else:
                companies_by_key[key]['open_positions'] += 1
                
                current_date = job.get('posted_date')
                if current_date:
                    last_posting_date = companies_by_key[key].get('last_posting_date')
                    if not last_posting_date or current_date > last_posting_date:
                        companies_by_key[key]['last_posting_date'] = current_date
        
        return list(companies_by_key.values())


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SimplyHired Canada Job Listings Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 job_scraper.py --job-title Driver --limit 100
  python3 job_scraper.py --job-title "Truck Driver" --location Ontario --limit 500
  python3 job_scraper.py --job-title "Software Engineer" --location Canada --limit 1000
        '''
    )
    
    parser.add_argument('--job-title', type=str, default='Driver',
                       help='Job title to search (default: Driver)')
    parser.add_argument('--location', type=str, default='Canada',
                       help='Location to search (default: Canada)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Maximum jobs to scrape (default: 100)')
    parser.add_argument('--output-dir', type=str, default='output',
                       help='Output directory (default: output)')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("SIMPLYHIRED CANADA JOB LISTINGS SCRAPER")
    print("="*70 + "\n")
    
    scraper = SimplyHiredJobScraper(
        output_dir=args.output_dir,
        max_jobs=args.limit
    )
    
    # Scrape jobs
    jobs = scraper.scrape_jobs(
        job_title=args.job_title,
        location=args.location,
        limit=args.limit
    )
    
    if jobs:
        # Export job listings
        scraper.export_to_csv(jobs, 'jobs_listing.csv')
        scraper.export_to_json(jobs, 'jobs_listing.json')
        
        # Extract and export companies with addresses
        companies = scraper.get_companies_from_jobs(jobs)
        scraper.export_to_csv(companies, 'companies_from_jobs.csv')
        scraper.export_to_json(companies, 'companies_from_jobs.json')
        
        print("\n" + "="*70)
        print(f"✓ SUCCESS! Scraped {len(jobs)} job listings")
        print(f"✓ Found {len(companies)} unique companies hiring")
        print("="*70)
        print(f"\nFiles saved to '{args.output_dir}/':")
        print(f"  • jobs_listing.csv - {len(jobs)} job postings")
        print(f"  • jobs_listing.json - {len(jobs)} job postings")
        print(f"  • companies_from_jobs.csv - {len(companies)} hiring companies")
        print(f"  • companies_from_jobs.json - {len(companies)} hiring companies")
        
        print("\nSample Job Listings:")
        print("-" * 70)
        for i, job in enumerate(jobs[:3], 1):
            print(f"\n{i}. {job.get('job_title', 'N/A')}")
            print(f"   Company: {job.get('company_name', 'N/A')}")
            print(f"   Location: {job.get('address', 'N/A')}")
            print(f"   Salary: {job.get('salary', 'Not specified')}")
            print(f"   Posted: {job.get('posted_date', 'Recently')}")
        
        print("\n\nSample Companies Hiring:")
        print("-" * 70)
        for i, company in enumerate(companies[:3], 1):
            print(f"\n{i}. {company.get('company_name', 'N/A')}")
            print(f"   Address: {company.get('address', 'N/A')}")
            print(f"   Province: {company.get('province', 'N/A')}")
            print(f"   Open Positions: {company.get('open_positions', 0)}")
        
        print("\n" + "="*70 + "\n")
    else:
        logger.error("No jobs were scraped")


if __name__ == '__main__':
    main()
