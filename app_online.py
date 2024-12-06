import streamlit as st
import pandas as pd
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime
from contextlib import contextmanager
import logging
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Configurações
CONFIG = {
    'WAIT_TIME': 20,
    'SCROLL_PAUSE': 3,
    'PAGE_LOAD_WAIT': 5,
    'BASE_URL': "https://www.vivareal.com.br/venda/ceara/eusebio/lote-terreno_residencial/",
    'RETRY_ATTEMPTS': 3
}

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--window-size=1920,1080')
    # Argumentos adicionais para ambiente cloud
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

@contextmanager
def managed_driver():
    driver = None
    try:
        driver = setup_driver()
        yield driver
    finally:
        if driver:
            driver.quit()

def scroll_page(driver):
    """Função para rolar a página e carregar todo o conteúdo"""
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(CONFIG['SCROLL_PAUSE'])

def extract_property_data(prop, global_id, page):
    """Extrair dados de uma propriedade individual"""
    try:
        return {
            'ID': global_id,
            'Título': prop.find_element(By.CSS_SELECTOR, 'span.property-card__title').text,
            'Endereço': prop.find_element(By.CSS_SELECTOR, 'span.property-card__address').text,
            'Área': prop.find_element(By.CSS_SELECTOR, 'span.property-card__detail-area').text,
            'Preço': prop.find_element(By.CSS_SELECTOR, 'div.property-card__price').text,
            'Link': prop.find_element(By.CSS_SELECTOR, 'a.property-card__content-link').get_attribute('href'),
            'Página': page
        }
    except Exception as e:
        logger.error(f"Erro ao extrair dados da propriedade: {str(e)}")
        return None

def find_next_button(wait):
    """Encontrar e retornar o botão de próxima página"""
    selectors = [
        "//button[contains(., 'Próxima página')]",
        "//a[contains(., 'Próxima página')]",
        "//button[contains(@class, 'pagination__button')]",
        "//button[contains(@class, 'js-change-page')]",
        "//button[@title='Próxima página']",
        "//a[@title='Próxima página']"
    ]
    
    for selector in selectors:
        try:
            return wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
        except:
            continue
    return None

def navigate_to_next_page(driver, wait, status_placeholder, page):
    """Navegar para a próxima página"""
    next_button = find_next_button(wait)
    if next_button:
        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
        time.sleep(2)
        driver.execute_script("arguments[0].click();", next_button)
        time.sleep(CONFIG['PAGE_LOAD_WAIT'])
        return True
    else:
        status_placeholder.write("Chegamos à última página disponível")
        return False

def scrape_vivareal(num_pages=5):
    all_data = []
    global_id = 0
    status_placeholder = st.empty()
    
    try:
        with managed_driver() as driver:
            driver.get(CONFIG['BASE_URL'])
            wait = WebDriverWait(driver, CONFIG['WAIT_TIME'])
            
            for page in range(1, num_pages + 1):
                try:
                    status_placeholder.write(f"Coletando dados da página {page} de {num_pages}")
                    time.sleep(CONFIG['PAGE_LOAD_WAIT'])
                    
                    scroll_page(driver)
                    
                    properties = wait.until(EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, 'div[data-type="property"]')))
                    
                    if not properties:
                        status_placeholder.write(f"Não foram encontradas propriedades na página {page}")
                        break
                    
                    status_placeholder.write(
                        f"Coletando dados da página {page} de {num_pages}\n"
                        f"Número de propriedades encontradas na página {page}: {len(properties)}"
                    )
                    
                    for prop in properties:
                        global_id += 1
                        property_data = extract_property_data(prop, global_id, page)
                        if property_data:
                            all_data.append(property_data)
                    
                    status_placeholder.write(
                        f"Página {page} completada com sucesso.\n"
                        f"Total de propriedades coletadas até agora: {global_id}"
                    )
                    
                    if page < num_pages and not navigate_to_next_page(driver, wait, status_placeholder, page):
                        break
                        
                except Exception as e:
                    logger.error(f"Erro ao processar página {page}: {str(e)}")
                    continue
                    
        if not all_data:
            status_placeholder.write("Nenhum dado foi encontrado")
            return None
            
        df = pd.DataFrame(all_data)
        status_placeholder.write(f"Total de propriedades coletadas: {len(df)}")
        return df
        
    except Exception as e:
        logger.error(f"Erro ao fazer scraping: {str(e)}")
        st.error(f"Erro ao fazer scraping: {str(e)}")
        return None

def export_to_excel(df):
    """Exportar dados para Excel"""
    hoje = datetime.now().strftime("%d_%m_%Y")
    nome_arquivo = f"lotes_eusebio_vivareal_{hoje}.xlsx"
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue(), nome_arquivo

def main():
    st.title("Scraping de Lotes - Vivareal Eusébio")
    
    num_pages = st.slider("Número de páginas para coletar", 1, 10, 5)
    
    if st.button("Iniciar Scraping"):
        with st.spinner("Coletando dados..."):
            df = scrape_vivareal(num_pages)
            
            if df is not None and not df.empty:
                st.success("Dados coletados com sucesso!")
                st.dataframe(df)
                
                excel_data, nome_arquivo = export_to_excel(df)
                
                st.download_button(
                    label="Baixar dados em Excel",
                    data=excel_data,
                    file_name=nome_arquivo,
                    mime="application/vnd.ms-excel"
                )
            else:
                st.error("Não foi possível coletar os dados. Tente novamente mais tarde.")

if __name__ == "__main__":
    main() 