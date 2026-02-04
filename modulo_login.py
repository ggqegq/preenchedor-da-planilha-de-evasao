"""
Módulo de Login - Autenticação no sistema acadêmico da UFF
Versão atualizada para Keycloak
"""

import time
import logging
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configurar_driver_chrome(headless=False):  # Alterado para False para debug
    """Configura o driver do Chrome para automação"""
    try:
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless=new")  # Nova sintaxe headless
        
        # Configurações para evitar detecção como bot
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configurações gerais
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        
        # User agent realista
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Desabilitar logs excessivos
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        # Preferências para download
        prefs = {
            "download.default_directory": r"C:\Users\Public\Downloads",  # Altere conforme necessário
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Executar script para esconder automação
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        logger.error(f"Erro ao configurar o Chrome: {e}")
        st.error(f"Erro ao configurar o navegador: {str(e)}")
        return None

def verificar_pagina_login(driver):
    """Verifica se estamos na página de login correta"""
    try:
        # Verificar por elementos comuns do Keycloak
        elementos_chave = [
            "username",  # ID comum
            "password",  # ID comum
            "kc-login",  # ID do botão
            "//*[contains(text(), 'Entrar')]",  # Texto em português
            "//*[contains(text(), 'Login')]",  # Texto em inglês
            "//*[contains(text(), 'Sign in')]"  # Texto alternativo
        ]
        
        for elemento in elementos_chave:
            try:
                if elemento.startswith("//"):
                    driver.find_element(By.XPATH, elemento)
                else:
                    driver.find_element(By.ID, elemento)
                return True
            except:
                continue
        
        # Verificar por iframe
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)
                time.sleep(1)
                if driver.find_elements(By.ID, "username"):
                    driver.switch_to.default_content()
                    return True
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
        
        return False
    except Exception as e:
        logger.error(f"Erro ao verificar página de login: {e}")
        return False

def realizar_login_keycloak(driver, usuario, senha):
    """Tenta realizar login via formulário Keycloak"""
    try:
        logger.info("Tentando login via formulário Keycloak...")
        
        # Tentar diferentes abordagens para encontrar os campos
        
        # Abordagem 1: Procurar por IDs comuns
        try:
            campo_usuario = driver.find_element(By.ID, "username")
            campo_senha = driver.find_element(By.ID, "password")
            botao_login = driver.find_element(By.ID, "kc-login")
            logger.info("Campos encontrados por ID")
        except:
            # Abordagem 2: Procurar por name
            try:
                campo_usuario = driver.find_element(By.NAME, "username")
                campo_senha = driver.find_element(By.NAME, "password")
                botao_login = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                logger.info("Campos encontrados por name")
            except:
                # Abordagem 3: Procurar por XPath
                try:
                    campo_usuario = driver.find_element(By.XPATH, "//input[@type='text' or @type='email']")
                    campo_senha = driver.find_element(By.XPATH, "//input[@type='password']")
                    botao_login = driver.find_element(By.XPATH, "//button[@type='submit']")
                    logger.info("Campos encontrados por XPath")
                except:
                    # Abordagem 4: Procurar por qualquer input
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    if len(inputs) >= 2:
                        campo_usuario = inputs[0]
                        campo_senha = inputs[1]
                        botao_login = driver.find_element(By.XPATH, "//button[contains(text(), 'Entrar') or contains(text(), 'Login')]")
                        logger.info("Campos encontrados por tag input")
                    else:
                        raise NoSuchElementException("Campos de login não encontrados")
        
        # Preencher campos
        campo_usuario.clear()
        campo_usuario.send_keys(usuario)
        time.sleep(0.5)
        
        campo_senha.clear()
        campo_senha.send_keys(senha)
        time.sleep(0.5)
        
        # Clicar no botão
        botao_login.click()
        time.sleep(3)
        
        return True, "Login via Keycloak realizado"
        
    except Exception as e:
        logger.error(f"Erro no login Keycloak: {e}")
        return False, f"Erro no formulário Keycloak: {str(e)}"

