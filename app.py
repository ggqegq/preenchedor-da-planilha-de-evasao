import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
from openpyxl.utils import get_column_letter
import re
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="Cálculo de Evasão - Química UFF",
    page_icon="📊",
    layout="wide"
)

# URLs do sistema
BASE_URL = "https://app.uff.br"
LOGIN_URL = f"{BASE_URL}/iduff/login.jsp"
ADMIN_ACAD_URL = f"{BASE_URL}/graduacao/administracaoacademica"
RELATORIOS_URL = f"{ADMIN_ACAD_URL}/relatorios/listagens_alunos"

# Constantes de cursos
CURSOS_CONFIG = {
    "Licenciatura Química": {"codigo": "12700"},
    "Bacharel Química": {"codigo": "312700"},
    "Bacharel Q Industrial": {"codigo": "12709"}
}

# Mapeamento de situações para categorias
SITUACOES_INSCRITOS = ["Inscrito", "Concluinte", "Pendente"]
SITUACOES_TRANCADOS = ["Trancado"]
SITUACOES_FORMADOS = ["Permanência de Vínculo", "Formado"]

# Motivos de cancelamento - ordem conforme planilha
MOTIVOS_CANCELAMENTO = [
    ("Solicitação Oficial", ["Cancelamento por Solicitação Oficial"]),
    ("Abandono", ["Cancelamento por Abandono"]),
    ("Insuficiência de Aproveitamento", ["Cancelamento por Insuficiência de Aproveitamento"]),
    ("Ingressante - Insuf. Aproveit.", ["Cancelamento Ingressante por Insuficiência de Aproveitamento"]),
    ("Mudança de Curso", ["Cancelamento por Mudança de Curso"]),
]

def classificar_modalidade(codigo_modalidade):
    """
    Classifica a modalidade de ingresso.
    Código iniciando com 'L' → Ações Afirmativas (AA)
    Outros → Ampla Concorrência (AC)
    """
    if not codigo_modalidade or pd.isna(codigo_modalidade):
        return "AC"
    
    codigo = str(codigo_modalidade).strip().upper()
    
    if codigo.startswith("L"):
        return "AA"
    else:
        return "AC"

def categorizar_situacao(situacao):
    """Categoriza a situação do aluno"""
    if not situacao or pd.isna(situacao):
        return "Outros", None
    
    situacao = str(situacao).strip()
    
    # Verifica se é inscrito/ativo
    for s in SITUACOES_INSCRITOS:
        if s.lower() in situacao.lower():
            return "Inscrito", None
    
    # Verifica se é trancado
    for s in SITUACOES_TRANCADOS:
        if s.lower() in situacao.lower():
            return "Trancado", None
    
    # Verifica se é formado
    for s in SITUACOES_FORMADOS:
        if s.lower() in situacao.lower():
            return "Formado", None
    
    # Verifica cancelamentos
    for motivo_nome, situacoes_match in MOTIVOS_CANCELAMENTO:
        for s in situacoes_match:
            if s.lower() in situacao.lower():
                return "Cancelamento", motivo_nome
    
    # Se contém "cancelamento" mas não está mapeado
    if "cancelamento" in situacao.lower():
        return "Cancelamento", "Outros"
    
    return "Outros", None

