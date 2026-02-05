"""
main.py - Aplicação Streamlit principal para automação de relatórios UFF
"""
import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd
import time
import logging
from bs4 import BeautifulSoup  # ADICIONAR ESTE IMPORT

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar diretório atual ao path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import UFFAuthenticator
from formulario_handler import FormularioHandler
from relatorio_automator import RelatorioUFFAutomator
from config import *
from utils import criar_resumo_relatorio

# Configuração da página
st.set_page_config(
    page_title="Automação de Relatórios UFF - Química",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar estado da sessão
def init_session_state():
    """Inicializa variáveis de estado da sessão"""
    default_states = {
        'authenticated': False,
        'authenticator': None,
        'username': '',
        'form_params': None,
        'selected_cursos': [],
        'selected_periodos': {},
        'formas_ingresso_selecionadas': [],
        'relatorios_baixados': {},
        'consulta_concluida': False,
        'dados_processados': {},
        'etapa_atual': 2,
        'localidade_selecionada': {'value': '1', 'text': 'Niterói'},
        'mostrar_dados_coletados': False
    }
    
    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Estilo CSS personalizado
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .css-1d391kg {
        padding-top: 1rem;
    }
    .relatorio-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: #f9f9f9;
    }
    .status-pronto {
        color: #28a745;
        font-weight: bold;
    }
    .status-processando {
        color: #ffc107;
        font-weight: bold;
    }
    .status-erro {
        color: #dc3545;
        font-weight: bold;
    }
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        border-radius: 10px;
        background-color: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Função para extrair parâmetros do formulário (da versão que funcionava)
def extract_form_parameters(session):
    """Extrai parâmetros do formulário de listagem de alunos"""
    try:
        response = session.get(
            "https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos",
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"Status code {response.status_code} ao acessar formulário")
            return None
        
        # REMOVER O IMPORT DAQUI E DEIXAR NO TOPO DO ARQUIVO
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form', {'id': 'rel_filtros'})
        if not form:
            logger.warning("Formulário com id 'rel_filtros' não encontrado, procurando alternativas...")
            # Tentar encontrar outros formulários
            form = soup.find('form', action=lambda x: x and 'listagens_alunos' in x)
            if not form:
                form = soup.find('form')
        
        if not form:
            logger.error("Nenhum formulário encontrado na página")
            return None
        
        logger.info(f"Formulário encontrado: {form.get('action', 'Sem ação')}")
        
        # Extrair token CSRF
        csrf_token = None
        csrf_input = soup.find('input', {'name': 'authenticity_token'})
        if csrf_input:
            csrf_token = csrf_input.get('value', '')
            logger.info(f"CSRF token encontrado: {csrf_token[:20]}...")
        else:
            logger.warning("Token CSRF não encontrado")
        
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
            logger.info(f"Localidades encontradas: {len(localidades)}")
        else:
            logger.warning("Select de localidade não encontrado")
        
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
            logger.info(f"Formas de ingresso encontradas: {len(formas_ingresso)}")
        else:
            logger.warning("Select de forma de ingresso não encontrado")
        
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
            logger.info(f"Períodos encontrados: {len(periodos)}")
        else:
            logger.warning("Select de período não encontrado")
        
        result = {
            'csrf_token': csrf_token,
            'localidades': localidades,
            'formas_ingresso': formas_ingresso,
            'periodos': periodos,
            'action': form.get('action', '')
        }
        
        logger.info("Parâmetros do formulário extraídos com sucesso")
        return result
        
    except Exception as e:
        logger.error(f"Erro ao extrair parâmetros: {str(e)}", exc_info=True)
        return None

# Funções auxiliares para processamento de períodos
def parse_periodo_texto(periodo_texto):
    """Extrai ano e semestre de um texto de período"""
    if not periodo_texto:
        return None, None
    
    import re
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
    """Compara dois períodos"""
    ano1, sem1 = parse_periodo_texto(periodo1)
    ano2, sem2 = parse_periodo_texto(periodo2)
    
    if ano1 is None or ano2 is None:
        return 0
    
    if ano1 < ano2:
        return -1
    elif ano1 > ano2:
        return 1
    else:
        if sem1 < sem2:
            return -1
        elif sem1 > sem2:
            return 1
        else:
            return 0

# Título principal
st.title("📊 Sistema de Análise de Evasão - UFF")
st.markdown("---")

