import requests
import pandas as pd
import time
from tqdm import tqdm
import logging
import csv
import json
import re
import unicodedata
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURAÇÃO DE LOGS ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
file_handler = logging.FileHandler('scraping_final_expandido.log', mode='w', encoding='utf-8')
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

class RateLimiter:
    """
    Garante um intervalo mínimo entre chamadas, com jitter opcional.
    Use instâncias separadas para 'search' e 'detail' se desejar ritmos diferentes.
    """
    def __init__(self, min_interval_seconds=3.0, jitter_seconds=0.5, label="global"):
        self.min_interval = float(min_interval_seconds)
        self.jitter = float(jitter_seconds)
        self._last_ts = 0.0
        self.label = label

    def wait(self):
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_ts
        base_sleep = max(0.0, self.min_interval - elapsed)
        jitter = random.uniform(0, self.jitter) if self.jitter > 0 else 0.0
        to_sleep = base_sleep + jitter
        if to_sleep > 0:
            logger.info(f"Rate limit ({self.label}): aguardando {to_sleep:.2f}s "
                        f"(mín {self.min_interval:.2f}s + jitter {jitter:.2f}s).")
            time.sleep(to_sleep)
        self._last_ts = time.monotonic()

class BaseGovAPIScraper:
    """
    Scraper com deduplicação por ID, agregação de keywords e rate limiting:
    - Busca/paginação: 3s (+ ~0.7s jitter) entre chamadas
    - Detalhe: 1s (+ ~0.3s jitter) entre chamadas
    """
    API_URL = "https://www.base.gov.pt/Base4/pt/resultados/"
    DETAIL_PAGE_URL = "https://www.base.gov.pt/Base4/pt/detalhe/?type=contratos&id={}"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.base.gov.pt',
        'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    # Parâmetros de comportamento (ajuste aqui, se necessário)
    SEARCH_RATE_SECONDS = 3.0     # intervalo mínimo entre chamadas de busca
    SEARCH_JITTER_SECONDS = 0.7   # jitter adicional para busca
    DETAIL_RATE_SECONDS = 1.0     # intervalo mínimo entre chamadas de detalhe
    DETAIL_JITTER_SECONDS = 0.3   # jitter adicional para detalhe
    PAGE_SIZE = 100
    ENABLE_FUZZY_DEDUPE = False   # opcional: dedupe adicional por hash de campos

    def __init__(self, keywords, districts):
        self.keywords = keywords
        self.target_districts = districts

        # Sessão com retries e backoff
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status=5,
            backoff_factor=2,  # 0, 2, 4, 8, 16s ...
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'POST']),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Inicializa sessão (cookies)
        try:
            self.session.get("https://www.base.gov.pt/Base4/pt/pesquisa/", timeout=30)
        except requests.RequestException as e:
            logger.warning(f"Falha ao inicializar sessão (seguiremos mesmo assim): {e}")

        # Rate limiters (tempos mais baixos e com jitter)
        self.search_rl = RateLimiter(self.SEARCH_RATE_SECONDS, self.SEARCH_JITTER_SECONDS, label="search")
        self.detail_rl = RateLimiter(self.DETAIL_RATE_SECONDS, self.DETAIL_JITTER_SECONDS, label="detail")

        # Mapa de distritos normalizados -> nome original
        self.normalized_districts = {self._normalize_text(name): name for name in self.target_districts.keys()}

    # --- Normalizações e utilidades ---
    def _normalize_text(self, s):
        if not s:
            return ''
        s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode('ascii')
        s = s.lower()
        s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
        return s

    def _normalize_keyword(self, kw):
        return self._normalize_text(kw)

    def _join_unique_keywords(self, kw_set):
        seen = set()
        ordered = sorted(kw_set, key=lambda s: self._normalize_keyword(s))
        out = []
        for kw in ordered:
            key = self._normalize_keyword(kw)
            if key and key not in seen:
                seen.add(key)
                out.append(kw)
        return ' | '.join(out)

    def _find_actual_district(self, execution_place):
        if not execution_place:
            return ''
        parts = re.split(r'[,;/|]+', execution_place)
        for part in parts:
            n = self._normalize_text(part)
            if n in self.normalized_districts:
                return self.normalized_districts[n]
        full = self._normalize_text(execution_place)
        for nname, original in self.normalized_districts.items():
            if re.search(r'\b' + re.escape(nname) + r'\b', full):
                return original
        return ''

    # --- Acesso à API com rate limiting ---
    def _post_api(self, url, payload, headers=None, kind="search", timeout=30):
        # Aplica o rate limit antes de cada chamada
        if kind == "search":
            self.search_rl.wait()
        else:
            self.detail_rl.wait()
        response = self.session.post(url, data=payload, headers=headers or {}, timeout=timeout)
        response.raise_for_status()
        return response

    def _discover_contract_ids(self, keyword, district_id):
        discovered_ids = set()
        page = 0
        while True:
            payload = {
                'type': 'search_contratos',
                'version': '141.0',
                'query': f"texto={keyword}&tipo=0&tipocontrato=0&pais=0&distrito={district_id}&concelho=0",
                'sort': '-publicationDate',
                'page': str(page),
                'size': self.PAGE_SIZE
            }
            try:
                response = self._post_api(self.API_URL, payload, kind="search", timeout=60)
                data = response.json()
                items = data.get('items') if data else None
                if items:
                    for item in items:
                        if 'id' in item:
                            discovered_ids.add(item['id'])
                    if len(items) < self.PAGE_SIZE:
                        break
                    page += 1
                else:
                    break
            except requests.RequestException as e:
                logger.error(f"Erro na descoberta para '{keyword}' (distrito {district_id}) pág {page}: {e}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido na descoberta para '{keyword}' pág {page}: {e}")
                break
        return list(discovered_ids)

    def _get_details_from_api(self, contract_id):
        try:
            payload = {'id': contract_id, 'type': 'detail_contratos', 'version': '141.0'}
            detail_headers = {'Referer': self.DETAIL_PAGE_URL.format(contract_id)}
            response = self._post_api(self.API_URL, payload, headers=detail_headers, kind="detail", timeout=60)
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Não foi possível obter detalhes da API para o ID {contract_id}. Erro: {e}")
            return None

    def _format_date(self, date_string):
        if not date_string or not isinstance(date_string, str):
            return ''
        try:
            return pd.to_datetime(date_string, dayfirst=True, errors='coerce').strftime('%d/%m/%Y')
        except Exception:
            return date_string

    def _build_fuzzy_key(self, details_json):
        """
        Opcional: cria um hash/assinatura para detectar quase duplicatas
        (IDs diferentes mas mesmo objeto/valor/data/entidades).
        """
        try:
            desc = self._normalize_text(details_json.get('description', ''))
            place = self._normalize_text(details_json.get('executionPlace', ''))
            sign = self._format_date(details_json.get('signingDate') or '')
            pub = self._format_date(details_json.get('publicationDate') or '')
            contracting = details_json.get('contracting', [])
            if isinstance(contracting, dict): contracting = [contracting]
            contracting_name = self._normalize_text(contracting[0].get('description', '')) if contracting else ''
            contracted = details_json.get('contracted', [])
            if isinstance(contracted, dict): contracted = [contracted]
            contracted_name = self._normalize_text(contracted[0].get('description', '')) if contracted else ''
            raw_valor = str(details_json.get('initialContractualPrice', '0'))
            valor_num = pd.to_numeric(raw_valor.replace('€', '').replace('.', '').replace(',', '.').strip(), errors='coerce')
            valor_norm = f"{valor_num:.2f}" if pd.notna(valor_num) else "nan"
            base = f"{desc}|{place}|{sign}|{pub}|{contracting_name}|{contracted_name}|{valor_norm}"
            return base
        except Exception:
            return None

    # --- Workflow principal ---
    def run(self):
        logger.info("Início com deduplicação por ID e rate limit reduzido (3s busca, 1s detalhe, com jitter).")
        all_contracts_data = []

        # 1) keyword x distrito
        search_space = [(kw, dn, did) for kw in self.keywords for dn, did in self.target_districts.items()]

        # 2) Descobrir IDs e indexar: ID -> {keywords: set(), distritos: set()}
        contracts_index = {}
        total_hits = 0
        for keyword, district_name_query, district_id in tqdm(search_space, desc="Descobrindo IDs"):
            contract_ids = self._discover_contract_ids(keyword, district_id)
            total_hits += len(contract_ids)
            logger.info(f"Encontrados {len(contract_ids)} contratos para '{keyword}' em '{district_name_query}'.")
            for cid in contract_ids:
                entry = contracts_index.get(cid)
                if entry is None:
                    entry = {'keywords': set(), 'districts': set()}
                    contracts_index[cid] = entry
                entry['keywords'].add(keyword)
                entry['districts'].add(district_name_query)

        logger.info(f"IDs descobertos (brutos): {total_hits} | IDs únicos: {len(contracts_index)}")

        # 3) Enriquecer detalhes UMA VEZ por ID e filtrar por distrito efetivo
        fuzzy_seen = set()
        for contract_id, meta in tqdm(contracts_index.items(), desc="Obtendo detalhes únicos", leave=False):
            details_json = self._get_details_from_api(contract_id)
            if not details_json:
                continue

            location_string = details_json.get('executionPlace', '') or ''
            actual_district = self._find_actual_district(location_string)
            if not actual_district:
                logger.debug(f"Contrato {contract_id} ignorado. Localização '{location_string}' fora do escopo.")
                continue

            # contratados
            contracted = details_json.get('contracted', [])
            if isinstance(contracted, dict): contracted = [contracted]
            adjudicatario_nome = contracted[0].get('description', '') if contracted else ''

            # contratante
            contracting = details_json.get('contracting', [])
            if isinstance(contracting, dict): contracting = [contracting]
            entidade_contratante = contracting[0].get('description', '') if contracting else ''

            # valor
            raw_valor = str(details_json.get('initialContractualPrice', '0'))
            valor_num = pd.to_numeric(
                raw_valor.replace('€', '').replace('.', '').replace(',', '.').strip(),
                errors='coerce'
            )

            record = {
                'Distrito': actual_district,
                'Município': location_string,
                'Palavra-Chave Encontrada': self._join_unique_keywords(meta['keywords']),
                'Objeto do Contrato': details_json.get('description', ''),
                'Entidade Contratante': entidade_contratante,
                'Adjudicatário': adjudicatario_nome,
                'Valor (€)': valor_num,
                'Data do Contrato': self._format_date(details_json.get('signingDate')),
                'Publicação': self._format_date(details_json.get('publicationDate')),
                'Link': self.DETAIL_PAGE_URL.format(contract_id),
                'ID Contrato': contract_id
            }

            # Dedupe fuzzy opcional
            if self.ENABLE_FUZZY_DEDUPE:
                key = self._build_fuzzy_key(details_json)
                if key and key in fuzzy_seen:
                    logger.info(f"Removendo quase-duplicata (fuzzy) ID {contract_id}")
                    continue
                if key:
                    fuzzy_seen.add(key)

            all_contracts_data.append(record)

        logger.info(f"Extração completa. Total de {len(all_contracts_data)} contratos válidos (deduplicados por ID).")
        self.save_to_csv(all_contracts_data)

    def save_to_csv(self, data, filename="reporte_FINAL_Centro.csv"):
        if not data:
            logger.warning("Nenhum dado para guardar.")
            return

        df = pd.DataFrame(data)

        # Segurança extra: remover duplicatas por ID
        before = len(df)
        df = df.drop_duplicates(subset=['ID Contrato'], keep='first').copy()
        after = len(df)
        if after < before:
            logger.info(f"Removidas {before - after} duplicatas na gravação (por ID Contrato).")

        # Ordenação por publicação (mais recente primeiro)
        if 'Publicação' in df.columns:
            try:
                df['_pub_dt'] = pd.to_datetime(df['Publicação'], format='%d/%m/%Y', errors='coerce')
                df = df.sort_values(by=['_pub_dt'], ascending=False).drop(columns=['_pub_dt'])
            except Exception:
                pass

        headers = ['Distrito', 'Município', 'Palavra-Chave Encontrada', 'Objeto do Contrato',
                   'Entidade Contratante', 'Adjudicatário', 'Valor (€)', 'Data do Contrato',
                   'Publicação', 'Link', 'ID Contrato']
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=';', extrasaction='ignore')
                writer.writeheader()
                writer.writerows(df.to_dict(orient='records'))
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