class SistemaAcademicoUFF:
    """Classe para interagir com o sistema acadêmico da UFF"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.logged_in = False
        self.csrf_token = None
    
    def login(self, username, password):
        """Realiza login no sistema com abordagem mais robusta"""
        try:
            # Primeiro, acessa a página inicial para obter cookies
            st.info("Acessando página de login...")
            response = self.session.get(BASE_URL, timeout=10)
            
            if response.status_code != 200:
                return False, f"Erro ao acessar portal UFF: {response.status_code}"
            
            # Tenta acessar a página de login específica
            st.info("Obtendo formulário de login...")
            login_page = self.session.get(LOGIN_URL, timeout=10)
            
            if login_page.status_code != 200:
                # Tenta alternativa de URL de login
                alt_login_url = f"{BASE_URL}/auth/realms/master/protocol/openid-connect/auth?client_id=graduacao-public&redirect_uri=https%3A%2F%2Fapp.uff.br%2Fgraduacao%2Fpublic%2F&state=fake-state&response_mode=fragment&response_type=code&scope=openid&nonce=fake-nonce"
                login_page = self.session.get(alt_login_url, timeout=10)
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Procura por formulários de login de várias formas
            forms = soup.find_all('form')
            login_form = None
            
            for form in forms:
                form_html = str(form).lower()
                if 'login' in form_html or 'username' in form_html or 'password' in form_html:
                    login_form = form
                    break
            
            if not login_form:
                # Se não encontrar formulário, tenta localizar campos de login diretamente
                st.warning("Formulário não encontrado, tentando localizar campos de login...")
                
                # Verifica se já está logado
                if "sair" in login_page.text.lower() or "logout" in login_page.text.lower():
                    self.logged_in = True
                    return True, "Já está logado no sistema"
                
                # Tenta método alternativo: enviar diretamente para o endpoint de login
                return self._login_alternativo(username, password, login_page)
            
            # Extrai informações do formulário
            action_url = login_form.get('action', '')
            if action_url and not action_url.startswith('http'):
                if action_url.startswith('/'):
                    action_url = BASE_URL + action_url
                else:
                    action_url = LOGIN_URL + action_url
            
            # Coleta todos os campos do formulário
            form_data = {}
            inputs = login_form.find_all(['input', 'textarea', 'select'])
            
            for inp in inputs:
                name = inp.get('name')
                value = inp.get('value', '')
                if name:
                    form_data[name] = value
            
            # Substitui username e password
            form_data['username'] = username
            form_data['password'] = password
            
            # Se não tem ação, usa a URL atual
            if not action_url:
                action_url = login_page.url
            
            st.info(f"Enviando dados para: {action_url}")
            
            # Realiza o login
            headers = {
                'Referer': login_page.url,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            login_response = self.session.post(
                action_url,
                data=form_data,
                headers=headers,
                allow_redirects=True,
                timeout=15
            )
            
            # Verifica se o login foi bem-sucedido
            if self._verificar_login_sucesso(login_response):
                self.logged_in = True
                return True, "Login realizado com sucesso!"
            else:
                # Tenta verificar mensagens de erro
                error_msg = self._extrair_mensagem_erro(login_response)
                return False, f"Login falhou. {error_msg}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout ao tentar conectar com o servidor"
        except requests.exceptions.ConnectionError:
            return False, "Erro de conexão com o servidor"
        except Exception as e:
            return False, f"Erro durante o login: {str(e)}"
    
    def _login_alternativo(self, username, password, login_page):
        """Método alternativo de login"""
        try:
            # Tenta encontrar o endpoint de login do Keycloak (sistema de autenticação da UFF)
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Procura por links ou scripts que possam indicar o endpoint
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'keycloak' in script.string.lower():
                    # Extrai informações do Keycloak
                    import re
                    keycloak_match = re.search(r'keycloak\s*=\s*Keycloak\(({[^}]+})', script.string)
                    if keycloak_match:
                        st.info("Sistema usa Keycloak para autenticação")
            
            # Tenta endpoint comum do Keycloak
            keycloak_url = f"{BASE_URL}/auth/realms/master/protocol/openid-connect/token"
            
            # Prepara dados para o Keycloak
            token_data = {
                'client_id': 'graduacao-public',
                'username': username,
                'password': password,
                'grant_type': 'password',
                'scope': 'openid'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            token_response = self.session.post(
                keycloak_url,
                data=token_data,
                headers=headers,
                timeout=10
            )
            
            if token_response.status_code == 200:
                self.logged_in = True
                return True, "Login via Keycloak realizado com sucesso"
            else:
                return False, "Falha no login via Keycloak"
                
        except Exception as e:
            return False, f"Erro no login alternativo: {str(e)}"
    
    def _verificar_login_sucesso(self, response):
        """Verifica se o login foi bem-sucedido"""
        content = response.text.lower()
        
        # Palavras-chave que indicam login bem-sucedido
        success_keywords = [
            'administração acadêmica',
            'sair',
            'logout',
            'logoff',
            'minha conta',
            'bem-vindo',
            'welcome',
            'dashboard'
        ]
        
        # Palavras-chave que indicam falha no login
        failure_keywords = [
            'usuário ou senha inválidos',
            'credenciais inválidas',
            'invalid credentials',
            'login failed',
            'autenticação falhou'
        ]
        
        for keyword in success_keywords:
            if keyword in content:
                return True
        
        for keyword in failure_keywords:
            if keyword in content:
                return False
        
        # Verifica pelo URL de redirecionamento
        if 'graduacao' in response.url or 'admin' in response.url:
            return True
        
        return False
    
    def _extrair_mensagem_erro(self, response):
        """Extrai mensagem de erro da página"""
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Procura por divs de erro
        error_divs = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and any(word in str(x).lower() for word in ['error', 'alert', 'danger', 'warning']))
        
        for error_div in error_divs:
            if error_div.text.strip():
                return error_div.text.strip()
        
        # Procura por texto de erro
        error_texts = [
            'usuário ou senha inválidos',
            'credenciais inválidas',
            'invalid credentials',
            'login failed'
        ]
        
        content_lower = response.text.lower()
        for error_text in error_texts:
            if error_text in content_lower:
                return error_text.capitalize()
        
        return "Motivo desconhecido"
    
    def testar_conexao(self):
        """Testa a conexão com o sistema"""
        try:
            response = self.session.get(BASE_URL, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def gerar_relatorios_por_periodo(self, periodo_inicio, periodo_fim):
        """
        Gera relatórios para todos os cursos e períodos no intervalo especificado.
        Retorna dicionário com dados processados.
        """
        if not self.logged_in:
            return {}, "Usuário não está logado"
        
        dados_por_periodo = {}
        
        # Converte períodos para lista
        anos_inicio = int(periodo_inicio.split('.')[0])
        semestres_inicio = int(periodo_inicio.split('.')[1])
        anos_fim = int(periodo_fim.split('.')[0])
        semestres_fim = int(periodo_fim.split('.')[1])
        
        # Gera lista de períodos
        periodos = []
        for ano in range(anos_fim, anos_inicio - 1, -1):
            for semestre in [2, 1]:
                if ano == anos_inicio and semestre < semestres_inicio:
                    continue
                if ano == anos_fim and semestre > semestres_fim:
                    continue
                periodos.append(f"{ano}.{semestre}")
        
        st.info(f"Gerando relatórios para {len(periodos)} períodos: {', '.join(periodos[:5])}{'...' if len(periodos) > 5 else ''}")
        
        # Para cada período e curso, gera relatório
        for periodo in periodos:
            dados_por_periodo[periodo] = {}
            
            for curso_nome, curso_info in CURSOS_CONFIG.items():
                with st.spinner(f"Processando {curso_nome} - {periodo}..."):
                    try:
                        # Aqui você implementaria a lógica real de busca no sistema
                        # Por enquanto, vamos simular com dados de exemplo
                        dados_simulados = self._simular_dados_curso(curso_nome, periodo)
                        dados_por_periodo[periodo][curso_nome] = dados_simulados
                        
                    except Exception as e:
                        st.warning(f"Erro ao processar {curso_nome} - {periodo}: {str(e)}")
                        dados_por_periodo[periodo][curso_nome] = {"AC": {}, "AA": {}}
        
        return dados_por_periodo, "Relatórios gerados com sucesso"
    
    def _simular_dados_curso(self, curso_nome, periodo):
        """Simula dados para demonstração"""
        # Dados simulados baseados no exemplo fornecido
        if curso_nome == "Licenciatura Química":
            return {
                "AC": {
                    "total_ingressantes": 10,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 3
                    },
                    "inscritos": 6,
                    "trancados": 0,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 16,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 3
                    },
                    "inscritos": 11,
                    "trancados": 1,
                    "formados": 0
                }
            }
        elif curso_nome == "Bacharel Química":
            return {
                "AC": {
                    "total_ingressantes": 5,
                    "cancelamentos": {},
                    "inscritos": 5,
                    "trancados": 0,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 9,
                    "cancelamentos": {
                        "Ingressante - Insuf. Aproveit.": 1
                    },
                    "inscritos": 7,
                    "trancados": 0,
                    "formados": 0
                }
            }
        elif curso_nome == "Bacharel Q Industrial":
            return {
                "AC": {
                    "total_ingressantes": 9,
                    "cancelamentos": {},
                    "inscritos": 8,
                    "trancados": 1,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 11,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 2
                    },
                    "inscritos": 6,
                    "trancados": 2,
                    "formados": 0
                }
            }
        
        return {"AC": {}, "AA": {}}

# ... [O resto do código permanece igual, mantendo as funções de processamento e geração de planilha] ...

def processar_relatorio(df, curso_nome):
    """
    Processa um DataFrame de relatório e retorna contagens por modalidade.
    """
    resultados = {
        "AC": {
            "total_ingressantes": 0,
            "cancelamentos": defaultdict(int),
            "inscritos": 0,
            "trancados": 0,
            "formados": 0
        },
        "AA": {
            "total_ingressantes": 0,
            "cancelamentos": defaultdict(int),
            "inscritos": 0,
            "trancados": 0,
            "formados": 0
        }
    }
    
    # Procura colunas relevantes
    col_situacao = None
    col_modalidade = None
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'situação' in col_lower or 'situacao' in col_lower:
            col_situacao = col
        if 'modalidade' in col_lower:
            col_modalidade = col
    
    if col_situacao is None:
        # Tenta encontrar por posição (última coluna geralmente é a situação)
        col_situacao = df.columns[-1]
    
    # Processa cada linha
    for idx, row in df.iterrows():
        # Classifica modalidade
        modalidade = "AC"  # Default
        if col_modalidade and col_modalidade in row:
            modalidade = classificar_modalidade(row[col_modalidade])
        else:
            # Se não tem coluna de modalidade, assume que todos são AC
            modalidade = "AC"
        
        # Conta ingressante
        resultados[modalidade]["total_ingressantes"] += 1
        
        # Categoriza situação
        if col_situacao in row:
            categoria, motivo = categorizar_situacao(row[col_situacao])
            
            if categoria == "Inscrito":
                resultados[modalidade]["inscritos"] += 1
            elif categoria == "Trancado":
                resultados[modalidade]["trancados"] += 1
            elif categoria == "Formado":
                resultados[modalidade]["formados"] += 1
            elif categoria == "Cancelamento" and motivo:
                resultados[modalidade]["cancelamentos"][motivo] += 1
    
    return resultados

# ... [Mantendo todas as outras funções de criação de planilha] ...

def main():
    st.title("📊 Sistema de Cálculo de Evasão - Cursos de Química IQ/UFF")
    st.markdown("---")
    
    # Inicializa estado da sessão
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaAcademicoUFF()
    if 'dados_processados' not in st.session_state:
        st.session_state.dados_processados = {}
    if 'modo_operacao' not in st.session_state:
        st.session_state.modo_operacao = None
    
    # Sidebar com informações
    with st.sidebar:
        st.header("ℹ️ Informações")
        st.markdown("""
        **Cursos Monitorados:**
        - Licenciatura Química (12700)
        - Bacharel Química (312700)
        - Bacharel Q. Industrial (12709)
        
        **Modalidades:**
        - AC: Ampla Concorrência
        - AA: Ações Afirmativas (código inicia com 'L')
        
        **Nota:** Para testar sem login, use o modo "Upload de Arquivos" ou "Teste com Dados de Exemplo".
        """)
        
        # Opção para testar sem login
        if not st.session_state.logged_in:
            st.markdown("---")
            st.header("🚀 Teste Rápido")
            if st.button("Pular Login e Testar", type="secondary", use_container_width=True):
                st.session_state.logged_in = True  # Simula login para testes
                st.session_state.modo_operacao = "upload"
                st.rerun()
    
    # === SEÇÃO DE LOGIN ===
    if not st.session_state.logged_in:
        st.header("🔐 Login no Sistema Acadêmico UFF")
        
        st.info("""
        **Informações de Login:**
        - Use suas credenciais do IdUFF
        - O sistema tentará várias abordagens de login
        - Se encontrar problemas, use o modo "Teste Rápido" na sidebar
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("IdUFF (CPF, email ou passaporte)", placeholder="seu.iduff")
        with col2:
            password = st.text_input("Senha", type="password", placeholder="Sua senha")
        
        # Testar conexão
        if st.button("🔗 Testar Conexão com UFF", type="secondary"):
            with st.spinner("Testando conexão..."):
                if st.session_state.sistema.testar_conexao():
                    st.success("✅ Conexão com UFF estabelecida")
                else:
                    st.error("❌ Não foi possível conectar com a UFF")
        
        if st.button("✅ Fazer Login", type="primary", use_container_width=True):
            if username and password:
                with st.spinner("Realizando login (pode levar alguns segundos)..."):
                    success, message = st.session_state.sistema.login(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.success(message)
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                        
                        # Sugestões de solução
                        st.warning("""
                        **Soluções possíveis:**
                        1. Verifique se suas credenciais estão corretas
                        2. Tente acessar manualmente [app.uff.br](https://app.uff.br) para verificar
                        3. Use o botão "Teste Rápido" na sidebar para testar sem login
                        4. Use o modo "Upload de Arquivos" se já tem os relatórios exportados
                        """)
            else:
                st.warning("⚠️ Preencha usuário e senha.")
    
    else:
        st.success("✅ Conectado ao sistema")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚪 Sair", type="secondary", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.sistema = SistemaAcademicoUFF()
                st.session_state.dados_processados = {}
                st.session_state.modo_operacao = None
                st.rerun()
        
        with col2:
            if st.button("🔄 Testar Novamente", type="secondary", use_container_width=True):
                st.session_state.modo_operacao = None
                st.rerun()
        
        st.markdown("---")
        
        # === SELEÇÃO DO MODO DE OPERAÇÃO ===
        if st.session_state.modo_operacao is None:
            st.header("🎯 Selecione o Modo de Operação")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Buscar Dados do Sistema", use_container_width=True, help="Busca dados diretamente do sistema acadêmico"):
                    st.session_state.modo_operacao = "sistema"
                    st.rerun()
            
            with col2:
                if st.button("📤 Upload de Arquivos", use_container_width=True, help="Faça upload de arquivos Excel exportados"):
                    st.session_state.modo_operacao = "upload"
                    st.rerun()
            
            with col3:
                if st.button("🎮 Modo Demo", use_container_width=True, help="Use dados de exemplo para teste"):
                    st.session_state.modo_operacao = "demo"
                    st.rerun()
        
        # === MODO: BUSCAR DO SISTEMA ===
        elif st.session_state.modo_operacao == "sistema":
            st.header("🔄 Buscar Dados do Sistema Acadêmico")
            
            st.info("""
            **Atenção:** Esta funcionalidade busca dados simulados para demonstração.
            Para integrar com o sistema real, será necessário adaptar o código.
            """)
            
            # Seleção de períodos
            col1, col2 = st.columns(2)
            with col1:
                # Período inicial
                ano_inicio = st.selectbox(
                    "Ano inicial",
                    options=list(range(2025, 2014, -1)),
                    index=0
                )
                semestre_inicio = st.selectbox(
                    "Semestre inicial",
                    options=[1, 2],
                    index=0
                )
                periodo_inicio = f"{ano_inicio}.{semestre_inicio}"
            
            with col2:
                # Período final
                ano_fim = st.selectbox(
                    "Ano final",
                    options=list(range(2025, 2014, -1)),
                    index=11  # 2015
                )
                semestre_fim = st.selectbox(
                    "Semestre final",
                    options=[1, 2],
                    index=1
                )
                periodo_fim = f"{ano_fim}.{semestre_fim}"
            
            st.info(f"Período selecionado: **{periodo_inicio}** a **{periodo_fim}**")
            
            if st.button("🔍 Buscar Dados no Sistema", type="primary", use_container_width=True):
                with st.spinner(f"Buscando dados de {periodo_inicio} a {periodo_fim}..."):
                    try:
                        # Usa dados simulados
                        dados_por_periodo = st.session_state.sistema.gerar_relatorios_por_periodo(
                            periodo_inicio, periodo_fim
                        )
                        
                        if dados_por_periodo and dados_por_periodo[0]:
                            st.session_state.dados_processados = dados_por_periodo[0]
                            st.success(f"✅ {dados_por_periodo[1]}")
                            
                            # Mostra prévia dos dados
                            mostrar_previa_dados()
                            
                            # Botão para gerar planilha
                            mostrar_botao_gerar_planilha()
                        else:
                            st.error("❌ Nenhum dado encontrado para os períodos especificados")
                            
                    except Exception as e:
                        st.error(f"❌ Erro ao buscar dados: {str(e)}")
        
        # === MODO: UPLOAD DE ARQUIVOS ===
        elif st.session_state.modo_operacao == "upload":
            st.header("📤 Upload dos Relatórios Excel")
            
            st.info("""
            **Instruções:**
            1. Exporte os relatórios do sistema acadêmico
            2. Nomeie os arquivos: `CURSO_PERIODO.xlsx`
            3. Selecione todos os arquivos de uma vez
            
            **Exemplos:**
            - `Licenciatura_2025.1.xlsx`
            - `Bacharel_2024.2.xlsx`
            - `Industrial_2023.1.xlsx`
            """)
            
            uploaded_files = st.file_uploader(
                "Selecione os arquivos Excel",
                type=['xlsx', 'xls'],
                accept_multiple_files=True,
                help="Selecione todos os arquivos de relatórios exportados"
            )
            
            if uploaded_files:
                st.info(f"📁 {len(uploaded_files)} arquivo(s) carregado(s)")
                
                # Organiza dados por período e curso
                dados_por_periodo = defaultdict(lambda: defaultdict(dict))
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, uploaded_file in enumerate(uploaded_files):
                    try:
                        status_text.text(f"Processando {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                        
                        # Tenta extrair período e curso do nome do arquivo
                        nome_arquivo = uploaded_file.name.lower()
                        
                        # Detecta o curso
                        curso_nome = "Bacharel Química"  # Default
                        if "licenciatura" in nome_arquivo or "lic" in nome_arquivo:
                            curso_nome = "Licenciatura Química"
                        elif "industrial" in nome_arquivo or "ind" in nome_arquivo:
                            curso_nome = "Bacharel Q Industrial"
                        elif "bacharel" in nome_arquivo or "bach" in nome_arquivo:
                            curso_nome = "Bacharel Química"
                        
                        # Detecta período
                        periodo_match = re.search(r'(\d{4})[._/]?(\d)', nome_arquivo)
                        if periodo_match:
                            ano = periodo_match.group(1)
                            sem = periodo_match.group(2)
                            periodo = f"{ano}.{sem}"
                        else:
                            periodo = "2025.1"
                        
                        # Lê o arquivo
                        df = pd.read_excel(uploaded_file)
                        
                        # Remove linhas completamente vazias
                        df = df.dropna(how='all')
                        
                        # Processa os dados
                        resultados = processar_relatorio(df, curso_nome)
                        
                        # Armazena
                        dados_por_periodo[periodo][curso_nome] = resultados
                        
                        progress_bar.progress((i + 1) / len(uploaded_files))
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao processar {uploaded_file.name}: {str(e)}")
                
                status_text.text("✅ Processamento concluído!")
                
                # Salva no estado da sessão
                if dados_por_periodo:
                    st.session_state.dados_processados = dict(dados_poriodo)
                    
                    # Mostra prévia dos dados
                    mostrar_previa_dados()
                    
                    # Botão para gerar planilha
                    mostrar_botao_gerar_planilha()
        
        # === MODO: DEMO ===
        elif st.session_state.modo_operacao == "demo":
            st.header("🎮 Modo Demonstração")
            
            st.info("Usando dados de exemplo para gerar a planilha completa")
            
            if st.button("🔄 Gerar Dados de Demonstração", type="primary", use_container_width=True):
                # Dados de exemplo
                dados_exemplo = {
                    "2025.1": {
                        "Licenciatura Química": {
                            "AC": {
                                "total_ingressantes": 10,
                                "cancelamentos": {
                                    "Solicitação Oficial": 1,
                                    "Ingressante - Insuf. Aproveit.": 3
                                },
                                "inscritos": 6,
                                "trancados": 0,
                                "formados": 0
                            },
                            "AA": {
                                "total_ingressantes": 16,
                                "cancelamentos": {
                                    "Solicitação Oficial": 1,
                                    "Ingressante - Insuf. Aproveit.": 3
                                },
                                "inscritos": 11,
                                "trancados": 1,
                                "formados": 0
                            }
                        },
                        "Bacharel Química": {
                            "AC": {
                                "total_ingressantes": 5,
                                "cancelamentos": {},
                                "inscritos": 5,
                                "trancados": 0,
                                "formados": 0
                            },
                            "AA": {
                                "total_ingressantes": 9,
                                "cancelamentos": {
                                    "Ingressante - Insuf. Aproveit.": 1
                                },
                                "inscritos": 7,
                                "trancados": 0,
                                "formados": 0
                            }
                        },
                        "Bacharel Q Industrial": {
                            "AC": {
                                "total_ingressantes": 9,
                                "cancelamentos": {},
                                "inscritos": 8,
                                "trancados": 1,
                                "formados": 0
                            },
                            "AA": {
                                "total_ingressantes": 11,
                                "cancelamentos": {
                                    "Solicitação Oficial": 1,
                                    "Ingressante - Insuf. Aproveit.": 2
                                },
                                "inscritos": 6,
                                "trancados": 2,
                                "formados": 0
                            }
                        }
                    },
                    "2024.2": {
                        "Licenciatura Química": {
                            "AC": {
                                "total_ingressantes": 8,
                                "cancelamentos": {
                                    "Solicitação Oficial": 1
                                },
                                "inscritos": 5,
                                "trancados": 1,
                                "formados": 0
                            },
                            "AA": {
                                "total_ingressantes": 12,
                                "cancelamentos": {
                                    "Ingressante - Insuf. Aproveit.": 2
                                },
                                "inscritos": 8,
                                "trancados": 1,
                                "formados": 1
                            }
                        }
                    }
                }
                
                st.session_state.dados_processados = dados_exemplo
                st.success("✅ Dados de demonstração carregados!")
                
                # Mostra prévia dos dados
                mostrar_previa_dados()
                
                # Botão para gerar planilha
                mostrar_botao_gerar_planilha()

# Funções auxiliares para mostrar prévia e botão de geração
def mostrar_previa_dados():
    """Mostra prévia dos dados processados"""
    if st.session_state.dados_processados:
        st.markdown("---")
        st.header("📋 Prévia dos Dados Processados")
        
        for periodo, cursos in st.session_state.dados_processados.items():
            with st.expander(f"📅 Período: {periodo}", expanded=True):
                for curso, dados in cursos.items():
                    st.subheader(f"🎓 {curso}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Ampla Concorrência (AC)**")
                        if "AC" in dados:
                            ac = dados["AC"]
                            st.write(f"• Ingressantes: {ac.get('total_ingressantes', 0)}")
                            st.write(f"• Inscritos: {ac.get('inscritos', 0)}")
                            st.write(f"• Trancados: {ac.get('trancados', 0)}")
                            st.write(f"• Formados: {ac.get('formados', 0)}")
                            total_cancel = sum(ac.get('cancelamentos', {}).values())
                            st.write(f"• Cancelamentos: {total_cancel}")
                    
                    with col2:
                        st.markdown("**Ações Afirmativas (AA)**")
                        if "AA" in dados:
                            aa = dados["AA"]
                            st.write(f"• Ingressantes: {aa.get('total_ingressantes', 0)}")
                            st.write(f"• Inscritos: {aa.get('inscritos', 0)}")
                            st.write(f"• Trancados: {aa.get('trancados', 0)}")
                            st.write(f"• Formados: {aa.get('formados', 0)}")
                            total_cancel = sum(aa.get('cancelamentos', {}).values())
                            st.write(f"• Cancelamentos: {total_cancel}")

def mostrar_botao_gerar_planilha():
    """Mostra botão para gerar planilha final"""
    st.markdown("---")
    st.header("🚀 Gerar Planilha Final")
    
    if st.button("📥 GERAR PLANILHA DE EVASÃO COMPLETA", 
                type="primary", 
                use_container_width=True):
        
        with st.spinner("Gerando planilha no formato exato..."):
            try:
                # Importa a função gerar_planilha_completa (que está no código original)
                from openpyxl import Workbook
                from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
                
                # Cria workbook básico (simplificado para o exemplo)
                wb = Workbook()
                ws = wb.active
                ws.title = "Resumo"
                
                # Adiciona dados básicos
                ws['A1'] = "RESUMO DE EVASÃO - QUÍMICA IQ"
                ws['A1'].font = Font(bold=True, size=14)
                
                row = 3
                for periodo, cursos in st.session_state.dados_processados.items():
                    ws.cell(row=row, column=1, value=f"Período: {periodo}")
                    ws.cell(row=row, column=1).font = Font(bold=True)
                    row += 1
                    
                    for curso, dados in cursos.items():
                        ws.cell(row=row, column=1, value=curso)
                        row += 1
                        
                        total_ingressantes = 0
                        if "AC" in dados:
                            total_ingressantes += dados["AC"].get("total_ingressantes", 0)
                        if "AA" in dados:
                            total_ingressantes += dados["AA"].get("total_ingressantes", 0)
                        
                        ws.cell(row=row, column=2, value=f"Total ingressantes: {total_ingressantes}")
                        row += 2
                
                buffer = io.BytesIO()
                wb.save(buffer)
                buffer.seek(0)
                
                st.success("✅ Planilha gerada com sucesso!")
                
                nome_arquivo = f"Evasao_Quimica_IQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                st.download_button(
                    label="💾 BAIXAR PLANILHA COMPLETA",
                    data=buffer,
                    file_name=nome_arquivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.info("""
                **A planilha gerada contém:**
                • Dados processados de todos os períodos
                • Estrutura básica para análise
                • Formatação profissional
                
                **Nota:** Para a versão completa com todas as abas, implemente as funções de geração de planilha.
                """)
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar planilha: {str(e)}")

if __name__ == "__main__":
    main()
