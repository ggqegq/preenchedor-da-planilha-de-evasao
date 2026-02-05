# app.py - VERSÃO CORRIGIDA
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

# Funções para login
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
                # Verificar se há mensagem de erro
                soup = BeautifulSoup(login_response.text, 'html.parser')
                error_div = soup.find('div', {'class': 'alert-error'})
                if error_div:
                    st.error(f"Erro: {error_div.get_text(strip=True)}")
                return False
        
        return False
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Erro inesperado: {str(e)}")
        return False

# Funções para extrair dados do formulário
def extract_form_parameters(session):
    """Extrai parâmetros do formulário de listagem de alunos"""
    try:
        response = session.get(
            "https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos",
            timeout=10
        )
        
        if response.status_code != 200:
            st.error(f"Erro ao acessar página: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar o formulário principal
        form = soup.find('form', {'id': 'rel_filtros'})
        if not form:
            st.error("Formulário não encontrado")
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
        
    except Exception as e:
        st.error(f"Erro ao extrair parâmetros: {str(e)}")
        return None

# Interface de seleção de período
def etapa_selecao_periodo():
    """Interface para seleção de período e cursos"""
    
    st.markdown("## 📅 Etapa 2 - Seleção de Período e Cursos")
    
    # Carregar dados do formulário se necessário
    if st.session_state.form_params is None:
        with st.spinner("Carregando dados do sistema..."):
            st.session_state.form_params = extract_form_parameters(st.session_state.session)
    
    if st.session_state.form_params is None:
        st.error("Não foi possível carregar os dados do sistema. Verifique sua conexão.")
        return False
    
    # Dados disponíveis
    form_params = st.session_state.form_params
    
    # Criar interface de seleção
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Parâmetros da Consulta")
        
        # Localidade (fixa como Niterói conforme especificado)
        localidades = form_params.get('localidades', [])
        localidade_niteroi = next((loc for loc in localidades if loc['value'] == '1'), None)
        
        if localidade_niteroi:
            st.info(f"**Localidade:** {localidade_niteroi['text']}")
            localidade_value = '1'
        else:
            st.error("Localidade Niterói não encontrada")
            return False
        
        # Forma de Ingresso - SELECIONAR AMBOS OS SISUS
        formas_ingresso = form_params.get('formas_ingresso', [])
        
        # Filtrar apenas SISU
        formas_sisu = [f for f in formas_ingresso if 'SISU' in f['text']]
        
        if len(formas_sisu) >= 2:
            # Seleção múltipla para SISU 1ª e 2ª Edição
            sisu_options = [f['text'] for f in formas_sisu]
            formas_selecionadas = st.multiselect(
                "Formas de Ingresso (SISU):",
                options=sisu_options,
                default=sisu_options[:2],  # Pré-selecionar os dois primeiros SISU
                help="Selecione SISU 1ª Edição para 1º semestre e SISU 2ª Edição para 2º semestre"
            )
            
            if len(formas_selecionadas) != 2:
                st.warning("⚠️ É necessário selecionar AMBOS: SISU 1ª Edição e SISU 2ª Edição")
                formas_ingresso_valores = []
            else:
                # Mapear textos selecionados para valores
                formas_ingresso_valores = []
                for forma in formas_sisu:
                    if forma['text'] in formas_selecionadas:
                        formas_ingresso_valores.append(forma['value'])
                
                st.success(f"✅ Formas de ingresso selecionadas: {', '.join(formas_selecionadas)}")
        else:
            st.error("Formas de ingresso SISU não encontradas no sistema")
            return False
    
    with col2:
        st.subheader("🎯 Seleção de Períodos")
        
        # Períodos disponíveis
        periodos = form_params.get('periodos', [])
        
        if not periodos:
            st.error("Nenhum período disponível")
            return False
        
        # Converter para lista de textos e valores
        periodo_textos = [p['text'] for p in periodos]
        periodo_valores = {p['text']: p['value'] for p in periodos}
        
        # Encontrar índices para 2025.1 e 2025.2 (ou os mais recentes)
        def encontrar_indice_periodo(texto_busca):
            for i, texto in enumerate(periodo_textos):
                if texto_busca in texto:
                    return i
            return 0
        
        # Tentar encontrar 2025
        idx_2025_1 = encontrar_indice_periodo("2025 / 1")
        idx_2025_2 = encontrar_indice_periodo("2025 / 2")
        
        # Se não encontrar 2025, usar os mais recentes
        if idx_2025_1 == 0 and idx_2025_2 == 0:
            idx_2025_1 = 1  # Segundo mais recente (o primeiro é "--- Todos ---")
            idx_2025_2 = 2  # Terceiro mais recente
        
        # Período Inicial
        periodo_inicial_texto = st.selectbox(
            "Período Inicial",
            options=periodo_textos,
            index=idx_2025_1,
            help="Selecione o período letivo inicial para análise"
        )
        
        # Período Final
        # Encontrar índice do período inicial
        periodo_inicial_idx = periodo_textos.index(periodo_inicial_texto)
        
        # Filtrar períodos que são iguais ou posteriores ao inicial
        periodos_finais_disponiveis = periodo_textos[periodo_inicial_idx:]
        
        # Encontrar índice do período final (padrão: um período após o inicial)
        idx_final = 0
        if len(periodos_finais_disponiveis) > 1:
            # Tentar encontrar 2025.2 se disponível
            for i, periodo in enumerate(periodos_finais_disponiveis):
                if "2025 / 2" in periodo:
                    idx_final = i
                    break
            if idx_final == 0 and len(periodos_finais_disponiveis) > 1:
                idx_final = 1  # Próximo período
        
        periodo_final_texto = st.selectbox(
            "Período Final",
            options=periodos_finais_disponiveis,
            index=idx_final,
            help="Selecione o período letivo final para análise"
        )
        
        # Validar seleção
        if periodo_inicial_texto and periodo_final_texto:
            # Extrair ano e semestre para validação
            def parse_periodo_texto(texto):
                match = re.search(r'(\d{4})\s*/\s*(\d+)', texto)
                if match:
                    ano = int(match.group(1))
                    semestre = int(match.group(2).replace('º', '').replace('°', ''))
                    return ano, semestre
                return None, None
            
            ano_inicial, sem_inicial = parse_periodo_texto(periodo_inicial_texto)
            ano_final, sem_final = parse_periodo_texto(periodo_final_texto)
            
            if ano_inicial and ano_final:
                # Calcular valor numérico para comparação
                valor_inicial = ano_inicial * 10 + sem_inicial
                valor_final = ano_final * 10 + sem_final
                
                if valor_final < valor_inicial:
                    st.error("❌ Período final não pode ser anterior ao período inicial")
                    return False
                elif valor_final == valor_inicial:
                    st.warning("⚠️ Período inicial e final são iguais")
                else:
                    st.success(f"✅ Período selecionado: {periodo_inicial_texto} a {periodo_final_texto}")
    
    # Seleção de Cursos
    st.markdown("---")
    st.subheader("📚 Cursos para Análise")
    
    # Cursos pré-definidos conforme especificação
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
    
    # Seleção múltipla de cursos
    cursos_selecionados_nomes = st.multiselect(
        "Selecione os cursos para análise:",
        options=[curso['nome'] for curso in cursos_disponiveis],
        default=[curso['nome'] for curso in cursos_disponiveis],  # Todos pré-selecionados
        help="Selecione os 3 cursos de Química para análise de evasão"
    )
    
    # Mapear nomes selecionados para objetos de curso
    cursos_selecionados_objetos = []
    for curso_nome in cursos_selecionados_nomes:
        curso_obj = next((c for c in cursos_disponiveis if c['nome'] == curso_nome), None)
        if curso_obj:
            cursos_selecionados_objetos.append(curso_obj)
    
    # Botão para confirmar seleção
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("✅ Confirmar Seleção e Prosseguir", type="primary", use_container_width=True):
            # Validações finais
            if not formas_ingresso_valores or len(formas_ingresso_valores) != 2:
                st.error("Selecione ambas as formas de ingresso SISU")
                return False
            
            if not cursos_selecionados_objetos:
                st.error("Selecione pelo menos um curso")
                return False
            
            if not periodo_inicial_texto or not periodo_final_texto:
                st.error("Selecione os períodos")
                return False
            
            # Armazenar seleções
            st.session_state.selected_cursos = cursos_selecionados_objetos
            st.session_state.selected_periodos = {
                'inicial': periodo_inicial_texto,
                'final': periodo_final_texto,
                'valor_inicial': periodo_valores.get(periodo_inicial_texto, ''),
                'valor_final': periodo_valores.get(periodo_final_texto, '')
            }
            st.session_state.formas_ingresso_selecionadas = formas_ingresso_valores
            st.session_state.localidade_selecionada = {
                'text': localidade_niteroi['text'],
                'value': localidade_value
            }
            
            st.success("🎉 Seleção confirmada com sucesso!")
            time.sleep(2)
            st.rerun()
    
    # Mostrar resumo da seleção atual
    if cursos_selecionados_objetos:
        with st.expander("📋 Pré-visualização da Configuração", expanded=True):
            st.markdown("**Configuração atual:**")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.markdown(f"**Localidade:** {localidade_niteroi['text']}")
                st.markdown(f"**Formas de Ingresso:** {', '.join(formas_selecionadas) if 'formas_selecionadas' in locals() else 'Não selecionadas'}")
            
            with col_res2:
                st.markdown(f"**Período Inicial:** {periodo_inicial_texto}")
                st.markdown(f"**Período Final:** {periodo_final_texto}")
            
            st.markdown("**Cursos selecionados:**")
            for curso in cursos_selecionados_objetos:
                st.markdown(f"- **{curso['nome']}** ({curso['tipo']})")
                st.markdown(f"  Código: `{curso['codigo']}`")
    
    return True

# Interface principal
def main():
    st.title("🎓 Sistema de Análise de Evasão - UFF")
    
    # Estado de autenticação
    if not st.session_state.authenticated:
        # Página de login
        st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form("login_form", clear_on_submit=False):
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
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Falha no login. Verifique suas credenciais.")
            
            st.markdown("---")
            st.markdown("""
            **Ajuda:**
            - Utilize sua identificação UFF (CPF, email ou passaporte)
            - Em caso de problemas, entre em contato com a central de atendimento
            """)
    
    else:
        # Menu principal após login
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.success(f"✅ Logado como: {st.session_state.username}")
        
        with col2:
            if st.button("🚪 Sair", type="secondary", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.username = ""
                st.session_state.session = requests.Session()
                st.session_state.form_params = None
                st.session_state.selected_cursos = []
                st.session_state.selected_periodos = {}
                st.session_state.formas_ingresso_selecionadas = []
                st.rerun()
        
        st.markdown("---")
        
        # Barra de progresso
        st.markdown("### 📋 Progresso do Processo")
        
        col_prog1, col_prog2, col_prog3, col_prog4, col_prog5 = st.columns(5)
        
        with col_prog1:
            st.markdown("**1. Login**")
            st.success("✅")
        
        with col_prog2:
            st.markdown("**2. Período**")
            if st.session_state.selected_periodos:
                st.success("✅")
            else:
                st.info("🔄")
        
        with col_prog3:
            st.markdown("**3. Consulta**")
            st.info("⏳")
        
        with col_prog4:
            st.markdown("**4. Processamento**")
            st.info("⏳")
        
        with col_prog5:
            st.markdown("**5. Planilha**")
            st.info("⏳")
        
        st.markdown("---")
        
        # Conteúdo principal
        if not st.session_state.selected_periodos:
            # Etapa 2 - Seleção de período
            etapa_selecao_periodo()
        else:
            # Mostrar resumo e preparar para próxima etapa
            st.markdown("## 🎯 Configuração Confirmada")
            
            with st.expander("📊 Resumo da Configuração", expanded=True):
                periodos = st.session_state.selected_periodos
                cursos = st.session_state.selected_cursos
                formas_ingresso = st.session_state.formas_ingresso_selecionadas
                
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    st.markdown("**Período Analisado:**")
                    st.info(f"**Início:** {periodos['inicial']}")
                    st.info(f"**Término:** {periodos['final']}")
                    st.markdown(f"**Localidade:** Niterói")
                    
                    # Recuperar nomes das formas de ingresso
                    formas_nomes = []
                    if st.session_state.form_params and 'formas_ingresso' in st.session_state.form_params:
                        for forma in st.session_state.form_params['formas_ingresso']:
                            if forma['value'] in formas_ingresso:
                                formas_nomes.append(forma['text'])
                    
                    st.markdown(f"**Formas de Ingresso:** {', '.join(formas_nomes) if formas_nomes else 'SISU 1ª e 2ª Edição'}")
                
                with col_res2:
                    st.markdown("**Cursos Selecionados:**")
                    for i, curso in enumerate(cursos, 1):
                        st.markdown(f"{i}. **{curso['nome']}**")
                        st.markdown(f"   Tipo: {curso['tipo']}")
                        st.markdown(f"   Código: `{curso['codigo']}`")
            
            st.markdown("---")
            st.markdown("### 🚀 Próxima Etapa: Consulta de Relatórios")
            
            st.info("""
            **A Etapa 3 irá:**
            1. Acessar automaticamente o sistema acadêmico
            2. Consultar relatórios para cada curso selecionado
            3. Coletar dados de matrículas e cancelamentos
            4. Preparar dados para processamento
            """)
            
            # Botões de controle
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            
            with col_btn2:
                if st.button("🔍 Iniciar Consulta de Relatórios", type="primary", use_container_width=True):
                    st.session_state.etapa_atual = 3
                    st.info("⏳ Iniciando consulta... (Etapa 3 em desenvolvimento)")
                
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.selected_periodos = {}
                    st.session_state.selected_cursos = []
                    st.session_state.formas_ingresso_selecionadas = []
                    st.rerun()
        
        # Informações técnicas
        with st.expander("🔧 Informações Técnicas"):
            status_info = f"""
            Status: {'Autenticado' if st.session_state.authenticated else 'Não autenticado'}
            Usuário: {st.session_state.username}
            Cookies ativos: {len(st.session_state.session.cookies)}
            """
            
            if st.session_state.selected_periodos:
                status_info += f"""
                Período configurado: {st.session_state.selected_periodos.get('inicial', 'N/A')} a {st.session_state.selected_periodos.get('final', 'N/A')}
                Cursos selecionados: {len(st.session_state.selected_cursos)}
                """
            
            st.code(status_info)

if __name__ == "__main__":
    main()
