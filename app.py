# app.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
import time
import re

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise de Evasão - UFF",
    page_icon="🎓",
    layout="wide"
)

# Inicialização de estado de sessão
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
if 'username' not in st.session_state:
    st.session_state.username = ""

# Funções para login
def extract_login_parameters(html_content):
    """Extrai parâmetros necessários para o login do HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Encontrar o formulário de login
    login_form = soup.find('form', {'id': 'kc-form-login'})
    
    if not login_form:
        return None
    
    # Extrair action URL
    action_url = login_form.get('action', '')
    
    # Extrair campos ocultos (se houver)
    hidden_inputs = {}
    for input_tag in login_form.find_all('input', type='hidden'):
        name = input_tag.get('name', '')
        value = input_tag.get('value', '')
        if name:
            hidden_inputs[name] = value
    
    return {
        'action_url': action_url,
        'hidden_fields': hidden_inputs
    }

def perform_login(session, base_url, username, password):
    """Realiza o login no sistema da UFF"""
    
    # Primeira requisição para obter a página de login
    try:
        login_page_url = "https://app.uff.br/graduacao/administracaoacademica"
        response = session.get(login_page_url, timeout=10)
        
        if response.status_code != 200:
            st.error(f"Erro ao acessar página de login: {response.status_code}")
            return False
        
        # Extrair parâmetros do formulário
        login_params = extract_login_parameters(response.text)
        
        if not login_params:
            st.error("Não foi possível encontrar o formulário de login")
            return False
        
        # Preparar dados do formulário
        form_data = {
            'username': username,
            'password': password,
            'rememberMe': 'on'
        }
        
        # Adicionar campos ocultos
        if login_params['hidden_fields']:
            form_data.update(login_params['hidden_fields'])
        
        # Enviar requisição de login
        login_action = login_params['action_url']
        
        # Se a action_url for relativa, converter para absoluta
        if login_action.startswith('/'):
            # Extrair domínio base da URL original
            from urllib.parse import urlparse
            parsed_base = urlparse(base_url)
            login_action = f"{parsed_base.scheme}://{parsed_base.netloc}{login_action}"
        
        # Adicionar headers para simular navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': login_page_url,
            'Origin': 'https://app.uff.br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        login_response = session.post(
            login_action,
            data=form_data,
            headers=headers,
            allow_redirects=True,
            timeout=15
        )
        
        # Verificar se login foi bem sucedido
        # Podemos verificar pela presença de elementos da página logada
        # ou pela URL após redirecionamento
        if login_response.status_code == 200:
            # Verificar se estamos na página do sistema acadêmico
            if "administracaoacademica" in login_response.url or "portal" in login_response.url:
                return True
            else:
                # Verificar se há mensagem de erro
                soup = BeautifulSoup(login_response.text, 'html.parser')
                error_div = soup.find('div', {'class': 'alert-error'}) or soup.find('span', {'class': 'kc-feedback-text'})
                if error_div:
                    st.error(f"Erro de login: {error_div.get_text(strip=True)}")
                return False
        
        return False
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na conexão: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Erro inesperado: {str(e)}")
        return False

def logout():
    """Limpa a sessão e faz logout"""
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.session = requests.Session()
    st.rerun()

# Interface principal
def main():
    st.title("🎓 Sistema de Análise de Evasão - UFF")
    
    if not st.session_state.authenticated:
        # Página de login
        st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
        st.markdown("Para acessar os relatórios de evasão, faça login com suas credenciais da UFF.")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form"):
                username = st.text_input("Identificação (idUFF)", 
                                        placeholder="CPF, email ou passaporte")
                password = st.text_input("Senha", 
                                        type="password",
                                        placeholder="Sua senha da UFF")
                remember_me = st.checkbox("Manter conectado", value=False)
                
                submitted = st.form_submit_button("Acessar", type="primary")
                
                if submitted:
                    if not username or not password:
                        st.error("Por favor, preencha todos os campos")
                    else:
                        with st.spinner("Conectando ao sistema da UFF..."):
                            if perform_login(st.session_state.session, 
                                           "https://app.uff.br", 
                                           username, 
                                           password):
                                st.session_state.authenticated = True
                                st.session_state.username = username
                                st.success("Login realizado com sucesso!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Falha no login. Verifique suas credenciais.")
            
            st.markdown("---")
            st.markdown("""
            **Ajuda:**
            - Utilize sua identificação UFF (CPF, email ou passaporte)
            - Em caso de problemas, entre em contato com a central de atendimento
            - Telefone: (21) 2629-2042 opção 3
            - E-mail: [atendimento@id.uff.br](mailto:atendimento@id.uff.br)
            """)
    
    else:
        # Página principal após login
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ Logado como: {st.session_state.username}")
        
        with col2:
            if st.button("🚪 Sair", type="secondary"):
                logout()
        
        st.markdown("---")
        
        # Placeholder para as próximas etapas
        st.info("""
        **Login realizado com sucesso!** 
        
        As próximas etapas serão implementadas conforme solicitado:
        1. ✅ **Etapa 1 - Login** - Concluída
        2. 🔄 **Etapa 2 - Seleção de Período** - Em breve
        3. ⏳ **Etapa 3 - Consulta de Relatórios**
        4. ⏳ **Etapa 4 - Processamento dos Dados**
        5. ⏳ **Etapa 5 - Geração da Planilha**
        """)
        
        # Adicionar botão para continuar (quando implementado)
        st.markdown("---")
        st.markdown("### 📋 Próximos Passos")
        
        # Exemplo de como a próxima etapa será estruturada
        with st.expander("Pré-visualização da Etapa 2 - Seleção de Período"):
            st.markdown("""
            **Interface de seleção de período:**
            
            ```python
            periodo_inicial = st.selectbox("Período Inicial", 
                                         options=["2025.2", "2025.1", "2024.2"])
            periodo_final = st.selectbox("Período Final", 
                                       options=["2025.2", "2025.1", "2024.2"])
            ```
            
            **Validações:**
            - Período final não pode ser anterior ao inicial
            - Formato deve ser AAAA.S (ano.semestre)
            - Consulta apenas para períodos disponíveis no sistema
            """)
        
        # Informações técnicas
        with st.expander("📊 Informações Técnicas da Sessão"):
            st.code(f"""
            Status: Autenticado
            Usuário: {st.session_state.username}
            Cookies: {len(st.session_state.session.cookies)} cookies ativos
            User-Agent: {st.session_state.session.headers.get('User-Agent', 'Não definido')}
            """)

if __name__ == "__main__":
    main()
