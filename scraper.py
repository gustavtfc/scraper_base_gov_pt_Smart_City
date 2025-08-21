import requests
import pandas as pd
import time
from tqdm import tqdm
import logging
from pathlib import Path
import csv
import json

# --- CONFIGURAÇÃO DE LOGS ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
file_handler = logging.FileHandler('scraping_final_expandido.log', mode='w')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger = logging.getLogger('advanced_search')
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

class BaseGovAPIScraper:
    """
    Versão Final com Filtro de Integridade e lista de keywords expandida.
    """
    API_URL = "https://www.base.gov.pt/Base4/pt/resultados/"
    DETAIL_API_URL = "https://www.base.gov.pt/Base4/pt/json/"
    DETAIL_PAGE_URL = "https://www.base.gov.pt/Base4/pt/detalhe/?type=contratos&id={}"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.base.gov.pt'
    }

    def __init__(self, keywords, districts):
        self.keywords = keywords
        self.target_districts = districts
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.get("https://www.base.gov.pt/Base4/pt/pesquisa/")

    def _discover_contract_ids(self, keyword, district_id):
        discovered_ids = set()
        page = 0
        while True:
            payload = {'type': 'search_contratos','version': '141.0','query': f"texto={keyword}&tipo=0&tipocontrato=0&pais=0&distrito={district_id}&concelho=0",'sort': '-publicationDate','page': str(page),'size': 100}
            try:
                response = self.session.post(self.API_URL, data=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                if data and (items := data.get('items')):
                    for item in items: discovered_ids.add(item['id'])
                    if len(items) < 100: break
                    page += 1
                else: break
            except requests.RequestException as e:
                logger.error(f"Erro na descoberta: {e}")
                break
        return list(discovered_ids)

    def _get_details_from_api(self, contract_id):
        try:
            payload = {'id': contract_id, 'type': 'detail_contratos', 'version': '141.0'}
            detail_headers = {'Referer': self.DETAIL_PAGE_URL.format(contract_id)}
            response = self.session.post(self.API_URL, data=payload, headers=detail_headers, timeout=30)
            response.raise_for_status()
            return json.loads(response.text)
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Não foi possível obter detalhes da API para o ID {contract_id}. Erro: {e}")
            return None

    def _format_date(self, date_string):
        if not date_string or not isinstance(date_string, str): return ''
        try:
            return pd.to_datetime(date_string, dayfirst=True).strftime('%d/%m/%Y')
        except (ValueError, TypeError): return date_string
        
    def run(self):
        logger.info("A iniciar o processo de extração com lista de keywords expandida...")
        all_contracts_data = []

        search_space = [(kw, dn, did) for kw in self.keywords for dn, did in self.target_districts.items()]
        
        for keyword, district_name_query, district_id in tqdm(search_space, desc="Processando Keywords"):
            contract_ids = self._discover_contract_ids(keyword, district_id)
            logger.info(f"Encontrados {len(contract_ids)} contratos para '{keyword}' em '{district_name_query}'.")

            for contract_id in tqdm(contract_ids, desc=f"Obtendo detalhes de {keyword}", leave=False):
                details_json = self._get_details_from_api(contract_id)
                
                if details_json:
                    location_string = details_json.get('executionPlace', '')
                    location_parts = [part.strip() for part in location_string.split(',')]
                    
                    actual_district = ''
                    for part in location_parts:
                        if part in self.target_districts:
                            actual_district = part
                            break
                    
                    if not actual_district:
                        logger.debug(f"Contrato {contract_id} ignorado. Localização '{location_string}' fora do escopo.")
                        continue

                    adjudicatarios_list = details_json.get('contracted', [])
                    adjudicatario_nome = adjudicatarios_list[0].get('description', '') if adjudicatarios_list else ''

                    record = {
                        'Distrito': actual_district,
                        'Município': location_string,
                        'Palavra-Chave Encontrada': keyword,
                        'Objeto do Contrato': details_json.get('description', ''),
                        'Entidade Contratante': details_json.get('contracting', [{}])[0].get('description', ''),
                        'Adjudicatário': adjudicatario_nome,
                        'Valor (€)': pd.to_numeric(str(details_json.get('initialContractualPrice', '0')).replace('€', '').replace('.', '').replace(',', '.').strip(), errors='coerce'),
                        'Data do Contrato': self._format_date(details_json.get('signingDate')),
                        'Publicação': self._format_date(details_json.get('publicationDate')),
                        'Link': self.DETAIL_PAGE_URL.format(contract_id),
                        'ID Contrato': contract_id
                    }
                    all_contracts_data.append(record)
                
                time.sleep(0.1)

        logger.info(f"Extração completa. Total de {len(all_contracts_data)} contratos válidos e processados.")
        self.save_to_csv(all_contracts_data)

    def save_to_csv(self, data, filename="reporte_FINAL_Centro.csv"):
        if not data:
            logger.warning("Nenhum dado para guardar.")
            return
        headers = ['Distrito', 'Município', 'Palavra-Chave Encontrada', 'Objeto do Contrato', 'Entidade Contratante', 'Adjudicatário', 'Valor (€)', 'Data do Contrato', 'Publicação', 'Link', 'ID Contrato']
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=';', extrasaction='ignore')
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"Relatório final guardado com sucesso em '{filename}'")
        except Exception as e:
            logger.critical(f"Falha CRÍTICA ao guardar o ficheiro CSV: {e}")

if __name__ == "__main__":
    # ### LISTA DE KEYWORDS EXPANDIDA E BILINGUE ###
    keywords_to_search = [
        # Termos Originais + Traduções
        "WI-Fi", 
        "SIG", "GIS",
        "Smart City", "Cidade Inteligente",
        "Mobilidade Reduzida", "Reduced Mobility",
        "Contentores", "Containers",
        "Datacenter",
        "Cibersegurança", "Cybersecurity",
        "Eficiência Energética", "Energy Efficiency",
        "Energia Fotovoltaica", "Photovoltaic Energy",
        "Iluminação LED", "LED Lighting",
        "WebDoc",
        "IoT", "Internet das Coisas",
        "Big Data",
        "5G",
        "Sensores", "Sensors",

        # Novos Termos + Traduções
        "Veiculo elétrico", "Electric vehicle",
        "Inteligência artificial", "Artificial intelligence",
        "Realidade virtual", "Virtual reality",
        "Realidade aumentada", "Augmented reality",
        "Cloud", "Nuvem",
        "Edge", "Computação de borda",
        "Mobilidade", "Mobility",
        "Cyber", "Ciber"
    ]
    
    districts_to_search = {
        "Aveiro": 1, "Castelo Branco": 5, "Coimbra": 6,
        "Guarda": 9, "Leiria": 10, "Viseu": 18
    }
    
    scraper = BaseGovAPIScraper(keywords=keywords_to_search, districts=districts_to_search)
    scraper.run()