# Seção de Login
if not st.session_state.authenticated:
    st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
    
    # Container centralizado para login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            
            with st.form("login_form"):
                username = st.text_input(
                    "Identificação (idUFF)", 
                    placeholder="CPF, email ou passaporte",
                    key="login_username"
                )
                password = st.text_input(
                    "Senha", 
                    type="password",
                    placeholder="Sua senha da UFF",
                    key="login_password"
                )
                
                submitted = st.form_submit_button("Acessar Sistema", type="primary", use_container_width=True)
                
                if submitted:
                    if not username or not password:
                        st.error("⚠️ Por favor, preencha todos os campos")
                    else:
                        with st.spinner("Conectando ao sistema da UFF..."):
                            try:
                                authenticator = UFFAuthenticator(username, password)
                                if authenticator.login():
                                    st.session_state.authenticator = authenticator
                                    st.session_state.authenticated = True
                                    st.session_state.username = username
                                    st.success("✅ Login realizado com sucesso!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Falha no login. Verifique suas credenciais.")
                            except Exception as e:
                                st.error(f"❌ Erro durante o login: {str(e)}")
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    with col3:
        st.write("")  # Espaço vazio para alinhamento
    
    # Informações sobre o sistema
    with st.expander("ℹ️ Sobre este sistema", expanded=True):
        st.markdown("""
        ### Sistema de Análise de Evasão - Departamento de Química UFF
        
        **Funcionalidades:**
        1. **Autenticação segura** no sistema UFF
        2. **Configuração automatizada** de parâmetros de relatório
        3. **Geração em lote** de relatórios por curso/ingresso
        4. **Monitoramento automático** do processamento
        5. **Download organizado** dos arquivos XLSX
        6. **Análise de evasão** por modalidade e motivo
        
        **Cursos suportados:**
        - Química (Licenciatura)
        - Química (Bacharelado) 
        - Química Industrial
        
        **⚠️ Aviso:** Use suas credenciais oficiais da UFF (mesmas do SIGA).
        """)
    
    st.markdown("---")
    st.info("👈 Use o formulário acima para fazer login com suas credenciais UFF.")

