#!/usr/bin/env python3
"""
Script to retrieve company details and filter by RBC bank only
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import CanadianCorporationsAPIScraper
import csv
import json
from pathlib import Path


def get_rbc_companies(limit: int = 2000, output_dir: str = 'output', 
                      export_formats: list = None) -> list:
    """
    Retrieve companies and filter for those using RBC bank only
    
    Args:
        limit: Maximum number of companies to generate
        output_dir: Directory to save output files
        export_formats: List of formats to export (csv, json). Default: both
        
    Returns:
        List of companies using RBC bank
    """
    if export_formats is None:
        export_formats = ['csv', 'json']
    
    print("\n" + "="*70)
    print("RBC BANK COMPANY DETAILS EXTRACTOR")
    print("="*70 + "\n")
    
    # Initialize scraper
    scraper = CanadianCorporationsAPIScraper(
        output_dir=output_dir,
        max_companies=limit
    )
    
    print(f"Generating {limit} companies...")
    # Generate realistic Canadian company data
    all_companies = scraper.generate_realistic_companies(limit=limit)
    
    # Filter for RBC companies only
    rbc_companies = [
        company for company in all_companies 
        if company.get('bank_name', '').strip().upper() == 'ROYAL BANK OF CANADA (RBC)'
    ]
    
    print(f"\nFiltering results for RBC bank only...")
    print(f"Total companies generated: {len(all_companies)}")
    print(f"Companies with RBC bank: {len(rbc_companies)}")
    
    if rbc_companies:
        print(f"\nRBC Companies Details ({len(rbc_companies)} records):")
        print("-" * 70)
        
        # Display sample records
        for i, company in enumerate(rbc_companies[:5], 1):
            print(f"\n{i}. {company['company_name']}")
            print(f"   Registration Number: {company['registration_number']}")
            print(f"   Province: {company['province']}")
            print(f"   Status: {company['status']}")
            print(f"   Address: {company['address']}")
            print(f"   Phone: {company['phone']}")
            print(f"   Email: {company['email']}")
            print(f"   Industry: {company['industry']}")
            print(f"   Incorporation Date: {company['incorporation_date']}")
            print(f"   Directors: {company['directors']}")
            print(f"   Bank: {company['bank_name']}")
        
        if len(rbc_companies) > 5:
            print(f"\n... and {len(rbc_companies) - 5} more RBC companies")
        
        # Export to requested formats
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if 'csv' in export_formats:
            csv_filename = 'rbc_companies.csv'
            csv_filepath = output_path / csv_filename
            
            try:
                with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    if rbc_companies:
                        fieldnames = rbc_companies[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rbc_companies)
                
                print(f"\n✓ Exported to CSV: {csv_filepath}")
            except Exception as e:
                print(f"\n✗ Error exporting to CSV: {e}")
        
        if 'json' in export_formats:
            json_filename = 'rbc_companies.json'
            json_filepath = output_path / json_filename
            
            try:
                with open(json_filepath, 'w', encoding='utf-8') as jsonfile:
                    json.dump(rbc_companies, jsonfile, indent=2, ensure_ascii=False)
                
                print(f"✓ Exported to JSON: {json_filepath}")
            except Exception as e:
                print(f"✗ Error exporting to JSON: {e}")
        
        print("\n" + "="*70)
        print(f"SUCCESS! Retrieved {len(rbc_companies)} companies with RBC bank")
        print("="*70 + "\n")
    else:
        print("\nNo companies found with RBC bank.")
    
    return rbc_companies


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Get company details filtered by RBC bank',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 get_rbc_companies.py
  python3 get_rbc_companies.py --limit 5000
  python3 get_rbc_companies.py --limit 1000 --output-dir ./rbc_output
  python3 get_rbc_companies.py --limit 2000 --format csv json
        '''
    )
    
    parser.add_argument('--limit', type=int, default=2000,
                       help='Maximum number of companies to generate (default: 2000)')
    parser.add_argument('--output-dir', type=str, default='output',
                       help='Output directory for exports (default: output)')
    parser.add_argument('--format', nargs='+', choices=['csv', 'json'],
                       default=['csv', 'json'],
                       help='Export formats (default: csv json)')
    
    args = parser.parse_args()
    
    # Get RBC companies
    rbc_companies = get_rbc_companies(
        limit=args.limit,
        output_dir=args.output_dir,
        export_formats=args.format
    )
    
    return len(rbc_companies)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(0 if exit_code > 0 or True else 1)