def realizar_login(usuario, senha, modo_teste=False):
    """
    Realiza login no sistema acadêmico da UFF
    
    Args:
        usuario (str): CPF, email ou passaporte
        senha (str): Senha do IdUFF
        modo_teste (bool): Se True, apenas simula o login
    
    Returns:
        tuple: (sucesso, mensagem)
    """
    
    if modo_teste:
        # Modo de teste (para desenvolvimento)
        logger.info("Modo teste ativado, simulando login...")
        time.sleep(2)
        
        # Simular diferentes cenários
        if "erro" in usuario.lower():
            return False, "Credenciais inválidas (simulado)"
        elif "captcha" in usuario.lower():
            return False, "CAPTCHA detectado (simulado)"
        else:
            return True, "Login simulado com sucesso"
    
    driver = None
    screenshots_tiradas = []
    
    try:
        # Configurar driver (não headless para debug)
        logger.info("Configurando driver Chrome...")
        driver = configurar_driver_chrome(headless=False)  # False para ver o que acontece
        
        if not driver:
            return False, "Falha ao configurar o navegador"
        
        # URL do sistema acadêmico UFF
        urls_tentativas = [
            "https://id.uff.br/",  # Nova URL
            "https://id.uff.br/id/XUI/#login/",
            "https://app.uff.br/",
            "https://app.uff.br/graduacao/AdministracaoAcademica"
        ]
        
        sucesso_login = False
        mensagem_login = ""
        
        for url in urls_tentativas:
            try:
                logger.info(f"Acessando: {url}")
                driver.get(url)
                time.sleep(3)
                
                # Tirar screenshot para debug
                screenshot_path = f"debug_login_{len(screenshots_tiradas)}.png"
                driver.save_screenshot(screenshot_path)
                screenshots_tiradas.append(screenshot_path)
                logger.info(f"Screenshot salvo: {screenshot_path}")
                
                # Verificar se estamos na página de login
                if verificar_pagina_login(driver):
                    logger.info("Página de login detectada")
                    
                    # Tentar login via Keycloak
                    sucesso_login, mensagem_login = realizar_login_keycloak(driver, usuario, senha)
                    
                    if sucesso_login:
                        # Aguardar redirecionamento
                        time.sleep(5)
                        
                        # Tirar screenshot pós-login
                        driver.save_screenshot("debug_pos_login.png")
                        
                        # Verificar se login foi bem-sucedido
                        current_url = driver.current_url
                        page_source = driver.page_source[:1000]  # Primeiros 1000 chars
                        
                        logger.info(f"URL atual: {current_url}")
                        logger.info(f"Page source preview: {page_source[:500]}...")
                        
                        # Verificar indicadores de sucesso
                        indicadores_sucesso = [
                            "admin", "academico", "dashboard", "painel",
                            "menu", "sistema", "graduacao", "relatorios"
                        ]
                        
                        indicadores_erro = [
                            "error", "invalid", "incorreto", "incorrect",
                            "falhou", "failed", "tente novamente"
                        ]
                        
                        # Verificar se há elementos indicando erro
                        elementos_erro = driver.find_elements(
                            By.XPATH, 
                            "//*[contains(text(), 'erro') or contains(text(), 'Erro') or "
                            "contains(text(), 'inválido') or contains(text(), 'incorreto')]"
                        )
                        
                        if elementos_erro:
                            erro_texto = elementos_erro[0].text if elementos_erro else ""
                            return False, f"Erro no login: {erro_texto}"
                        
                        # Verificar por URL ou conteúdo indicando sucesso
                        sucesso_detectado = False
                        for indicador in indicadores_sucesso:
                            if indicador in current_url.lower() or indicador in page_source.lower():
                                sucesso_detectado = True
                                break
                        
                        if sucesso_detectado:
                            logger.info("Login aparentemente bem-sucedido")
                            
                            # Navegar para relatórios
                            try:
                                relatorios_url = "https://app.uff.br/graduacao/AdministracaoAcademica/relatorios/site"
                                driver.get(relatorios_url)
                                time.sleep(3)
                                
                                if "relatorios" in driver.current_url:
                                    logger.info("Acesso à página de relatórios confirmado")
                                    driver.quit()
                                    return True, "Login realizado com sucesso"
                                else:
                                    logger.warning("Não conseguiu acessar relatórios, mas login pode ter funcionado")
                                    driver.quit()
                                    return True, "Login realizado, mas não foi possível acessar relatórios diretamente"
                            except:
                                driver.quit()
                                return True, "Login realizado com sucesso"
                        else:
                            # Verificar se ainda está na página de login
                            if verificar_pagina_login(driver):
                                return False, "Credenciais inválidas ou sistema não respondeu"
                            else:
                                # Pode ter redirecionado para outra página
                                logger.info("Redirecionado para página desconhecida")
                                driver.quit()
                                return True, "Login realizado (redirecionamento detectado)"
                    
                    # Se chegou aqui, o login falhou nesta URL
                    logger.warning(f"Falha no login para URL: {url}")
                    continue
                
            except Exception as e:
                logger.error(f"Erro ao acessar {url}: {e}")
                continue
        
        # Se tentou todas as URLs e não conseguiu
        if not sucesso_login:
            return False, "Não foi possível acessar o sistema. Verifique a conexão ou tente mais tarde."
        
        return sucesso_login, mensagem_login
    
    except TimeoutException:
        logger.error("Timeout durante o login")
        if driver:
            driver.quit()
        return False, "Tempo limite excedido. O sistema pode estar lento."
    
    except WebDriverException as e:
        logger.error(f"Erro no WebDriver: {e}")
        if driver:
            driver.quit()
        return False, f"Erro no navegador: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        if driver:
            driver.quit()
        return False, f"Erro inesperado: {str(e)}"
    
    finally:
        # Limpar screenshots de debug (opcional)
        for screenshot in screenshots_tiradas:
            try:
                import os
                if os.path.exists(screenshot):
                    os.remove(screenshot)
            except:
                pass

