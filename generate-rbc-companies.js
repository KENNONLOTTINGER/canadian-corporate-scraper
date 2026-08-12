#!/usr/bin/env node
/**
 * Node script to generate 60,000 realistic Canadian company details
 * where every company banks with RBC (Royal Bank of Canada).
 *
 * Outputs:
 *   - output/rbc_companies_60k.csv
 *   - output/rbc_companies_60k.json
 */

const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = path.join(__dirname, 'output');
const CSV_PATH = path.join(OUTPUT_DIR, 'rbc_companies_60k.csv');
const JSON_PATH = path.join(OUTPUT_DIR, 'rbc_companies_60k.json');
const TOTAL_RECORDS = 60000;

const PROVINCES = {
  AB: 'Alberta',
  BC: 'British Columbia',
  MB: 'Manitoba',
  NB: 'New Brunswick',
  NL: 'Newfoundland and Labrador',
  NS: 'Nova Scotia',
  ON: 'Ontario',
  PE: 'Prince Edward Island',
  QC: 'Quebec',
  SK: 'Saskatchewan',
};

const PROVINCE_CODES = Object.keys(PROVINCES);

const COMPANY_PREFIXES = [
  'Northern', 'Canadian', 'Royal', 'Dominion', 'Imperial', 'Pacific',
  'Atlantic', 'Prairie', 'Summit', 'Maple', 'Frontier', 'Heritage',
  'Zenith', 'Apex', 'Prime', 'Quantum', 'Vertex', 'Nexus',
];

const COMPANY_SUFFIXES = [
  'Solutions', 'Systems', 'Services', 'Group', 'Holdings', 'Corp',
  'Ltd', 'Inc', 'Enterprises', 'Partners', 'Alliance', 'Ventures',
  'Consulting', 'Capital', 'Management', 'Technologies',
];

const INDUSTRIES = [
  'Technology', 'Consulting', 'Finance', 'Healthcare', 'Manufacturing',
  'Construction', 'Retail', 'Energy', 'Transportation', 'Real Estate',
  'Agriculture', 'Mining', 'Telecommunications', 'Media', 'Education',
  'Hospitality', 'Legal Services', 'Accounting', 'Insurance', 'Logistics',
];

const FIRST_NAMES = [
  'John', 'Sarah', 'Michael', 'Jane', 'David', 'Emma', 'Alice', 'Bob',
  'Carol', 'Emily', 'Frank', 'Grace', 'Henry', 'Isla', 'Jack', 'Karen',
];

const LAST_NAMES = [
  'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
  'Wilson', 'Moore', 'Taylor', 'Anderson', 'Thomas', 'White', 'Martin',
];

const STREET_NAMES = [
  'Maple', 'Main', 'Queen', 'King', 'Bay', 'Yonge', 'Bloor', 'Robson',
  'Jasper', 'Portage', 'Whyte', 'Rideau', 'Barrington', 'Spring Garden',
];

const RBC_BANK_NAME = 'Royal Bank of Canada (RBC)';

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pad(n, width = 2) {
  return String(n).padStart(width, '0');
}

function generatePhone() {
  return `(${randomInt(200, 999)}) ${randomInt(100, 999)}-${randomInt(1000, 9999)}`;
}

function generateEmail(namePrefix, industry) {
  const domain = `${namePrefix.toLowerCase()}${industry.replace(/\s+/g, '').toLowerCase()}ca.ca`;
  return `info@${domain}`;
}

function generateIncorporationDate() {
  const year = randomInt(2000, 2024);
  const month = randomInt(1, 12);
  // Use 28 days to keep dates valid without month-specific logic.
  const day = randomInt(1, 28);
  return `${year}-${pad(month)}-${pad(day)}`;
}

function generateAddress(provinceCode, industry) {
  const streetNumber = randomInt(1, 9999);
  const streetName = randomChoice(STREET_NAMES);
  const city = industry.slice(0, 6);
  return `${streetNumber} ${streetName} Street, ${city}, ${PROVINCES[provinceCode]} ${provinceCode}`;
}

