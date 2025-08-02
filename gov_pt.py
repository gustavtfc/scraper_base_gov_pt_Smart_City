import requests
import pandas as pd
import argparse

def main():
    """
    Main function to execute the scraping process.
    """
    # Set up command-line argument parsing to specify the output file.
    parser = argparse.ArgumentParser(description="Scrapes contract data from base.gov.pt.")
    parser.add_argument('-o', '--output', type=str, default='contracts_output.csv', help="Output file name for the CSV.")
    args = parser.parse_args()

    print(f"Starting scraping process...")

    # The API endpoint that accepts POST requests for searches.
    url = "https://www.base.gov.pt/Base4/pt/resultados/"

    # Headers to mimic a real browser request, captured from network tools.
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }

    # The payload contains the search parameters, captured from network tools.
    # This query searches for "consultoria".
    payload = {
        'type': 'search_contratos',
        'version': '141.0',
        'query': 'texto=consultoria&tipo=0&tipocontrato=0&pais=0&distrito=0&concelho=0',
        'sort': '-publicationDate',
        'page': '0',
        'size': '25' # Fetches 25 results per page.
    }

    try:
        # Execute the POST request with the specified URL, headers, and payload.
        response = requests.post(url, headers=headers, data=payload, timeout=20)
        
        # This will raise an error if the request failed (e.g., 404, 500).
        response.raise_for_status() 
        
        # The server responds with data in JSON format.
        data = response.json()
        
        # Extract the list of contracts from the JSON response.
        # The key 'items' might need to be adjusted if the API structure changes.
        contracts = data.get('items', []) 
        
        if contracts:
            # Convert the list of dictionaries into a Pandas DataFrame for easy handling.
            df = pd.DataFrame(contracts)
            
            # Save the DataFrame to a CSV file, without the pandas index.
            df.to_csv(args.output, index=False, encoding='utf-8')
            print(f"\nSuccess! Found {len(contracts)} contracts and saved them to {args.output}")
        else:
            print("\nRequest was successful, but no contracts were found in the response.")

    except requests.RequestException as e:
        # Handle network-related errors during the request.
        print(f"An error occurred during the request: {e}")
    except KeyError:
        # Handle cases where the expected 'items' key is not in the JSON.
        print("Could not find the 'items' key in the server response. The API structure may have changed.")


# Ensures the main function is called only when the script is executed directly.
if __name__ == "__main__":
    main()