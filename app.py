# app.py - ATUALIZADO COM ETAPA 2
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import json

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
if 'cursos_data' not in st.session_state:
    st.session_state.cursos_data = {}
if 'selected_cursos' not in st.session_state:
    st.session_state.selected_cursos = []
if 'periodos' not in st.session_state:
    st.session_state.periodos = []

# Funções para login (MANTIDAS DA ETAPA 1)
def extract_login_parameters(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    login_form = soup.find('form', {'id': 'kc-form-login'})
    
    if not login_form:
        return None
    
    action_url = login_form.get('action', '')
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
    try:
        login_page_url = "https://app.uff.br/graduacao/administracaoacademica"
        response = session.get(login_page_url, timeout=10)
        
        if response.status_code != 200:
            return False
        
        login_params = extract_login_parameters(response.text)
        
        if not login_params:
            return False
        
        form_data = {
            'username': username,
            'password': password,
            'rememberMe': 'on'
        }
        
        if login_params['hidden_fields']:
            form_data.update(login_params['hidden_fields'])
        
        login_action = login_params['action_url']
        
        if login_action.startswith('/'):
            from urllib.parse import urlparse
            parsed_base = urlparse(base_url)
            login_action = f"{parsed_base.scheme}://{parsed_base.netloc}{login_action}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
        
        if login_response.status_code == 200:
            if "administracaoacademica" in login_response.url:
                return True
            else:
                return False
        
        return False
        
    except requests.exceptions.RequestException:
        return False
    except Exception:
        return False

# NOVAS FUNÇÕES PARA ETAPA 2 - Análise da página principal
def extract_form_parameters(html_content):
    """Extrai parâmetros do formulário de listagem de alunos"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Encontrar o formulário principal
    form = soup.find('form', {'id': 'rel_filtros'})
    if not form:
        return None
    
    # Extrair token CSRF
    csrf_token = None
    csrf_input = soup.find('input', {'name': 'authenticity_token'})
    if csrf_input:
        csrf_token = csrf_input.get('value', '')
    
    # Extrair opções de localidade
    localidade_select = soup.find('select', {'id': 'idlocalidade'})
    localidades = []
    if localidade_select:
        for option in localidade_select.find_all('option'):
            if option.get('value'):
                localidades.append({
                    'value': option['value'],
                    'text': option.get_text(strip=True),
                    'selected': 'selected' in option.attrs
                })
    
    # Extrair opções de status do aluno
    status_select = soup.find('select', {'id': 'idstatusaluno'})
    status_options = []
    if status_select:
        for option in status_select.find_all('option'):
            if option.get('value'):
                status_options.append({
                    'value': option['value'],
                    'text': option.get_text(strip=True)
                })
    
    # Extrair opções de forma de ingresso
    forma_ingresso_select = soup.find('select', {'id': 'idformaingresso'})
    formas_ingresso = []
    if forma_ingresso_select:
        for option in forma_ingresso_select.find_all('option'):
            if option.get('value'):
                formas_ingresso.append({
                    'value': option['value'],
                    'text': option.get_text(strip=True),
                    'data_idingresso': option.get('data-idingresso', '')
                })
    
    # Extrair opções de período letivo (ingresso)
    periodo_select = soup.find('select', {'id': 'anosem_ingresso'})
    periodos = []
    if periodo_select:
        for option in periodo_select.find_all('option'):
            if option.get('value'):
                periodos.append({
                    'value': option['value'],
                    'text': option.get_text(strip=True)
                })
    
    return {
        'csrf_token': csrf_token,
        'localidades': localidades,
        'status_options': status_options,
        'formas_ingresso': formas_ingresso,
        'periodos': periodos,
        'action': form.get('action', '')
    }

def get_cursos_disponiveis(session, localidade_id):
    """Obtém cursos disponíveis para uma localidade específica"""
    try:
        # URL para obter cursos (baseado na análise do JavaScript da página)
        cursos_url = f"https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos/cursos?localidade={localidade_id}"
        
        response = session.get(cursos_url, timeout=10)
        if response.status_code == 200:
            # A resposta pode ser JSON ou HTML
            try:
                cursos_data = response.json()
                return cursos_data
            except:
                # Tentar parsear como HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                cursos = []
                options = soup.find_all('option')
                for option in options:
                    if option.get('value'):
                        cursos.append({
                            'value': option['value'],
                            'text': option.get_text(strip=True)
                        })
                return cursos
    except:
        pass
    return []

def logout():
    """Limpa a sessão e faz logout"""
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.session = requests.Session()
    st.session_state.cursos_data = {}
    st.session_state.selected_cursos = []
    st.session_state.periodos = []
    st.rerun()

# ETAPA 2 - Interface de seleção de período
def etapa_selecao_periodo():
    """Interface para seleção de período e cursos"""
    
    st.markdown("## 📅 Etapa 2 - Seleção de Período e Cursos")
    
    # Carregar dados da página
    if not st.session_state.cursos_data:
        with st.spinner("Carregando dados do sistema..."):
            try:
                response = st.session_state.session.get(
                    "https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos",
                    timeout=10
                )
                
                if response.status_code == 200:
                    form_params = extract_form_parameters(response.text)
                    if form_params:
                        st.session_state.cursos_data = form_params
                        st.success("Dados carregados com sucesso!")
                    else:
                        st.error("Não foi possível carregar os dados do formulário")
                else:
                    st.error(f"Erro ao acessar página: {response.status_code}")
                    
            except Exception as e:
                st.error(f"Erro: {str(e)}")
    
    if not st.session_state.cursos_data:
        st.warning("Não foi possível carregar os dados. Tente fazer login novamente.")
        return False
    
    # Criar interface de seleção
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Parâmetros da Consulta")
        
        # Localidade
        localidades = st.session_state.cursos_data.get('localidades', [])
        localidade_options = {loc['text']: loc['value'] for loc in localidades}
        localidade_selecionada = st.selectbox(
            "Localidade",
            options=list(localidade_options.keys()),
            index=list(localidade_options.values()).index('1') if '1' in localidade_options.values() else 0
        )
        
        # Forma de Ingresso
        formas_ingresso = st.session_state.cursos_data.get('formas_ingresso', [])
        # Filtrar apenas SISU (baseado nos parâmetros fornecidos)
        formas_sisu = [f for f in formas_ingresso if 'SISU' in f['text']]
        forma_options = {f['text']: f['value'] for f in formas_sisu}
        
        if forma_options:
            forma_ingresso = st.selectbox(
                "Forma de Ingresso",
                options=list(forma_options.keys())
            )
        else:
            forma_ingresso = None
            st.warning("Formas de ingresso SISU não encontradas")
    
    with col2:
        st.subheader("🎯 Seleção de Períodos")
        
        # Período Inicial
        periodos = st.session_state.cursos_data.get('periodos', [])
        # Ordenar períodos (mais recente primeiro)
        periodos_ordenados = sorted(periodos, 
                                  key=lambda x: x['value'], 
                                  reverse=True)
        
        periodo_inicial_options = [p['text'] for p in periodos_ordenados]
        periodo_inicial = st.selectbox(
            "Período Inicial",
            options=periodo_inicial_options,
            help="Selecione o período letivo inicial para análise"
        )
        
        # Período Final
        # Encontrar índice do período inicial
        periodo_inicial_idx = periodo_inicial_options.index(periodo_inicial)
        # Mostrar apenas períodos iguais ou anteriores ao inicial
        periodo_final_options = periodo_inicial_options[periodo_inicial_idx:]
        
        if len(periodo_final_options) > 1:
            periodo_final = st.selectbox(
                "Período Final",
                options=periodo_final_options,
                index=0,
                help="Selecione o período letivo final para análise"
            )
        else:
            periodo_final = periodo_inicial
            st.info("Apenas um período disponível para análise")
    
    # Validações
    if periodo_inicial and periodo_final:
        # Extrair ano e semestre para validação
        def parse_periodo(periodo_str):
            match = re.search(r'(\d{4})\s*/\s*(\d+)', periodo_str)
            if match:
                return int(match.group(1)), int(match.group(2).replace('º', '').replace('°', ''))
            return None, None
        
        ano_inicial, sem_inicial = parse_periodo(periodo_inicial)
        ano_final, sem_final = parse_periodo(periodo_final)
        
        if ano_inicial and ano_final:
            # Validar se período final não é anterior ao inicial
            if (ano_final < ano_inicial) or (ano_final == ano_inicial and sem_final < sem_inicial):
                st.error("❌ Período final não pode ser anterior ao período inicial")
                return False
            
            st.success(f"✅ Período selecionado: {periodo_inicial} a {periodo_final}")
    
    # Seleção de Cursos
    st.markdown("---")
    st.subheader("📚 Cursos para Análise")
    
    cursos_disponiveis = [
        {
            'nome': 'Química (Licenciatura)',
            'codigo': '12700',
            'desdobramento': 'Química (Licenciatura) (12700)'
        },
        {
            'nome': 'Química (Bacharelado)',
            'codigo': '312700', 
            'desdobramento': 'Química (Bacharelado) (312700)'
        },
        {
            'nome': 'Química Industrial',
            'codigo': '12709',
            'desdobramento': 'Química Industrial (12709)'
        }
    ]
    
    # Seleção múltipla de cursos
    cursos_selecionados = st.multiselect(
        "Selecione os cursos para análise:",
        options=[curso['nome'] for curso in cursos_disponiveis],
        default=[curso['nome'] for curso in cursos_disponiveis],
        help="Selecione os 3 cursos de Química para análise de evasão"
    )
    
    if cursos_selecionados:
        st.session_state.selected_cursos = [
            curso for curso in cursos_disponiveis 
            if curso['nome'] in cursos_selecionados
        ]
        
        # Mostrar resumo
        with st.expander("📋 Resumo da Seleção", expanded=True):
            st.markdown("**Configuração definida:**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Localidade", localidade_selecionada)
            with col2:
                st.metric("Forma de Ingresso", forma_ingresso if forma_ingresso else "SISU")
            with col3:
                st.metric("Período", f"{periodo_inicial} a {periodo_final}")
            
            st.markdown("**Cursos selecionados:**")
            for curso in st.session_state.selected_cursos:
                st.markdown(f"- {curso['nome']} ({curso['codigo']})")
    
    # Botão para confirmar seleção
    if st.button("✅ Confirmar Seleção e Prosseguir", type="primary"):
        if not st.session_state.selected_cursos:
            st.error("Selecione pelo menos um curso para análise")
            return False
        
        # Armazenar período selecionado
        st.session_state.periodos = {
            'inicial': periodo_inicial,
            'final': periodo_final,
            'localidade': localidade_selecionada,
            'forma_ingresso': forma_ingresso
        }
        
        st.success("🎉 Seleção confirmada! Pronto para a próxima etapa.")
        time.sleep(1)
        st.rerun()
    
    return True

# Interface principal
def main():
    st.title("🎓 Sistema de Análise de Evasão - UFF")
    
    if not st.session_state.authenticated:
        # Página de login (MANTIDA DA ETAPA 1)
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
    
    else:
        # Menu principal após login
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ Logado como: {st.session_state.username}")
        
        with col2:
            if st.button("🚪 Sair", type="secondary"):
                logout()
        
        st.markdown("---")
        
        # Progresso das etapas
        st.markdown("### 📋 Progresso do Processo")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown("**1. Login**")
            st.success("✅ Concluído")
        with col2:
            st.markdown("**2. Período**")
            if st.session_state.periodos:
                st.success("✅ Concluído")
            else:
                st.info("🔄 Em andamento")
        with col3:
            st.markdown("**3. Consulta**")
            st.info("⏳ Aguardando")
        with col4:
            st.markdown("**4. Processamento**")
            st.info("⏳ Aguardando")
        with col5:
            st.markdown("**5. Planilha**")
            st.info("⏳ Aguardando")
        
        st.markdown("---")
        
        # Conteúdo principal baseado no estado
        if not st.session_state.periodos:
            # Mostrar etapa 2 - seleção de período
            etapa_selecao_periodo()
        else:
            # Mostrar resumo e preparar para próxima etapa
            st.markdown("## 🎯 Seleção Confirmada")
            
            with st.expander("📊 Resumo da Configuração", expanded=True):
                periodos = st.session_state.periodos
                cursos = st.session_state.selected_cursos
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Período Analisado:**")
                    st.info(f"**De:** {periodos['inicial']}")
                    st.info(f"**Até:** {periodos['final']}")
                    st.markdown(f"**Localidade:** {periodos['localidade']}")
                    st.markdown(f"**Forma de Ingresso:** {periodos['forma_ingresso']}")
                
                with col2:
                    st.markdown("**Cursos Selecionados:**")
                    for i, curso in enumerate(cursos, 1):
                        st.markdown(f"{i}. **{curso['nome']}**")
                        st.markdown(f"   Código: `{curso['codigo']}`")
                        st.markdown(f"   Desdobramento: {curso['desdobramento']}")
            
            st.markdown("---")
            st.markdown("### 🚀 Próxima Etapa: Consulta de Relatórios")
            
            st.info("""
            **Próximos passos:**
            1. O sistema irá acessar automaticamente os relatórios do sistema acadêmico
            2. Coletar dados para cada curso selecionado
            3. Processar informações de matrículas, cancelamentos e evasão
            4. Gerar planilha final com análise completa
            """)
            
            # Botão para iniciar a próxima etapa
            if st.button("🔍 Iniciar Consulta de Relatórios", type="primary"):
                st.session_state.etapa_atual = 3
                st.info("Iniciando consulta... (Etapa 3 em desenvolvimento)")
                # Aqui será implementada a Etapa 3
        
        # Informações técnicas
        with st.expander("🔧 Informações Técnicas"):
            st.code(f"""
            Status: {'Autenticado' if st.session_state.authenticated else 'Não autenticado'}
            Usuário: {st.session_state.username}
            Cookies ativos: {len(st.session_state.session.cookies)}
            Período configurado: {st.session_state.periodos.get('inicial', 'Não definido')} a {st.session_state.periodos.get('final', 'Não definido')}
            Cursos selecionados: {len(st.session_state.selected_cursos)}
            """)

if __name__ == "__main__":
    main()