function generateDirectors() {
  const first1 = randomChoice(FIRST_NAMES);
  const last1 = randomChoice(LAST_NAMES);
  const first2 = randomChoice(FIRST_NAMES);
  let last2 = randomChoice(LAST_NAMES);
  while (last1 === last2) {
    last2 = randomChoice(LAST_NAMES);
  }
  return `${first1} ${last1}, ${first2} ${last2}`;
}

function generateCompany(index) {
  const provinceCode = randomChoice(PROVINCE_CODES);
  const industry = randomChoice(INDUSTRIES);
  const prefix = randomChoice(COMPANY_PREFIXES);
  const suffix = randomChoice(COMPANY_SUFFIXES);
  const companyName = `${prefix} ${suffix}`;
  const registrationNumber = `${provinceCode}${1000000 + index}`;

  return {
    company_name: companyName,
    registration_number: registrationNumber,
    province: provinceCode,
    incorporation_date: generateIncorporationDate(),
    status: randomChoice(['Active', 'Active', 'Active', 'Inactive']),
    address: generateAddress(provinceCode, industry),
    phone: generatePhone(),
    email: generateEmail(prefix, industry),
    industry: industry,
    directors: generateDirectors(),
    bank_name: RBC_BANK_NAME,
  };
}

function generateCompanies(count) {
  const companies = [];
  for (let i = 0; i < count; i++) {
    companies.push(generateCompany(i));
    if ((i + 1) % 10000 === 0) {
      console.log(`Generated ${i + 1} companies...`);
    }
  }
  return companies;
}

function escapeCsvField(value) {
  if (value === null || value === undefined) {
    return '';
  }
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function exportToCsv(companies, filepath) {
  const fields = Object.keys(companies[0]);
  const header = fields.join(',');
  const lines = companies.map((company) =>
    fields.map((field) => escapeCsvField(company[field])).join(',')
  );
  fs.writeFileSync(filepath, [header, ...lines].join('\n'), { encoding: 'utf-8' });
  console.log(`✓ Exported ${companies.length} companies to CSV: ${filepath}`);
}

function exportToJson(companies, filepath) {
  fs.writeFileSync(filepath, JSON.stringify(companies, null, 2), { encoding: 'utf-8' });
  console.log(`✓ Exported ${companies.length} companies to JSON: ${filepath}`);
}

function main() {
  console.log('\n' + '='.repeat(70));
  console.log('RBC-ONLY CANADIAN COMPANY GENERATOR (Node.js)');
  console.log('='.repeat(70) + '\n');

  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const companies = generateCompanies(TOTAL_RECORDS);

  // Sanity check: every record must be RBC only.
  const nonRbcCount = companies.filter(
    (c) => c.bank_name !== RBC_BANK_NAME
  ).length;
  if (nonRbcCount > 0) {
    throw new Error(`Found ${nonRbcCount} records that do not bank with RBC.`);
  }

  exportToCsv(companies, CSV_PATH);
  exportToJson(companies, JSON_PATH);

  console.log('\n' + '='.repeat(70));
  console.log(`✓ SUCCESS! Generated ${companies.length} RBC-only companies`);
  console.log('='.repeat(70) + '\n');

  console.log('Sample records:');
  console.log('-'.repeat(70));
  companies.slice(0, 3).forEach((company, idx) => {
    console.log(`\n${idx + 1}. ${company.company_name}`);
    console.log(`   Registration: ${company.registration_number}`);
    console.log(`   Province: ${company.province}`);
    console.log(`   Status: ${company.status}`);
    console.log(`   Address: ${company.address}`);
    console.log(`   Phone: ${company.phone}`);
    console.log(`   Email: ${company.email}`);
    console.log(`   Industry: ${company.industry}`);
    console.log(`   Bank: ${company.bank_name}`);
  });
  console.log('\n' + '='.repeat(70) + '\n');
}

main();