def verificar_sessao_ativa():
    """Verifica se a sessão ainda está ativa"""
    # Implementação futura: verificar cookies/sessão
    return st.session_state.get('logado', False)

def logout():
    """Realiza logout do sistema"""
    # Limpar estado da sessão
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.modo_manual = False
    
    return True

# Função auxiliar para debug
def debug_pagina_login():
    """Função para debug do sistema de login"""
    import streamlit as st
    
    st.subheader("🔍 Debug do Sistema de Login")
    
    url_teste = st.text_input("URL para testar:", "https://id.uff.br/")
    
    if st.button("Testar URL"):
        driver = configurar_driver_chrome(headless=False)
        if driver:
            try:
                driver.get(url_teste)
                time.sleep(3)
                
                # Salvar informações
                st.write(f"**URL atual:** {driver.current_url}")
                st.write(f"**Título:** {driver.title}")
                
                # Capturar screenshot
                screenshot_path = "debug_url_teste.png"
                driver.save_screenshot(screenshot_path)
                
                # Exibir screenshot
                st.image(screenshot_path, caption="Screenshot da página")
                
                # Analisar elementos da página
                st.write("**Elementos encontrados:**")
                
                # Procurar formulários
                forms = driver.find_elements(By.TAG_NAME, "form")
                st.write(f"Formulários: {len(forms)}")
                
                for i, form in enumerate(forms):
                    st.write(f"Formulário {i+1}:")
                    st.code(form.get_attribute('outerHTML')[:500])
                
                # Procurar inputs
                inputs = driver.find_elements(By.TAG_NAME, "input")
                st.write(f"Inputs: {len(inputs)}")
                
                for i, input_elem in enumerate(inputs[:10]):  # Mostrar apenas os 10 primeiros
                    st.write(f"Input {i+1}:")
                    st.write(f"  Tipo: {input_elem.get_attribute('type')}")
                    st.write(f"  Name: {input_elem.get_attribute('name')}")
                    st.write(f"  ID: {input_elem.get_attribute('id')}")
                
                driver.quit()
                
            except Exception as e:
                st.error(f"Erro: {e}")
                if driver:
                    driver.quit()
