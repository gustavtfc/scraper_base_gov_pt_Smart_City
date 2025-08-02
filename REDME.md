# **Scraping Exercise \- Base.gov.pt Portal**

This project contains scripts to extract and visualize public contract data from the base.gov.pt portal, as part of an internship exercise.

## **Description**

The project consists of two main scripts:

1. gov\_pt.py: A command-line script that scrapes data from the portal and saves it to a .csv file.  
2. view\_data.py: A small web application built with Streamlit that loads the .csv file and displays the data in an interactive, searchable, and sortable table.

## **How to Run**

Follow these steps to set up and run the project.

### **1\. Prerequisites**

* Python 3.8+  
* A virtual environment (recommended)

### **2\. Installation**

First, clone the repository and create a virtual environment: git clone \[https://github.com/gustavtfc/Scraping-exercise-base-gov-pt.git\](https://github.com/gustavtfc/Scraping-exercise-base-gov-pt.git)  
cd Scraping-exercise-base-gov-pt  
python3 \-m venv venv  
source venv/bin/activate

Next, install the required dependencies:  
pip install \-r requirements.txt

### **3\. Scrape the Data**

Run the scraping script to generate the contracts\_data.csv file:

python3 gov\_pt.py \-o contracts\_data.csv

### **4\. View the Data**

Run the Streamlit application to visualize the data. A new tab will open in your browser.

streamlit run view\_data.py

On the web page, simply upload the contracts\_data.csv file generated in the previous step.