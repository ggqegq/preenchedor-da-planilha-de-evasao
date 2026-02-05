# app.py - VERSÃO CORRIGIDA PARA PERÍODOS
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
if 'form_params' not in st.session_state:
    st.session_state.form_params = None
if 'selected_cursos' not in st.session_state:
    st.session_state.selected_cursos = []
if 'selected_periodos' not in st.session_state:
    st.session_state.selected_periodos = {}
if 'formas_ingresso_selecionadas' not in st.session_state:
    st.session_state.formas_ingresso_selecionadas = []

# Funções para login (mantidas)
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

# Função para extrair parâmetros do formulário
def extract_form_parameters(session):
    """Extrai parâmetros do formulário de listagem de alunos"""
    try:
        response = session.get(
            "https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos",
            timeout=10
        )
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
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
                        'text': option.get_text(strip=True),
                        'selected': 'selected' in option.attrs
                    })
        
        return {
            'csrf_token': csrf_token,
            'localidades': localidades,
            'formas_ingresso': formas_ingresso,
            'periodos': periodos,
            'action': form.get('action', '')
        }
        
    except Exception:
        return None

# Funções auxiliares para processamento de períodos
def parse_periodo_texto(periodo_texto):
    """Extrai ano e semestre de um texto de período"""
    if not periodo_texto:
        return None, None
    
    match = re.search(r'(\d{4})\s*/\s*(\d+)', periodo_texto)
    if match:
        try:
            ano = int(match.group(1))
            semestre = int(match.group(2).replace('º', '').replace('°', ''))
            return ano, semestre
        except:
            return None, None
    
    return None, None

def comparar_periodos(periodo1, periodo2):
    """Compara dois períodos, retorna -1 se periodo1 < periodo2, 0 se iguais, 1 se periodo1 > periodo2"""
    ano1, sem1 = parse_periodo_texto(periodo1)
    ano2, sem2 = parse_periodo_texto(periodo2)
    
    if ano1 is None or ano2 is None:
        return 0
    
    if ano1 < ano2:
        return -1
    elif ano1 > ano2:
        return 1
    else:
        # Anos iguais, comparar semestres
        if sem1 < sem2:
            return -1
        elif sem1 > sem2:
            return 1
        else:
            return 0

def get_indice_periodo(periodo_texto, periodos_lista):
    """Obtém índice de um período na lista de períodos"""
    for i, periodo in enumerate(periodos_lista):
        if periodo == periodo_texto:
            return i
    return 0

