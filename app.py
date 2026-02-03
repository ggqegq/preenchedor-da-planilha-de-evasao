import streamlit as st
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Configurações para evitar detecção de bot
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Para ambiente do Streamlit Cloud
    if os.environ.get('STREAMLIT_SHARING_MODE') or os.environ.get('STREAMLIT_SERVER_HEADLESS'):
        chrome_options.binary_location = '/usr/bin/chromium-browser'
    
    try:
        # Tenta usar webdriver_manager para gerenciar o driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Script para evitar detecção
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        st.error(f"Erro ao iniciar o driver: {e}")
        # Fallback: tenta com driver já instalado
        try:
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except:
            st.error("Não foi possível iniciar o ChromeDriver. Verifique se o Chrome está instalado.")
            return None

def login(driver, username, password):
    try:
        driver.get("https://app.uff.br/graduacao/administracaoacademica")
        
        # Aguarda o carregamento da página
        time.sleep(3)
        
        # Verifica qual página estamos
        if "id.uff.br" in driver.current_url or "login" in driver.current_url.lower():
            # Tenta encontrar o campo de login por vários seletores possíveis
            wait = WebDriverWait(driver, 10)
            
            # Tenta diferentes seletores para o campo de usuário
            selectors = [
                ("id", "idUFF"),
                ("name", "username"),
                ("name", "user"),
                ("name", "email"),
                ("css", "input[type='text']"),
                ("css", "input[type='email']"),
                ("xpath", "//input[@placeholder='CPF, email, passaporte']")
            ]
            
            username_field = None
            for by, value in selectors:
                try:
                    if by == "id":
                        username_field = wait.until(EC.presence_of_element_located((By.ID, value)))
                    elif by == "name":
                        username_field = wait.until(EC.presence_of_element_located((By.NAME, value)))
                    elif by == "css":
                        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, value)))
                    elif by == "xpath":
                        username_field = wait.until(EC.presence_of_element_located((By.XPATH, value)))
                    if username_field:
                        break
                except:
                    continue
            
            if not username_field:
                # Tira um screenshot para debug
                driver.save_screenshot("login_page.png")
                st.image("login_page.png", caption="Página de Login")
                return False, "Não foi possível encontrar o campo de usuário"
            
            # Preenche o campo de usuário
            username_field.clear()
            username_field.send_keys(username)
            
            # Encontra o campo de senha
            password_selectors = [
                ("id", "senha"),
                ("name", "password"),
                ("name", "pass"),
                ("css", "input[type='password']"),
                ("xpath", "//input[@type='password']")
            ]
            
            password_field = None
            for by, value in password_selectors:
                try:
                    if by == "id":
                        password_field = driver.find_element(By.ID, value)
                    elif by == "name":
                        password_field = driver.find_element(By.NAME, value)
                    elif by == "css":
                        password_field = driver.find_element(By.CSS_SELECTOR, value)
                    elif by == "xpath":
                        password_field = driver.find_element(By.XPATH, value)
                    if password_field:
                        break
                except:
                    continue
            
            if not password_field:
                return False, "Não foi possível encontrar o campo de senha"
            
            password_field.clear()
            password_field.send_keys(password)
            
            # Encontra e clica no botão de login
            button_selectors = [
                ("xpath", "//button[contains(text(), 'ACESSAR')]"),
                ("xpath", "//button[@type='submit']"),
                ("css", "button[type='submit']"),
                ("xpath", "//input[@type='submit']"),
                ("css", "input[type='submit']")
            ]
            
            login_button = None
            for by, value in button_selectors:
                try:
                    if by == "xpath":
                        login_button = driver.find_element(By.XPATH, value)
                    elif by == "css":
                        login_button = driver.find_element(By.CSS_SELECTOR, value)
                    if login_button:
                        break
                except:
                    continue
            
            if login_button:
                login_button.click()
            else:
                # Tenta enviar o formulário
                password_field.submit()
            
            # Aguarda o login
            time.sleep(5)
            
            # Verifica se o login foi bem-sucedido
            if "login" in driver.current_url.lower() or "id.uff.br" in driver.current_url:
                # Verifica se há mensagem de erro
                error_messages = driver.find_elements(By.CSS_SELECTOR, ".error, .alert, .mensagem-erro")
                if error_messages:
                    return False, f"Erro no login: {error_messages[0].text}"
                return False, "Login falhou. Verifique suas credenciais."
            
            return True, "Login realizado com sucesso!"
            
        else:
            # Já está logado ou em outra página
            return True, "Já autenticado"
            
    except Exception as e:
        return False, f"Erro durante o login: {str(e)}"

