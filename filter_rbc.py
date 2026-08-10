#!/usr/bin/env python3
"""
Filter companies by bank - specifically for RBC
"""

import json
import csv
from pathlib import Path

def filter_companies_by_bank(input_csv, output_csv, output_json, bank_filter="RBC"):
    """
    Filter companies to show only those with specified bank
    
    Args:
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        output_json: Path to output JSON file
        bank_filter: Bank name to filter for (default: RBC)
    """
    companies = []
    
    # Read the CSV file
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter for RBC bank
            if bank_filter.upper() in row.get('bank_name', '').upper():
                companies.append(row)
    
    if not companies:
        print(f"No companies found with {bank_filter} bank")
        return
    
    # Write filtered results to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        if companies:
            writer = csv.DictWriter(f, fieldnames=companies[0].keys())
            writer.writeheader()
            writer.writerows(companies)
    
    # Write filtered results to JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)
    
    # Print statistics
    print(f"\n{'='*70}")
    print(f"RBC BANK COMPANIES - FILTERED RESULTS")
    print(f"{'='*70}\n")
    print(f"Total companies with RBC: {len(companies)}")
    
    # Group by province
    provinces = {}
    for company in companies:
        prov = company.get('province', 'Unknown')
        provinces[prov] = provinces.get(prov, 0) + 1
    
    print(f"\nCompanies by Province:")
    for prov, count in sorted(provinces.items()):
        print(f"  {prov}: {count} companies")
    
    print(f"\nFiles saved:")
    print(f"  • {output_csv}")
    print(f"  • {output_json}")
    
    print(f"\nSample RBC Companies:")
    print("-" * 70)
    for i, company in enumerate(companies[:10], 1):
        print(f"\n{i}. {company['company_name']}")
        print(f"   Registration: {company['registration_number']}")
        print(f"   Province: {company['province']}")
        print(f"   Status: {company['status']}")
        print(f"   Address: {company['address']}")
        print(f"   Phone: {company['phone']}")
        print(f"   Email: {company['email']}")
        print(f"   Industry: {company['industry']}")
        print(f"   Bank: {company['bank_name']}")
    
    if len(companies) > 10:
        print(f"\n... and {len(companies) - 10} more companies")
    
    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Filter companies by bank (RBC)')
    parser.add_argument('--input', default='output/companies_2k.csv',
                       help='Input CSV file (default: output/companies_2k.csv)')
    parser.add_argument('--output-csv', default='output/rbc_companies.csv',
                       help='Output CSV file (default: output/rbc_companies.csv)')
    parser.add_argument('--output-json', default='output/rbc_companies.json',
                       help='Output JSON file (default: output/rbc_companies.json)')
    parser.add_argument('--bank', default='RBC',
                       help='Bank name to filter for (default: RBC)')
    
    args = parser.parse_args()
    
    filter_companies_by_bank(args.input, args.output_csv, args.output_json, args.bank)
