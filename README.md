# Web Scraper for the Base.gov.pt Portal

This project contains an advanced Python script for extracting public contract data from the Base.gov.pt portal. It focuses on robustness and efficiency through a 100% API-driven methodology, ensuring high-quality, deduplicated data.

## Description

The scraper was developed to bypass the limitations of dynamic websites that load data via JavaScript. Instead of parsing HTML, it interacts directly with the portal's internal JSON APIs to ensure complete, accurate, and fast data extraction.

### Features
- **100% API-Driven:** Interacts directly with the portal's JSON endpoints, avoiding the complexities and fragility of HTML scraping.
- **Two-Step API Strategy:** Uses a high-speed search API for mass discovery of contract IDs and a specific detail API to enrich each contract with complete information.
- **Data Deduplication:** A core feature that ensures each contract is processed only once, regardless of how many keywords it matches, resulting in a clean and unique final dataset.
- **Data Integrity Filter:** Validates the execution location of each contract against a target list of districts, discarding irrelevant results and ensuring data consistency.
- **Respectful & Resilient:** Includes built-in delays between requests to avoid overloading the server, and handles potential network errors gracefully.
- **Clean Export:** Saves the final, filtered, and deduplicated data into a formatted and easy-to-read `.csv` file.

## How to Run

Follow these steps to set up and run the project.

### 1. Prerequisites
* Python 3.8+
* Git

### 2. Installation
First, clone the repository and create a virtual environment:

```bash
git clone https://github.com/gustavtfc/scraper_base_gov_pt_Smart_City
cd scraper_base_gov_pt_Smart_City
python3 -m venv venv
source venv/bin/activate

###Next, install the required dependencies:
pip install -r requirements.txt

###Execution

###To start the scraper, simply run the main script. It will process all keywords and districts defined in the code.

python3 scraper.py

###The output will be saved in the reporte_FINAL_FILTRADO.csv file.