# Interface de seleção de período - CORRIGIDA
def etapa_selecao_periodo():
    """Interface para seleção de período e cursos"""
    
    st.markdown("## 📅 Etapa 2 - Seleção de Período e Cursos")
    
    # Carregar dados do formulário se necessário
    if st.session_state.form_params is None:
        with st.spinner("Carregando dados do sistema..."):
            st.session_state.form_params = extract_form_parameters(st.session_state.session)
    
    if st.session_state.form_params is None:
        st.error("Não foi possível carregar os dados do sistema.")
        return False
    
    form_params = st.session_state.form_params
    
    # Criar interface de seleção
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Parâmetros da Consulta")
        
        # Localidade (fixa como Niterói)
        localidades = form_params.get('localidades', [])
        localidade_niteroi = next((loc for loc in localidades if loc['value'] == '1'), None)
        
        if localidade_niteroi:
            st.info(f"**Localidade:** {localidade_niteroi['text']}")
            localidade_value = '1'
        else:
            st.error("Localidade Niterói não encontrada")
            return False
        
        # Forma de Ingresso - AMBOS SISUS PRÉ-SELECIONADOS
        formas_ingresso = form_params.get('formas_ingresso', [])
        formas_sisu = [f for f in formas_ingresso if 'SISU' in f['text']]
        
        if len(formas_sisu) >= 2:
            # Separar SISU 1ª e 2ª Edição
            sisu_1 = next((f for f in formas_sisu if '1ª' in f['text'] or '1º' in f['text']), None)
            sisu_2 = next((f for f in formas_sisu if '2ª' in f['text'] or '2º' in f['text']), None)
            
            formas_selecionadas = []
            formas_valores = []
            
            if sisu_1:
                formas_selecionadas.append(sisu_1['text'])
                formas_valores.append(sisu_1['value'])
                st.success(f"✅ {sisu_1['text']}")
            
            if sisu_2:
                formas_selecionadas.append(sisu_2['text'])
                formas_valores.append(sisu_2['value'])
                st.success(f"✅ {sisu_2['text']}")
            
            if len(formas_selecionadas) == 2:
                st.success("✅ Ambos SISU 1ª e 2ª Edição selecionados")
            else:
                st.warning("⚠️ Nem todas as formas SISU foram encontradas")
        else:
            st.error("Formas de ingresso SISU não encontradas")
            return False
    
    with col2:
        st.subheader("🎯 Seleção de Períodos")
        
        # Períodos disponíveis
        periodos = form_params.get('periodos', [])
        
        if not periodos:
            st.error("Nenhum período disponível")
            return False
        
        # Converter para lista de textos
        periodo_textos = [p['text'] for p in periodos if p['text'] != '--- Todos ---']
        periodo_valores = {p['text']: p['value'] for p in periodos if p['text'] != '--- Todos ---'}
        
        if not periodo_textos:
            st.error("Períodos não disponíveis")
            return False
        
        # Ordenar períodos do mais antigo para o mais recente
        # Primeiro extrair ano e semestre para ordenação
        periodos_com_info = []
        for texto in periodo_textos:
            ano, semestre = parse_periodo_texto(texto)
            if ano and semestre:
                periodos_com_info.append({
                    'texto': texto,
                    'ano': ano,
                    'semestre': semestre,
                    'valor_ordenacao': ano * 10 + semestre
                })
        
        # Ordenar do mais antigo (menor valor) para mais recente (maior valor)
        periodos_com_info.sort(key=lambda x: x['valor_ordenacao'])
        periodo_textos_ordenados = [p['texto'] for p in periodos_com_info]
        
        # Encontrar índices para período inicial (mais antigo) e final (mais recente)
        idx_inicial = 0  # Mais antigo
        idx_final = len(periodo_textos_ordenados) - 1  # Mais recente
        
        # Período Inicial (MAIS ANTIGO - início do intervalo)
        periodo_inicial_texto = st.selectbox(
            "Período Inicial (início do intervalo)",
            options=periodo_textos_ordenados,
            index=idx_inicial,
            help="Selecione o período mais ANTIGO do intervalo de análise"
        )
        
        # Período Final (MAIS RECENTE - fim do intervalo)
        # Encontrar índice do período inicial selecionado
        periodo_inicial_idx = periodo_textos_ordenados.index(periodo_inicial_texto)
        
        # Filtrar períodos que são IGUAIS OU POSTERIORES ao inicial
        periodos_finais_disponiveis = periodo_textos_ordenados[periodo_inicial_idx:]
        
        # Índice padrão para período final (o mais recente disponível)
        idx_final_disponivel = len(periodos_finais_disponiveis) - 1
        
        periodo_final_texto = st.selectbox(
            "Período Final (fim do intervalo)",
            options=periodos_finais_disponiveis,
            index=idx_final_disponivel,
            help="Selecione o período mais RECENTE do intervalo de análise"
        )
        
        # Validação CORRIGIDA - permitir período inicial ANTERIOR ao final
        if periodo_inicial_texto and periodo_final_texto:
            resultado_comparacao = comparar_periodos(periodo_inicial_texto, periodo_final_texto)
            
            if resultado_comparacao == 0:
                st.info("⚠️ Período inicial e final são iguais")
            elif resultado_comparacao == -1:
                st.success(f"✅ Intervalo válido: {periodo_inicial_texto} a {periodo_final_texto}")
            else:
                st.error("❌ Período inicial deve ser ANTERIOR ou IGUAL ao período final")
                return False
    
    # Seleção de Cursos
    st.markdown("---")
    st.subheader("📚 Cursos para Análise")
    
    cursos_disponiveis = [
        {
            'nome': 'Química (Licenciatura)',
            'codigo': '12700',
            'desdobramento': 'Química (Licenciatura) (12700)',
            'tipo': 'Licenciatura'
        },
        {
            'nome': 'Química (Bacharelado)',
            'codigo': '312700', 
            'desdobramento': 'Química (Bacharelado) (312700)',
            'tipo': 'Bacharelado'
        },
        {
            'nome': 'Química Industrial',
            'codigo': '12709',
            'desdobramento': 'Química Industrial (12709)',
            'tipo': 'Bacharelado'
        }
    ]
    
    # Seleção múltipla com todos pré-selecionados
    cursos_selecionados_nomes = st.multiselect(
        "Selecione os cursos para análise:",
        options=[curso['nome'] for curso in cursos_disponiveis],
        default=[curso['nome'] for curso in cursos_disponiveis],
        help="Os 3 cursos de Química estão pré-selecionados"
    )
    
    # Mapear para objetos
    cursos_selecionados_objetos = []
    for curso_nome in cursos_selecionados_nomes:
        curso_obj = next((c for c in cursos_disponiveis if c['nome'] == curso_nome), None)
        if curso_obj:
            cursos_selecionados_objetos.append(curso_obj)
    
    # Botão para confirmar
    st.markdown("---")
    
    if st.button("✅ Confirmar Seleção e Prosseguir", type="primary", use_container_width=True):
        # Validações
        if not formas_valores or len(formas_valores) != 2:
            st.error("As duas formas de ingresso SISU devem estar selecionadas")
            return False
        
        if not cursos_selecionados_objetos:
            st.error("Selecione pelo menos um curso")
            return False
        
        if not periodo_inicial_texto or not periodo_final_texto:
            st.error("Selecione os períodos")
            return False
        
        # Validar novamente o intervalo
        resultado = comparar_periodos(periodo_inicial_texto, periodo_final_texto)
        if resultado == 1:  # Inicial > Final (inválido)
            st.error("Período inicial não pode ser posterior ao final")
            return False
        
        # Armazenar seleções
        st.session_state.selected_cursos = cursos_selecionados_objetos
        st.session_state.selected_periodos = {
            'inicial': periodo_inicial_texto,
            'final': periodo_final_texto,
            'valor_inicial': periodo_valores.get(periodo_inicial_texto, ''),
            'valor_final': periodo_valores.get(periodo_final_texto, '')
        }
        st.session_state.formas_ingresso_selecionadas = formas_valores
        st.session_state.localidade_selecionada = {
            'text': localidade_niteroi['text'],
            'value': localidade_value
        }
        
        st.success("🎉 Configuração salva com sucesso!")
        time.sleep(1)
        st.rerun()
    
    # Mostrar pré-visualização
    if cursos_selecionados_objetos:
        with st.expander("📋 Pré-visualização da Configuração", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Localidade:** Niterói")
                st.markdown(f"**Formas de Ingresso:** {' e '.join(formas_selecionadas)}")
            with col_b:
                st.markdown(f"**Período Inicial:** {periodo_inicial_texto}")
                st.markdown(f"**Período Final:** {periodo_final_texto}")
            
            st.markdown("**Cursos:**")
            for curso in cursos_selecionados_objetos:
                st.markdown(f"- {curso['nome']}")
    
    return True

# Interface principal
def main():
    st.title("🎓 Sistema de Análise de Evasão - UFF")
    
    if not st.session_state.authenticated:
        # Página de login
        st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
        
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
        # Menu principal
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ Logado como: {st.session_state.username}")
        
        with col2:
            if st.button("🚪 Sair", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        st.markdown("---")
        
        # Progresso
        st.markdown("### 📋 Progresso do Processo")
        
        cols = st.columns(5)
        etapas = [
            ("1. Login", "✅" if st.session_state.authenticated else "⏳"),
            ("2. Período", "✅" if st.session_state.selected_periodos else "🔄"),
            ("3. Consulta", "⏳"),
            ("4. Processamento", "⏳"),
            ("5. Planilha", "⏳")
        ]
        
        for col, (etapa, status) in zip(cols, etapas):
            with col:
                st.markdown(f"**{etapa}**")
                st.markdown(status)
        
        st.markdown("---")
        
        # Conteúdo principal
        if not st.session_state.selected_periodos:
            etapa_selecao_periodo()
        else:
            # Mostrar resumo
            st.markdown("## 🎯 Configuração Confirmada")
            
            with st.expander("📊 Resumo da Configuração", expanded=True):
                periodos = st.session_state.selected_periodos
                cursos = st.session_state.selected_cursos
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**📅 Período Analisado**")
                    st.info(f"**Início:** {periodos['inicial']}")
                    st.info(f"**Término:** {periodos['final']}")
                    st.markdown(f"**📍 Localidade:** Niterói")
                    
                    # Recuperar nomes SISU
                    formas_nomes = []
                    if st.session_state.form_params:
                        for forma in st.session_state.form_params.get('formas_ingresso', []):
                            if forma['value'] in st.session_state.formas_ingresso_selecionadas:
                                formas_nomes.append(forma['text'])
                    
                    st.markdown(f"**🎯 Formas de Ingresso:**")
                    for nome in formas_nomes:
                        st.markdown(f"- {nome}")
                
                with col_b:
                    st.markdown("**📚 Cursos Selecionados**")
                    for i, curso in enumerate(cursos, 1):
                        st.markdown(f"{i}. **{curso['nome']}**")
                        st.markdown(f"   Tipo: {curso['tipo']}")
                        st.markdown(f"   Código: `{curso['codigo']}`")
            
            st.markdown("---")
            st.markdown("### 🚀 Próxima Etapa: Consulta de Relatórios")
            
            st.info("""
            **A Etapa 3 irá:**
            1. Acessar o sistema acadêmico
            2. Consultar relatórios para cada curso
            3. Coletar dados de matrículas
            4. Preparar para processamento
            """)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔍 Iniciar Consulta", type="primary", use_container_width=True):
                    st.session_state.etapa_atual = 3
                    st.info("Iniciando consulta...")
            
            with col_btn2:
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.selected_periodos = {}
                    st.session_state.selected_cursos = []
                    st.session_state.formas_ingresso_selecionadas = []
                    st.rerun()

if __name__ == "__main__":
    main()