else:
    # Usuário autenticado - Menu principal
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.success(f"✅ Logado como: {st.session_state.username}")
    
    with col2:
        if st.button("🚪 Sair", type="secondary", use_container_width=True):
            if st.session_state.authenticator:
                st.session_state.authenticator.logout()
            
            # Limpar estado da sessão
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            st.rerun()
    
    st.markdown("---")
    
    # Progresso das etapas
    st.markdown("### 📋 Progresso do Processo")
    
    # Determinar etapa atual
    if not st.session_state.selected_periodos:
        etapa_atual = 2
    elif not st.session_state.consulta_concluida:
        etapa_atual = 3
    else:
        etapa_atual = 4
    
    col_e1, col_e2, col_e3, col_e4, col_e5 = st.columns(5)
    
    etapas = [
        ("1. Login", 1, st.session_state.authenticated),
        ("2. Período", 2, bool(st.session_state.selected_periodos)),
        ("3. Consulta", 3, st.session_state.consulta_concluida),
        ("4. Processamento", 4, etapa_atual >= 4),
        ("5. Planilha", 5, etapa_atual >= 5)
    ]
    
    for col, (nome, num, concluida) in zip([col_e1, col_e2, col_e3, col_e4, col_e5], etapas):
        with col:
            st.markdown(f"**{nome}**")
            if concluida:
                st.success("✅")
            elif etapa_atual == num:
                st.info("🔄")
            else:
                st.info("⏳")
    
    st.markdown("---")
    
    # Etapa 2 - Seleção de Período e Cursos (mantida da versão que funcionava)
    if etapa_atual == 2:
        st.markdown("## 📅 Etapa 2 - Seleção de Período e Cursos")
        
        # Carregar dados do formulário se necessário
        if st.session_state.form_params is None:
            with st.spinner("Carregando dados do sistema..."):
                st.session_state.form_params = extract_form_parameters(
                    st.session_state.authenticator.session
                )
        
        if st.session_state.form_params is None:
            st.error("Não foi possível carregar os dados do sistema.")
            
            # Tentar diagnóstico
            with st.expander("🔍 Diagnóstico de Problemas"):
                st.write("Possíveis causas:")
                st.write("1. A sessão pode ter expirado")
                st.write("2. O sistema UFF pode estar indisponível")
                st.write("3. Permissões insuficientes")
                
                if st.button("🔄 Testar Conexão"):
                    try:
                        test_response = st.session_state.authenticator.session.get(
                            "https://app.uff.br/graduacao/administracaoacademica",
                            timeout=10
                        )
                        st.write(f"Status: {test_response.status_code}")
                        if test_response.status_code == 200:
                            st.success("✅ Conexão bem-sucedida")
                        else:
                            st.error(f"❌ Erro: {test_response.status_code}")
                    except Exception as e:
                        st.error(f"❌ Erro de conexão: {str(e)}")
            
            if st.button("🔄 Tentar novamente"):
                st.rerun()
            if st.button("🔙 Fazer logout e tentar novamente"):
                st.session_state.authenticator.logout()
                st.session_state.authenticated = False
                st.rerun()
        else:
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
                    # Mostrar opções disponíveis
                    st.error("Localidade Niterói não encontrada")
                    st.write("Localidades disponíveis:")
                    for loc in localidades:
                        st.write(f"- {loc['text']} (valor: {loc['value']})")
                    # Usar a primeira localidade se Niterói não estiver disponível
                    if localidades:
                        localidade_niteroi = localidades[0]
                        localidade_value = localidade_niteroi['value']
                        st.warning(f"Usando: {localidade_niteroi['text']} como alternativa")
                
                # Forma de Ingresso - AMBOS SISUS PRÉ-SELECIONADOS
                formas_ingresso = form_params.get('formas_ingresso', [])
                formas_sisu = [f for f in formas_ingresso if 'SISU' in f['text']]
                
                if len(formas_sisu) >= 2:
                    # Separar SISU 1ª e 2ª Edição
                    sisu_1 = next((f for f in formas_sisu if '1ª' in f['text'] or '1º' in f['text'] or '1°' in f['text']), None)
                    sisu_2 = next((f for f in formas_sisu if '2ª' in f['text'] or '2º' in f['text'] or '2°' in f['text']), None)
                    
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
                        
                        # Mostrar todas as formas disponíveis para debug
                        with st.expander("Ver todas as formas de ingresso disponíveis"):
                            for forma in formas_ingresso:
                                st.write(f"- {forma['text']} (valor: {forma['value']})")
                else:
                    st.error("Formas de ingresso SISU não encontradas")
                    st.write("Formas disponíveis:")
                    for forma in formas_ingresso:
                        st.write(f"- {forma['text']} (valor: {forma['value']})")
            
            with col2:
                st.subheader("🎯 Seleção de Períodos")
                
                # Períodos disponíveis
                periodos = form_params.get('periodos', [])
                
                if not periodos:
                    st.error("Nenhum período disponível")
                    st.write("A lista de períodos está vazia")
                else:
                    # Filtrar apenas períodos válidos (remover "--- Todos ---")
                    periodos_validos = [p for p in periodos if p['text'] != '--- Todos ---']
                    
                    if not periodos_validos:
                        st.error("Nenhum período válido encontrado")
                        st.write("Todos os períodos são '--- Todos ---'")
                        # Usar períodos mesmo sendo "Todos" se não houver outros
                        periodos_validos = periodos
                    
                    # Converter para lista de textos
                    periodo_textos = [p['text'] for p in periodos_validos]
                    periodo_valores = {p['text']: p['value'] for p in periodos_validos}
                    
                    if not periodo_textos:
                        st.error("Períodos não disponíveis")
                    else:
                        # Ordenar períodos do mais antigo para o mais recente
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
                        
                        if periodos_com_info:
                            # Ordenar do mais antigo para mais recente
                            periodos_com_info.sort(key=lambda x: x['valor_ordenacao'])
                            periodo_textos_ordenados = [p['texto'] for p in periodos_com_info]
                            
                            # ENCONTRAR 2013/1° COMO PADRÃO INICIAL
                            idx_2013_1 = -1
                            for i, periodo in enumerate(periodo_textos_ordenados):
                                if '2013 / 1' in periodo:
                                    idx_2013_1 = i
                                    break
                            
                            # Se não encontrar 2013/1, usar o mais antigo disponível
                            idx_inicial = idx_2013_1 if idx_2013_1 != -1 else 0
                            
                            # Período Inicial (MAIS ANTIGO - início do intervalo)
                            periodo_inicial_texto = st.selectbox(
                                "Período Inicial (início do intervalo)",
                                options=periodo_textos_ordenados,
                                index=idx_inicial,
                                help="Selecione o período mais ANTIGO do intervalo de análise",
                                key="periodo_inicial"
                            )
                            
                            # Período Final (MAIS RECENTE - fim do intervalo)
                            periodo_inicial_idx = periodo_textos_ordenados.index(periodo_inicial_texto)
                            periodos_finais_disponiveis = periodo_textos_ordenados[periodo_inicial_idx:]
                            idx_final_disponivel = len(periodos_finais_disponiveis) - 1
                            
                            periodo_final_texto = st.selectbox(
                                "Período Final (fim do intervalo)",
                                options=periodos_finais_disponiveis,
                                index=idx_final_disponivel,
                                help="Selecione o período mais RECENTE do intervalo de análise",
                                key="periodo_final"
                            )
                        else:
                            # Se não conseguir parsear períodos, mostrar lista simples
                            st.warning("Não foi possível ordenar períodos automaticamente")
                            periodo_inicial_texto = st.selectbox(
                                "Período Inicial",
                                options=periodo_textos,
                                key="periodo_inicial_simple"
                            )
                            periodo_final_texto = st.selectbox(
                                "Período Final",
                                options=periodo_textos,
                                key="periodo_final_simple"
                            )
            
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
                help="Os 3 cursos de Química estão pré-selecionados",
                key="cursos_selecao"
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
                validation_errors = []
                
                if not formas_valores or len(formas_valores) != 2:
                    validation_errors.append("As duas formas de ingresso SISU devem estar selecionadas")
                
                if not cursos_selecionados_objetos:
                    validation_errors.append("Selecione pelo menos um curso")
                
                if not periodo_inicial_texto or not periodo_final_texto:
                    validation_errors.append("Selecione os períodos")
                else:
                    # Validar intervalo
                    resultado = comparar_periodos(periodo_inicial_texto, periodo_final_texto)
                    if resultado == 1:  # Inicial > Final (inválido)
                        validation_errors.append("Período inicial não pode ser posterior ao final")
                
                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                else:
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
                        'text': localidade_niteroi['text'] if localidade_niteroi else 'Niterói',
                        'value': localidade_value
                    }
                    
                    st.success("🎉 Configuração salva com sucesso!")
                    
                    # Mostrar resumo
                    with st.expander("📋 Resumo da Configuração", expanded=True):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**Localidade:** {st.session_state.localidade_selecionada['text']}")
                            st.write(f"**Formas de Ingresso:** {', '.join(formas_selecionadas)}")
                        with col_b:
                            st.write(f"**Período:** {periodo_inicial_texto} a {periodo_final_texto}")
                        
                        st.write("**Cursos selecionados:**")
                        for curso in cursos_selecionados_objetos:
                            st.write(f"- {curso['nome']} ({curso['tipo']})")
                    
                    time.sleep(2)
                    st.rerun()
            
            # Mostrar pré-visualização
            if cursos_selecionados_objetos and 'formas_selecionadas' in locals():
                with st.expander("📋 Pré-visualização da Configuração", expanded=False):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Localidade:** {localidade_niteroi['text'] if localidade_niteroi else 'N/A'}")
                        st.markdown(f"**Formas de Ingresso:** {' e '.join(formas_selecionadas)}")
                    with col_b:
                        st.markdown(f"**Período Inicial:** {periodo_inicial_texto}")
                        st.markdown(f"**Período Final:** {periodo_final_texto}")
                    
                    st.markdown("**Cursos:**")
                    for curso in cursos_selecionados_objetos:
                        st.markdown(f"- {curso['nome']}")
    # ADICIONAR ESTAS FUNÇÕES NOVAS NO main.py, ANTES DA SEÇÃO "Etapa 3"

