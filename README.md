# Web Scraper for the Base.gov.pt Portal

This project contains an advanced Python script for extracting public contract data from the Base.gov.pt portal, focusing on robustness and efficiency through a 100% API-driven approach.

## Description

The scraper is designed to bypass the limitations of dynamic websites that load data via JavaScript. Instead of parsing HTML, it interacts directly with the portal's internal APIs to ensure complete and accurate data extraction.

### Features
- **100% API-Driven:** Interacts directly with the portal's JSON endpoints, avoiding the complexities of HTML scraping and JavaScript execution.
- **Two-Phase Extraction:** Utilizes a search API to quickly discover contract IDs and a detail API to retrieve comprehensive information for each one.
- **Data Integrity Filter:** Validates the execution location of each contract to ensure the results match the desired districts, discarding inconsistent data.
- **Resilient:** The code is built to handle inconsistencies in the API responses (such as lists vs. strings and different date formats).
- **Clean Export:** Saves the final data into a formatted and easy-to-read `.csv` file.

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