def main():
    st.set_page_config(page_title="Automação UFF", page_icon="🎓")
    
    st.title("🎓 Automação de Sistema UFF")
    st.markdown("### Acesso ao Sistema de Graduação")
    
    with st.expander("ℹ️ Instruções"):
        st.info("""
        1. Insira suas credenciais do idUFF
        2. Clique em 'Acessar Sistema'
        3. Aguarde o login automático
        4. Após login, você poderá navegar até os relatórios
        """)
    
    # Credenciais
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Identificação (CPF, email ou passaporte)", key="username")
    with col2:
        password = st.text_input("Senha", type="password", key="password")
    
    maintain_login = st.checkbox("Manter conectado", value=False)
    
    if st.button("🔐 Acessar Sistema", type="primary"):
        if not username or not password:
            st.error("Por favor, preencha todos os campos.")
            return
        
        # Inicializa o driver
        with st.spinner("Iniciando navegador..."):
            driver = init_driver()
            
        if driver:
            # Realiza o login
            with st.spinner("Realizando login..."):
                success, message = login(driver, username, password)
                
                if success:
                    st.success(message)
                    
                    # Mostra informações da página atual
                    st.info(f"Página atual: {driver.current_url}")
                    
                    # Tira screenshot da página após login
                    driver.save_screenshot("after_login.png")
                    
                    with st.expander("📸 Visualizar página após login"):
                        st.image("after_login.png", caption="Página após login", use_column_width=True)
                    
                    # Aqui você pode adicionar a navegação para os relatórios
                    st.session_state['driver'] = driver
                    st.session_state['logged_in'] = True
                    
                    # Opções de navegação
                    st.markdown("### 📊 Navegação para Relatórios")
                    
                    # Você pode adicionar botões para diferentes ações
                    if st.button("🧭 Navegar para Relatórios Acadêmicos"):
                        with st.spinner("Navegando para relatórios..."):
                            # Exemplo de navegação
                            try:
                                # Tenta encontrar links de relatórios
                                report_links = driver.find_elements(By.PARTIAL_LINK_TEXT, "Relat")
                                if report_links:
                                    report_links[0].click()
                                    time.sleep(3)
                                    st.success("Navegado para seção de relatórios!")
                                    
                                    # Mostra conteúdo atual
                                    st.code(driver.page_source[:2000], language='html')
                                else:
                                    st.warning("Não foram encontrados links de relatórios na página.")
                            except Exception as e:
                                st.error(f"Erro na navegação: {e}")
                    
                else:
                    st.error(message)
                    
                # Opção para fechar o driver
                if st.button("🚪 Sair do Sistema"):
                    driver.quit()
                    if 'driver' in st.session_state:
                        del st.session_state['driver']
                    st.session_state['logged_in'] = False
                    st.success("Sessão encerrada!")
        else:
            st.error("Não foi possível iniciar o navegador automático.")

    # Seção de ajuda
    st.markdown("---")
    st.markdown("### 📞 Suporte")
    st.markdown("""
    Em caso de dúvidas:
    - Telefone: (21) 2629-2042 opção 3
    - E-mail: atendimento@id.uff.br
    """)

if __name__ == "__main__":
    main()