def buscar_cursos_por_localidade(session, localidade_id):
    """Busca cursos disponíveis para uma localidade"""
    try:
        url = f"{APLICACAO_URL}/relatorios/listagens_alunos/cursos?localidade={localidade_id}"
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            cursos = []
            
            for option in soup.find_all('option'):
                if option.get('value') and option.get('value') != '':
                    cursos.append({
                        'value': option['value'],
                        'text': option.get_text(strip=True)
                    })
            
            return cursos
    except Exception as e:
        logger.error(f"Erro ao buscar cursos: {str(e)}")
    
    return []

def buscar_desdobramentos_por_curso(session, curso_id):
    """Busca desdobramentos disponíveis para um curso"""
    try:
        url = f"{APLICACAO_URL}/relatorios/listagens_alunos/desdobramentos?curso={curso_id}"
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            desdobramentos = []
            
            for option in soup.find_all('option'):
                if option.get('value') and option.get('value') != '':
                    desdobramentos.append({
                        'value': option['value'],
                        'text': option.get_text(strip=True)
                    })
            
            return desdobramentos
    except Exception as e:
        logger.error(f"Erro ao buscar desdobramentos: {str(e)}")
    
    return []

def encontrar_desdobramento_curso(desdobramentos, texto_busca):
    """Encontra o desdobramento correspondente ao curso"""
    if not desdobramentos:
        return None
    
    for desdobramento in desdobramentos:
        if texto_busca in desdobramento['text']:
            return desdobramento
    
    # Se não encontrar exato, procurar por similaridade
    for desdobramento in desdobramentos:
        if 'química' in desdobramento['text'].lower():
            return desdobramento
    
    return None

