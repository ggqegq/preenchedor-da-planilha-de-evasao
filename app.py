# requirements.txt (adicione ao seu projeto):
# streamlit
# selenium
# webdriver-manager

import streamlit as st
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Executa em segundo plano
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login(driver, username, password):
    driver.get("https://app.uff.br/graduacao/administracaoacademica")
    
    # Aguarda o campo de login aparecer
    wait = WebDriverWait(driver, 10)
    username_input = wait.until(EC.presence_of_element_located((By.ID, "idUFF")))
    
    # Preenche login e senha
    username_input.send_keys(username)
    driver.find_element(By.ID, "senha").send_keys(password)
    
    # Clica no botão de acesso
    driver.find_element(By.XPATH, "//button[contains(text(), 'ACESSAR')]").click()
    
    # Aguarda o login ser concluído
    time.sleep(5)
    
    # Verifica se o login foi bem-sucedido
    if "login" in driver.current_url.lower():
        return False
    return True

def navigate_to_report(driver):
    # Exemplo de navegação até o relatório (ajuste conforme necessário)
    # Você precisará inspecionar a página para encontrar os elementos corretos
    try:
        # Aguarda o carregamento do menu
        wait = WebDriverWait(driver, 10)
        relatorio_link = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Relatórios"))
        )
        relatorio_link.click()
        time.sleep(2)
        
        # Clica no relatório específico (ajuste o texto conforme necessário)
        relatorio_item = driver.find_element(By.LINK_TEXT, "Relatório Acadêmico")
        relatorio_item.click()
        time.sleep(3)
        
        # Preenche parâmetros do relatório (exemplo)
        # driver.find_element(By.ID, "parametro").send_keys("valor")
        # time.sleep(1)
        
        # Clica para gerar o relatório
        gerar_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Gerar')]")
        gerar_btn.click()
        time.sleep(5)
        
        # Verifica se o relatório foi gerado
        return "Relatório gerado com sucesso" in driver.page_source
    except Exception as e:
        st.error(f"Erro na navegação: {e}")
        return False

def main():
    st.title("Automação de Relatório UFF")
    st.markdown("### Insira suas credenciais para acessar o sistema")
    
    username = st.text_input("idUFF (CPF, email ou passaporte)")
    password = st.text_input("Senha", type="password")
    
    if st.button("Acessar e Gerar Relatório"):
        if not username or not password:
            st.error("Por favor, preencha todos os campos.")
            return
        
        with st.spinner("Conectando ao sistema..."):
            driver = init_driver()
            
            # Etapa 1: Login
            if login(driver, username, password):
                st.success("Login realizado com sucesso!")
                
                # Etapa 2: Navegação até o relatório
                with st.spinner("Navegando para o relatório..."):
                    if navigate_to_report(driver):
                        st.success("Relatório gerado com sucesso!")
                        
                        # Você pode adicionar aqui a captura do relatório
                        # Exemplo: salvar a página ou fazer download do arquivo
                        # screenshot = driver.save_screenshot("relatorio.png")
                        # st.image("relatorio.png")
                    else:
                        st.error("Falha ao gerar o relatório.")
            else:
                st.error("Falha no login. Verifique suas credenciais.")
            
            driver.quit()

if __name__ == "__main__":
    main()
