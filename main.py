# main.py - VERSÃO COMPLETA CORRIGIDA
import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd
import time
import logging
from bs4 import BeautifulSoup
import re

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar diretório atual ao path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import UFFAuthenticator

# URLs do sistema
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
PASTA_RELATORIOS = 'relatorios'

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
        'mostrar_dados_coletados': False,
        'consulta_em_andamento': False
    }
    
    for key, default_value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# Função para extrair parâmetros do formulário
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
        
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form', {'id': 'rel_filtros'})
        if not form:
            logger.warning("Formulário com id 'rel_filtros' não encontrado")
            form = soup.find('form', action=lambda x: x and 'listagens_alunos' in x)
        
        if not form:
            logger.error("Nenhum formulário encontrado na página")
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
                        'text': option.get_text(strip=True)
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
        logger.error(f"Erro ao extrair parâmetros: {str(e)}")
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
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            username = st.text_input(
                "Identificação (idUFF)", 
                placeholder="CPF, email ou passaporte"
            )
            password = st.text_input(
                "Senha", 
                type="password",
                placeholder="Sua senha da UFF"
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
        """)

else:
    # Usuário autenticado - Menu principal
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.success(f"✅ Logado como: {st.session_state.username}")
    
    with col2:
        if st.button("🚪 Sair", type="secondary", use_container_width=True):
            if st.session_state.authenticator:
                st.session_state.authenticator.logout()
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
    
    # Etapa 2 - Seleção de Período e Cursos
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
            if st.button("🔄 Tentar novamente"):
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
                    st.error("Localidade Niterói não encontrada")
                    # Em vez de 'return', usamos um valor padrão ou paramos o fluxo
                    if localidades:
                        # Usar a primeira localidade disponível
                        localidade_niteroi = localidades[0]
                        localidade_value = localidade_niteroi['value']
                        st.warning(f"Usando alternativa: {localidade_niteroi['text']}")
                    else:
                        st.error("Nenhuma localidade disponível")
                        st.stop()  # Para a execução
                
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
                        # Mostrar opções disponíveis
                        with st.expander("Formas disponíveis"):
                            for forma in formas_ingresso:
                                st.write(f"- {forma['text']} (valor: {forma['value']})")
                else:
                    st.error("Formas de ingresso SISU não encontradas")
                    with st.expander("Formas disponíveis"):
                        for forma in formas_ingresso:
                            st.write(f"- {forma['text']} (valor: {forma['value']})")
            
            with col2:
                st.subheader("🎯 Seleção de Períodos")
                
                # Períodos disponíveis
                periodos = form_params.get('periodos', [])
                
                if not periodos:
                    st.error("Nenhum período disponível")
                else:
                    # Filtrar apenas períodos válidos (remover "--- Todos ---")
                    periodos_validos = [p for p in periodos if p['text'] != '--- Todos ---']
                    
                    # Se não houver períodos válidos, usar todos
                    if not periodos_validos:
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
                            periodo_inicial_texto = st.selectbox(
                                "Período Inicial",
                                options=periodo_textos,
                                key="periodo_inicial_simple"
                            )
                            periodo_final_texto = st.selectbox(
                                "Período Final",
                                options=periodo_textos,
                                index=len(periodo_textos)-1,
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
                
                if 'formas_valores' not in locals() or not formas_valores or len(formas_valores) < 2:
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
                            if 'formas_selecionadas' in locals():
                                st.write(f"**Formas de Ingresso:** {', '.join(formas_selecionadas)}")
                        with col_b:
                            st.write(f"**Período:** {periodo_inicial_texto} a {periodo_final_texto}")
                        
                        st.write("**Cursos selecionados:**")
                        for curso in cursos_selecionados_objetos:
                            st.write(f"- {curso['nome']} ({curso['tipo']})")
                    
                    time.sleep(2)
                    st.rerun()
            
            # Mostrar pré-visualização
            if cursos_selecionados_objetos:
                with st.expander("📋 Pré-visualização da Configuração", expanded=False):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Localidade:** {localidade_niteroi['text'] if localidade_niteroi else 'N/A'}")
                        if 'formas_selecionadas' in locals():
                            st.markdown(f"**Formas de Ingresso:** {' e '.join(formas_selecionadas)}")
                    with col_b:
                        st.markdown(f"**Período Inicial:** {periodo_inicial_texto}")
                        st.markdown(f"**Período Final:** {periodo_final_texto}")
                    
                    st.markdown("**Cursos:**")
                    for curso in cursos_selecionados_objetos:
                        st.markdown(f"- {curso['nome']}")
    
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
                st.info("""
                **O que acontecerá na consulta:**
                1. Para cada curso selecionado, o sistema irá:
                   - Buscar o código do curso no sistema UFF
                   - Buscar o desdobramento correto
                   - Configurar os parâmetros do relatório
                   - Enviar solicitação de geração do relatório XLSX
                
                2. **Importante:** A geração de relatórios pode levar vários minutos
                
                3. O sistema monitorará automaticamente o processamento
                
                4. Quando pronto, fará o download do arquivo XLSX
                """)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚀 Iniciar Consulta de Relatórios", type="primary", use_container_width=True):
                        # Implementar a lógica de consulta aqui
                        st.info("Funcionalidade de consulta será implementada")
                        # TODO: Implementar usando RelatorioUFFAutomator
                
                with col2:
                    if st.button("🔄 Voltar para Configuração", type="secondary", use_container_width=True):
                        st.session_state.selected_periodos = {}
                        st.session_state.selected_cursos = []
                        st.session_state.etapa_atual = 2
                        st.rerun()
            
            # Se consulta foi concluída
            elif st.session_state.consulta_concluida:
                st.markdown("### 📊 Resultados da Consulta")
                st.info("Consulta concluída anteriormente")
    
    # Etapa 4 - Processamento dos Dados
    elif etapa_atual >= 4:
        st.markdown("## ⚙️ Etapa 4 - Processamento dos Dados")
        
        if st.session_state.consulta_concluida and st.session_state.relatorios_baixados:
            # Resumo dos dados coletados
            st.markdown("### 📊 Dados Coletados")
            
            total_registros = 0
            for curso, data in st.session_state.relatorios_baixados.items():
                if 'df' in data and data['status'] == 'sucesso':
                    total_registros += len(data['df'])
            
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