def gerar_relatorio_xlsx(session, form_data):
    """Gera e baixa relatório em XLSX"""
    try:
        url = f"{APLICACAO_URL}/relatorios/listagens_alunos"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url,
            'Origin': BASE_URL,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        # Adicionar formato XLSX
        form_data['format'] = 'xls'
        
        response = session.post(
            url,
            data=form_data,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )
        
        if response.status_code == 200:
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url and 'listagens_alunos' not in response.url:
                # Extrair ID do relatório da URL
                import re
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    relatorio_id = match.group(1)
                    logger.info(f"Relatório criado com ID: {relatorio_id}")
                    return {
                        'success': True,
                        'relatorio_id': relatorio_id,
                        'url_relatorio': response.url,
                        'html': response.text
                    }
            
            # Verificar se é um arquivo XLSX (download direto)
            content_type = response.headers.get('content-type', '')
            if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type or \
               'xlsx' in content_type or \
               'excel' in content_type.lower():
                
                # Retornar conteúdo do arquivo
                return {
                    'success': True,
                    'conteudo': response.content,
                    'diretamente': True
                }
        
        return {
            'success': False,
            'error': f"Status code: {response.status_code}",
            'html': response.text[:500] if response.text else ''
        }
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def processar_consulta_relatorios():
    """Processa a consulta de relatórios para todos os cursos selecionados"""
    
    st.session_state.relatorios_baixados = {}
    st.session_state.dados_processados = {}
    
    # Configurações base
    config = {
        'localidade': st.session_state.localidade_selecionada['value'],
        'forma_ingresso': st.session_state.formas_ingresso_selecionadas,
        'periodo_inicial': st.session_state.selected_periodos['valor_inicial'],
        'periodo_final': st.session_state.selected_periodos['valor_final'],
        'csrf_token': st.session_state.form_params['csrf_token'] if st.session_state.form_params else ''
    }
    
    # Status para cada curso
    status_cursos = {}
    
    # Barra de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    mensagens = st.empty()
    
    # Para cada curso selecionado
    cursos = st.session_state.selected_cursos
    total_cursos = len(cursos)
    
    for idx, curso in enumerate(cursos):
        curso_nome = curso['nome']
        codigo_curso = curso['codigo']
        desdobramento_texto = curso['desdobramento']
        
        # Atualizar status
        status_text.text(f"Consultando curso: {curso_nome}...")
        mensagens.text(f"Progresso: {idx+1}/{total_cursos}")
        progress_bar.progress((idx) / total_cursos)
        
        try:
            # 1. Buscar cursos disponíveis para a localidade
            status_text.text(f"Buscando cursos disponíveis para {curso_nome}...")
            cursos_disponiveis = buscar_cursos_por_localidade(
                st.session_state.authenticator.session, 
                config['localidade']
            )
            
            if not cursos_disponiveis:
                status_cursos[curso_nome] = {
                    'status': 'erro',
                    'mensagem': 'Nenhum curso encontrado para a localidade selecionada'
                }
                continue
            
            # 2. Encontrar o curso específico
            curso_encontrado = None
            for curso_disp in cursos_disponiveis:
                if codigo_curso in curso_disp['text'] or curso_nome.lower() in curso_disp['text'].lower():
                    curso_encontrado = curso_disp
                    break
            
            if not curso_encontrado:
                # Mostrar opções disponíveis para debug
                logger.warning(f"Cursos disponíveis para {curso_nome}:")
                for c in cursos_disponiveis[:5]:  # Mostrar apenas os primeiros 5
                    logger.warning(f"  - {c['text']} (valor: {c['value']})")
                
                status_cursos[curso_nome] = {
                    'status': 'erro', 
                    'mensagem': f'Curso {curso_nome} não encontrado no sistema'
                }
                continue
            
            # 3. Buscar desdobramentos para o curso
            status_text.text(f"Buscando desdobramentos para {curso_nome}...")
            desdobramentos = buscar_desdobramentos_por_curso(
                st.session_state.authenticator.session,
                curso_encontrado['value']
            )
            
            if not desdobramentos:
                status_cursos[curso_nome] = {
                    'status': 'erro',
                    'mensagem': 'Nenhum desdobramento encontrado'
                }
                continue
            
            # 4. Encontrar desdobramento específico
            desdobramento_encontrado = encontrar_desdobramento_curso(
                desdobramentos,
                desdobramento_texto
            )
            
            if not desdobramento_encontrado:
                # Usar o primeiro desdobramento disponível
                desdobramento_encontrado = desdobramentos[0]
                logger.warning(f"Usando desdobramento alternativo: {desdobramento_encontrado['text']}")
            
            # 5. Preparar dados do formulário
            form_data = {
                'authenticity_token': config['csrf_token'],
                'utf8': '✓',
                'idlocalidade': config['localidade'],
                'idcurso': curso_encontrado['value'],
                'iddesdobramento': desdobramento_encontrado['value'],
                'idturno': '',  # Todos
                'idstatusaluno': '',  # Todos
                'idsituacaoaluno': '',  # Todos
                'idformaingresso': config['forma_ingresso'][0],  # Primeiro SISU
                'idacaoafirmativa': '',  # Todos
                'anosem_ingresso': config['periodo_inicial'],
                'anosem_desvinculacao': ''  # Todos
            }
            
            # 6. Gerar relatório XLSX
            status_text.text(f"Gerando relatório para {curso_nome}...")
            resultado = gerar_relatorio_xlsx(
                st.session_state.authenticator.session,
                form_data
            )
            
            if resultado['success']:
                if resultado.get('diretamente'):
                    # Download direto do arquivo
                    st.session_state.relatorios_baixados[curso_nome] = {
                        'conteudo': resultado['conteudo'],
                        'curso_id': curso_encontrado['value'],
                        'desdobramento_id': desdobramento_encontrado['value'],
                        'status': 'sucesso',
                        'tipo': 'diretamente'
                    }
                    
                    status_cursos[curso_nome] = {
                        'status': 'sucesso',
                        'mensagem': 'Relatório baixado diretamente'
                    }
                    
                else:
                    # Relatório em processamento (tem ID)
                    relatorio_id = resultado['relatorio_id']
                    url_relatorio = resultado['url_relatorio']
                    
                    # Usar o RelatorioUFFAutomator para monitorar e baixar
                    automator = RelatorioUFFAutomator(st.session_state.authenticator.session)
                    
                    # Monitorar até estar pronto
                    status_text.text(f"Monitorando processamento do relatório #{relatorio_id}...")
                    
                    def callback_progresso(progresso, mensagem, concluido):
                        status_text.text(mensagem)
                        progress_bar.progress(progresso)
                    
                    status_info = automator.aguardar_conclusao(
                        relatorio_id,
                        callback_progresso=callback_progresso,
                        intervalo=10,  # Verificar a cada 10 segundos
                        timeout=300   # Timeout de 5 minutos
                    )
                    
                    if status_info and status_info['status'] == 'PRONTO':
                        # Baixar o relatório
                        caminho = automator.baixar_relatorio(status_info)
                        
                        if caminho:
                            # Ler o arquivo baixado
                            try:
                                df = pd.read_excel(caminho)
                                st.session_state.relatorios_baixados[curso_nome] = {
                                    'df': df,
                                    'caminho': caminho,
                                    'curso_id': curso_encontrado['value'],
                                    'desdobramento_id': desdobramento_encontrado['value'],
                                    'status': 'sucesso',
                                    'linhas': len(df),
                                    'relatorio_id': relatorio_id
                                }
                                
                                status_cursos[curso_nome] = {
                                    'status': 'sucesso',
                                    'mensagem': f'Relatório com {len(df)} linhas baixado'
                                }
                                
                                # Pré-processar dados
                                dados_processados = preprocessar_dados_relatorio(df)
                                st.session_state.dados_processados[curso_nome] = dados_processados
                                
                            except Exception as e:
                                logger.error(f"Erro ao ler arquivo Excel: {str(e)}")
                                status_cursos[curso_nome] = {
                                    'status': 'erro',
                                    'mensagem': f'Erro ao processar arquivo: {str(e)}'
                                }
                        else:
                            status_cursos[curso_nome] = {
                                'status': 'erro',
                                'mensagem': 'Falha ao baixar relatório'
                            }
                    else:
                        status_cursos[curso_nome] = {
                            'status': 'erro',
                            'mensagem': 'Timeout no processamento do relatório'
                        }
                
            else:
                status_cursos[curso_nome] = {
                    'status': 'erro',
                    'mensagem': f'Falha ao gerar relatório: {resultado.get("error", "Erro desconhecido")}'
                }
                
        except Exception as e:
            logger.error(f"Erro no processamento do curso {curso_nome}: {str(e)}", exc_info=True)
            status_cursos[curso_nome] = {
                'status': 'erro',
                'mensagem': f'Erro: {str(e)}'
            }
        
        # Pequena pausa entre requisições para não sobrecarregar o servidor
        time.sleep(1)
    
    # Finalizar barra de progresso
    progress_bar.progress(1.0)
    status_text.text("Consulta concluída!")
    mensagens.empty()
    
    # Resumo da consulta
    return status_cursos

