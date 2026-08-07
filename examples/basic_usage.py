"""
Basic usage examples for Canadian Corporate Scraper
"""

from scraper import CanadianCorporateScraper


def example_search_by_name():
    """Example: Search companies by name"""
    print("=" * 50)
    print("EXAMPLE 1: Search by Company Name")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Search for a company
    results = scraper.search_by_name("Acme Corporation")
    
    # Display results
    for company in results:
        print(f"\nCompany: {company.get('company_name')}")
        print(f"Address: {company.get('address')}")
        print(f"Phone: {company.get('phone')}")
        print(f"Registration #: {company.get('registration_number')}")
        print(f"Province: {company.get('province')}")
        print(f"Industry: {company.get('industry')}")
        print(f"Status: {company.get('status')}")


def example_search_by_province():
    """Example: Search companies in a specific province"""
    print("\n" + "=" * 50)
    print("EXAMPLE 2: Search by Province (Ontario)")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Search for companies in Ontario
    results = scraper.search_by_province("ON")
    
    print(f"\nFound {len(results)} companies in Ontario")
    
    for company in results[:5]:  # Display first 5
        print(f"\n- {company.get('company_name')}")
        print(f"  {company.get('address')}")


def example_search_by_industry():
    """Example: Search companies by industry"""
    print("\n" + "=" * 50)
    print("EXAMPLE 3: Search by Industry (Technology)")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Search for technology companies
    results = scraper.search_by_industry("Technology")
    
    print(f"\nFound {len(results)} technology companies")
    
    for company in results[:5]:
        print(f"\n- {company.get('company_name')}")
        print(f"  Industry: {company.get('industry')}")
        print(f"  Province: {company.get('province')}")


def example_export_formats():
    """Example: Export data in multiple formats"""
    print("\n" + "=" * 50)
    print("EXAMPLE 4: Export Data in Multiple Formats")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Search for companies
    results = scraper.search_by_name("Business")
    
    # Export to CSV
    print("\nExporting to CSV...")
    scraper.export_to_csv(results, "output/companies.csv")
    
    # Export to JSON
    print("Exporting to JSON...")
    scraper.export_to_json(results, "output/companies.json")
    
    # Export to Excel
    print("Exporting to Excel...")
    scraper.export_to_excel(results, "output/companies.xlsx")
    
    # Save to database
    print("Saving to database...")
    scraper.save_to_database(results)
    
    print("\n✓ All exports completed!")


def example_bank_details():
    """Example: Retrieve bank details for a company"""
    print("\n" + "=" * 50)
    print("EXAMPLE 5: Get Bank Details")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Search for a company first
    results = scraper.search_by_name("Bank Example")
    
    if results:
        company = results[0]
        print(f"\nCompany: {company.get('company_name')}")
        
        # Get bank details (if stored in database)
        bank_info = scraper.get_bank_details(company.get('registration_number'))
        
        if bank_info:
            print(f"Bank Name: {bank_info.get('bank_name')}")
            print(f"Account Type: {bank_info.get('account_type')}")
            print(f"Account Status: {bank_info.get('account_status')}")
            print(f"Routing Number: {bank_info.get('routing_number')}")
        else:
            print("No bank details found for this company")


def example_retrieve_all():
    """Example: Retrieve all companies from database"""
    print("\n" + "=" * 50)
    print("EXAMPLE 6: Retrieve All Companies from Database")
    print("=" * 50)
    
    scraper = CanadianCorporateScraper()
    
    # Get all companies
    all_companies = scraper.get_all_companies()
    
    print(f"\nTotal companies in database: {len(all_companies)}")
    
    for company in all_companies[:3]:  # Display first 3
        print(f"\n- {company.get('company_name')}")
        print(f"  Registration #: {company.get('registration_number')}")
        print(f"  Province: {company.get('province')}")


if __name__ == '__main__':
    # Run all examples
    example_search_by_name()
    example_search_by_province()
    example_search_by_industry()
    example_export_formats()
    example_bank_details()
    example_retrieve_all()
    
    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)