def preprocessar_dados_relatorio(df):
    """Pré-processa dados do relatório para análise"""
    if df.empty:
        return {}
    
    # Criar cópia para não modificar o original
    df_processed = df.copy()
    
    # Converter nomes de colunas para minúsculas e remover espaços
    df_processed.columns = [str(col).strip().lower() for col in df_processed.columns]
    
    # Mapear colunas esperadas
    colunas_mapeadas = {}
    
    # Tentar identificar colunas importantes
    for col in df_processed.columns:
        col_lower = str(col).lower()
        
        if any(term in col_lower for term in ['matrícula', 'matricula']):
            colunas_mapeadas['matricula'] = col
        elif any(term in col_lower for term in ['nome', 'aluno']):
            colunas_mapeadas['nome'] = col
        elif any(term in col_lower for term in ['situação', 'situacao']):
            colunas_mapeadas['situacao'] = col
        elif any(term in col_lower for term in ['status']):
            colunas_mapeadas['status'] = col
        elif any(term in col_lower for term in ['ingresso', 'forma ingresso']):
            colunas_mapeadas['forma_ingresso'] = col
        elif any(term in col_lower for term in ['modalidade', 'ação afirmativa', 'acao afirmativa']):
            colunas_mapeadas['modalidade_ingresso'] = col
        elif any(term in col_lower for term in ['cancelamento', 'motivo']):
            colunas_mapeadas['motivo_cancelamento'] = col
    
    # Estatísticas básicas
    estatisticas = {
        'total_registros': len(df_processed),
        'colunas_identificadas': colunas_mapeadas,
        'colunas_disponiveis': list(df_processed.columns),
        'amostra_dados': df_processed.head(3).to_dict('records') if not df_processed.empty else []
    }
    
    return {
        'df': df_processed,
        'estatisticas': estatisticas,
        'colunas_mapeadas': colunas_mapeadas
    }
    
    # NO main.py, SUBSTITUIR A SEÇÃO "Etapa 3" COMPLETA POR:

    # Etapa 3 - Consulta de Relatórios
    elif etapa_atual == 3:
        st.markdown("## 🔍 Etapa 3 - Consulta de Relatórios")
        
        # Verificar se há configuração salva
        if not st.session_state.selected_periodos or not st.session_state.selected_cursos:
            st.error("Configure primeiro os períodos e cursos na Etapa 2")
            if st.button("🔙 Voltar para Etapa 2"):
                st.session_state.etapa_atual = 2
                st.rerun()
        else:
            # Mostrar resumo da configuração
            with st.expander("📋 Configuração Atual", expanded=True):
                periodos = st.session_state.selected_periodos
                cursos = st.session_state.selected_cursos
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Período:** {periodos['inicial']} a {periodos['final']}")
                    st.markdown(f"**Localidade:** {st.session_state.localidade_selecionada['text']}")
                    st.markdown(f"**Formas de Ingresso:** SISU 1ª e 2ª Edição")
                
                with col2:
                    st.markdown("**Cursos:**")
                    for curso in cursos:
                        st.markdown(f"- {curso['nome']} ({curso['tipo']})")
            
            st.markdown("---")
            
            if not st.session_state.consulta_concluida:
                st.markdown("### ⚙️ Preparar Consulta")
                
                # Informações sobre o processo
                with st.expander("ℹ️ Informações Importantes", expanded=True):
                    st.warning("""
                    **⚠️ ATENÇÃO:**
                    
                    1. A geração de relatórios pode levar **vários minutos** por curso
                    2. **Não feche** esta página durante o processo
                    3. O sistema irá automaticamente:
                       - Buscar cada curso no sistema UFF
                       - Configurar os parâmetros corretos
                       - Gerar o relatório XLSX
                       - Monitorar o processamento
                       - Baixar quando estiver pronto
                    
                    4. **Progresso** será mostrado em tempo real
                    5. Se houver erros, serão exibidos com detalhes
                    """)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🚀 Iniciar Consulta de Relatórios", type="primary", use_container_width=True):
                        # Iniciar consulta
                        st.session_state.consulta_em_andamento = True
                        st.rerun()
                
                with col2:
                    if st.button("🧪 Testar Conexão", type="secondary", use_container_width=True):
                        with st.spinner("Testando conexão..."):
                            try:
                                test_url = f"{APLICACAO_URL}/relatorios/listagens_alunos"
                                response = st.session_state.authenticator.session.get(test_url, timeout=10)
                                if response.status_code == 200:
                                    st.success("✅ Conexão com sistema UFF OK")
                                else:
                                    st.error(f"❌ Erro de conexão: {response.status_code}")
                            except Exception as e:
                                st.error(f"❌ Erro: {str(e)}")
                
                with col3:
                    if st.button("🔄 Voltar para Configuração", type="secondary", use_container_width=True):
                        st.session_state.selected_periodos = {}
                        st.session_state.selected_cursos = []
                        st.session_state.etapa_atual = 2
                        st.rerun()
            
            # Se a consulta está em andamento
            if st.session_state.get('consulta_em_andamento', False):
                st.markdown("---")
                st.markdown("### 🔄 Consulta em Andamento")
                
                # Container para logs e progresso
                log_container = st.container()
                
                with log_container:
                    # Executar a consulta
                    resultados = processar_consulta_relatorios()
                    
                    # Marcar como concluída
                    st.session_state.consulta_concluida = True
                    st.session_state.consulta_em_andamento = False
                    
                    # Mostrar resultados
                    st.markdown("### 📊 Resultados da Consulta")
                    
                    # Estatísticas
                    total_cursos = len(st.session_state.selected_cursos)
                    sucesso = sum(1 for curso in st.session_state.selected_cursos 
                                 if curso['nome'] in st.session_state.relatorios_baixados and 
                                 st.session_state.relatorios_baixados[curso['nome']]['status'] == 'sucesso')
                    erros = total_cursos - sucesso
                    
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        st.metric("Total de Cursos", total_cursos)
                    with col_s2:
                        st.metric("Sucesso", sucesso, delta=f"{sucesso/total_cursos*100:.1f}%" if total_cursos > 0 else "0%")
                    with col_s3:
                        st.metric("Erros", erros, delta_color="inverse")
                    
                    # Detalhes por curso
                    st.markdown("#### 📋 Detalhes por Curso")
                    
                    for curso in st.session_state.selected_cursos:
                        curso_nome = curso['nome']
                        
                        with st.expander(f"{'✅' if curso_nome in st.session_state.relatorios_baixados and st.session_state.relatorios_baixados[curso_nome]['status'] == 'sucesso' else '❌'} {curso_nome}", expanded=False):
                            if curso_nome in st.session_state.relatorios_baixados:
                                dados = st.session_state.relatorios_baixados[curso_nome]
                                
                                if dados['status'] == 'sucesso':
                                    st.success("✅ Relatório baixado com sucesso")
                                    
                                    # Informações do DataFrame
                                    if 'df' in dados:
                                        df = dados['df']
                                        st.markdown(f"**Total de registros:** {len(df):,}")
                                        st.markdown(f"**Colunas disponíveis:** {len(df.columns)}")
                                        
                                        # Pré-visualização dos dados
                                        st.markdown("**Pré-visualização:**")
                                        st.dataframe(df.head(), use_container_width=True)
                                        
                                        # Colunas identificadas
                                        if curso_nome in st.session_state.dados_processados:
                                            proc = st.session_state.dados_processados[curso_nome]
                                            st.markdown("**Colunas identificadas:**")
                                            for chave, coluna in proc['colunas_mapeadas'].items():
                                                st.markdown(f"- `{chave}`: {coluna}")
                                        
                                        # Botão para download
                                        if 'df' in dados:
                                            csv = df.to_csv(index=False).encode('utf-8')
                                            st.download_button(
                                                label="📥 Download CSV",
                                                data=csv,
                                                file_name=f"relatorio_{curso_nome.replace(' ', '_').lower()}.csv",
                                                mime="text/csv",
                                                use_container_width=True
                                            )
                                    else:
                                        st.info("Relatório baixado, mas não processado como DataFrame")
                                
                                else:
                                    st.error(f"❌ Falha: {dados.get('mensagem', 'Erro desconhecido')}")
                            else:
                                st.warning("⏳ Relatório não disponível")
                    
                    # Botões de controle após consulta
                    st.markdown("---")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    
                    with col_b1:
                        if st.button("🔄 Refazer Consulta", type="secondary", use_container_width=True):
                            st.session_state.consulta_concluida = False
                            st.session_state.consulta_em_andamento = False
                            st.session_state.relatorios_baixados = {}
                            st.session_state.dados_processados = {}
                            st.rerun()
                    
                    with col_b2:
                        if st.button("⚙️ Alterar Configuração", type="secondary", use_container_width=True):
                            st.session_state.selected_periodos = {}
                            st.session_state.selected_cursos = []
                            st.session_state.consulta_concluida = False
                            st.session_state.consulta_em_andamento = False
                            st.session_state.relatorios_baixados = {}
                            st.session_state.dados_processados = {}
                            st.session_state.etapa_atual = 2
                            st.rerun()
                    
                    with col_b3:
                        if sucesso > 0:
                            if st.button("🚀 Avançar para Processamento", type="primary", use_container_width=True):
                                st.session_state.etapa_atual = 4
                                st.success("Pronto para Etapa 4 - Processamento dos Dados!")
                                st.rerun()
                        else:
                            st.button("🚀 Avançar para Processamento", disabled=True, use_container_width=True)
            
            # Se consulta já foi concluída anteriormente
            elif st.session_state.consulta_concluida:
                st.markdown("### 📊 Consulta Concluída Anteriormente")
                
                # Mostrar resumo dos dados já coletados
                if st.session_state.relatorios_baixados:
                    total_registros = sum(
                        len(data['df']) 
                        for curso, data in st.session_state.relatorios_baixados.items() 
                        if 'df' in data and data['status'] == 'sucesso'
                    )
                    
                    st.info(f"✅ {len(st.session_state.relatorios_baixados)} curso(s) com dados coletados")
                    st.info(f"📊 Total de registros: {total_registros:,}")
                    
                    if st.button("🚀 Continuar para Processamento", type="primary", use_container_width=True):
                        st.session_state.etapa_atual = 4
                        st.rerun()
                    
                    if st.button("🔄 Refazer Consulta", type="secondary", use_container_width=True):
                        st.session_state.consulta_concluida = False
                        st.session_state.relatorios_baixados = {}
                        st.session_state.dados_processados = {}
                        st.rerun()    
    # Etapa 4 - Processamento dos Dados
    elif etapa_atual >= 4:
        st.markdown("## ⚙️ Etapa 4 - Processamento dos Dados")
        
        if st.session_state.consulta_concluida and st.session_state.relatorios_baixados:
            # Resumo dos dados coletados
            st.markdown("### 📊 Dados Coletados")
            
            total_registros = sum(
                len(data['df']) 
                for curso, data in st.session_state.relatorios_baixados.items() 
                if data['status'] == 'sucesso'
            )
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("Cursos com dados", len(st.session_state.relatorios_baixados))
            with col_r2:
                st.metric("Total de registros", total_registros)
            with col_r3:
                st.metric("Próxima etapa", "Processamento")
            
            st.markdown("---")
            st.markdown("### 🚀 Próximos Passos")
            
            st.info("""
            **O processamento dos dados incluirá:**
            
            1. **Normalização de legendas**:
               - "Inscrito", "Concluinte", "Pendente" → Inscritos/Pendentes/Concluintes
            
            2. **Cálculo de matrículas ativas**:
               - Inscritos + Pendentes + Concluintes + Trancados
            
            3. **Classificação de cancelamentos**:
               - Solicitação Oficial
               - Abandono  
               - Insuficiência de Aproveitamento
               - Ingressante - Insuf. Aproveit.
               - Mudança de Curso
               - Outros
            
            4. **Separação por modalidade**:
               - Código começando com "A" → Ampla Concorrência
               - Código começando com "L" → Ações Afirmativas
            
            5. **Cálculo de taxa de evasão**:
               - Percentual por curso
               - Percentual por motivo de cancelamento
            """)
            
            # Botões de controle
            col_b1, col_b2, col_b3 = st.columns(3)
            
            with col_b1:
                if st.button("🔍 Ver Dados Coletados", type="secondary", use_container_width=True):
                    st.session_state.mostrar_dados_coletados = True
            
            with col_b2:
                if st.button("🔄 Voltar para Consulta", type="secondary", use_container_width=True):
                    st.session_state.etapa_atual = 3
                    st.rerun()
            
            with col_b3:
                if st.button("⚙️ Iniciar Processamento", type="primary", use_container_width=True):
                    st.info("Iniciando processamento dos dados...")
                    # TODO: Implementar processamento real
        
        else:
            st.warning("Nenhum dado coletado ainda. Complete a Etapa 3 primeiro.")
            if st.button("🔙 Voltar para Etapa 3"):
                st.session_state.etapa_atual = 3
                st.rerun()

# Rodapé
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col1:
    st.caption(f"🕒 Última atualização: {datetime.now().strftime('%H:%M:%S')}")
with footer_col2:
    st.caption("📊 Departamento de Química - UFF")
with footer_col3:
    st.caption("🔒 Sistema de automação seguro")

# Script de inicialização
if __name__ == "__main__":
    # Criar pastas necessárias
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    
    # Registrar início
    if st.session_state.get('authenticated'):
        logger.info(f"Sistema iniciado para usuário: {st.session_state.username}")
