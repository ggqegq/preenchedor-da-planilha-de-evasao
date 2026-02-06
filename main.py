# main.py - ATUALIZADO
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
from gerador_relatorios import GeradorRelatorios, ProcessadorDadosRelatorios

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
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = None
if 'username' not in st.session_state:
    st.session_state.username = ''
if 'form_params' not in st.session_state:
    st.session_state.form_params = None
if 'selected_cursos' not in st.session_state:
    st.session_state.selected_cursos = []
if 'selected_periodos' not in st.session_state:
    st.session_state.selected_periodos = {}
if 'formas_ingresso_selecionadas' not in st.session_state:
    st.session_state.formas_ingresso_selecionadas = []
if 'relatorios_baixados' not in st.session_state:
    st.session_state.relatorios_baixados = {}
if 'consulta_concluida' not in st.session_state:
    st.session_state.consulta_concluida = False
if 'dados_processados' not in st.session_state:
    st.session_state.dados_processados = {}
if 'etapa_atual' not in st.session_state:
    st.session_state.etapa_atual = 2
if 'localidade_selecionada' not in st.session_state:
    st.session_state.localidade_selecionada = {'value': '1', 'text': 'Niterói'}
if 'mostrar_dados_coletados' not in st.session_state:
    st.session_state.mostrar_dados_coletados = False
if 'consulta_em_andamento' not in st.session_state:
    st.session_state.consulta_em_andamento = False
if 'gerador' not in st.session_state:
    st.session_state.gerador = None
if 'resultados_geracao' not in st.session_state:
    st.session_state.resultados_geracao = {}
if 'dados_consolidados' not in st.session_state:
    st.session_state.dados_consolidados = None
if 'planilha_gerada' not in st.session_state:
    st.session_state.planilha_gerada = False
if 'caminho_planilha' not in st.session_state:
    st.session_state.caminho_planilha = ''

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

def converter_periodo_para_valor(periodo_texto):
    """Converte texto de período para valor do sistema"""
    ano, semestre = parse_periodo_texto(periodo_texto)
    if ano and semestre:
        return f"{ano}{semestre}"
    return None

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
            st.session_state.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Progresso das etapas
    st.markdown("### 📋 Progresso do Processo")
    
    # Determinar etapa atual
    if not st.session_state.selected_periodos:
        st.session_state.etapa_atual = 2
    elif not st.session_state.consulta_concluida:
        st.session_state.etapa_atual = 3
    elif st.session_state.consulta_concluida and not st.session_state.planilha_gerada:
        st.session_state.etapa_atual = 4
    else:
        st.session_state.etapa_atual = 5
    
    etapa_atual = st.session_state.etapa_atual
    
    col_e1, col_e2, col_e3, col_e4, col_e5 = st.columns(5)
    
    etapas = [
        ("1. Login", 1, True),
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
    
    # ========== ETAPA 2 - Seleção de Período e Cursos ==========
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
                    st.stop()
                
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
                else:
                    st.error("Formas de ingresso SISU não encontradas")
                    st.stop()
            
            with col2:
                st.subheader("🎯 Seleção de Períodos")
                
                # Períodos disponíveis
                periodos = form_params.get('periodos', [])
                
                if not periodos:
                    st.error("Nenhum período disponível")
                    st.stop()
                else:
                    # Filtrar apenas períodos válidos (remover "--- Todos ---")
                    periodos_validos = [p for p in periodos if p['text'] != '--- Todos ---']
                    
                    # Converter para lista de textos
                    periodo_textos = [p['text'] for p in periodos_validos]
                    periodo_valores = {p['text']: p['value'] for p in periodos_validos}
                    
                    if not periodo_textos:
                        st.error("Períodos não disponíveis")
                        st.stop()
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
                if not formas_valores or len(formas_valores) != 2:
                    st.error("As duas formas de ingresso SISU devem estar selecionadas")
                elif not cursos_selecionados_objetos:
                    st.error("Selecione pelo menos um curso")
                elif not periodo_inicial_texto or not periodo_final_texto:
                    st.error("Selecione os períodos")
                else:
                    # Validar intervalo
                    resultado = comparar_periodos(periodo_inicial_texto, periodo_final_texto)
                    if resultado == 1:  # Inicial > Final (inválido)
                        st.error("Período inicial não pode ser posterior ao final")
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
                            'text': localidade_niteroi['text'],
                            'value': localidade_value
                        }
                        
                        st.success("🎉 Configuração salva com sucesso!")
                        st.session_state.etapa_atual = 3
                        time.sleep(1)
                        st.rerun()
    
    # ========== ETAPA 3 - Consulta de Relatórios ==========
    elif etapa_atual == 3:
        st.markdown("## 🔍 Etapa 3 - Geração de Relatórios")
        
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
                    
                    # Calcular total de relatórios
                    periodo_inicial_valor = converter_periodo_para_valor(periodos['inicial'])
                    periodo_final_valor = converter_periodo_para_valor(periodos['final'])
                    
                    if periodo_inicial_valor and periodo_final_valor:
                        # Gerar lista de períodos
                        gerador = GeradorRelatorios(st.session_state.authenticator.session)
                        periodos_lista = gerador.processar_periodos_intervalo(
                            periodo_inicial_valor, 
                            periodo_final_valor
                        )
                        
                        total_relatorios = len(cursos) * len(periodos_lista)
                        st.markdown(f"**Total de relatórios:** {total_relatorios}")
                
                with col2:
                    st.markdown("**Cursos:**")
                    for curso in cursos:
                        st.markdown(f"- {curso['nome']} ({curso['tipo']})")
            
            st.markdown("---")
            
            if not st.session_state.consulta_concluida:
                st.markdown("### ⚙️ Gerar Relatórios")
                
                # Informações sobre o processo
                st.info("""
                **O que acontecerá na geração:**
                1. Para cada curso selecionado, o sistema irá gerar relatórios para cada período
                2. **Importante:** A geração pode levar vários minutos por relatório
                3. O sistema monitorará automaticamente o processamento de cada relatório
                4. Quando todos estiverem prontos, fará o download dos arquivos XLSX
                5. Após o download, processará os dados para gerar estatísticas
                """)
                
                if st.button("🚀 Iniciar Geração de Relatórios", type="primary", use_container_width=True):
                    # Inicializar gerador
                    st.session_state.gerador = GeradorRelatorios(st.session_state.authenticator.session)
                    
                    # Obter cursos predefinidos
                    cursos_config = []
                    for curso_obj in st.session_state.selected_cursos:
                        # Mapear curso selecionado para configuração do gerador
                        if 'Licenciatura' in curso_obj['nome']:
                            cursos_config.append({
                                'nome': curso_obj['nome'],
                                'codigo_curso': '12700',
                                'codigo_desdobramento': '12700',
                                'tipo': 'Licenciatura'
                            })
                        elif 'Bacharelado' in curso_obj['nome'] and 'Industrial' not in curso_obj['nome']:
                            cursos_config.append({
                                'nome': curso_obj['nome'],
                                'codigo_curso': '12700',
                                'codigo_desdobramento': '312700',
                                'tipo': 'Bacharelado'
                            })
                        elif 'Industrial' in curso_obj['nome']:
                            cursos_config.append({
                                'nome': curso_obj['nome'],
                                'codigo_curso': '12709',
                                'codigo_desdobramento': '12709',
                                'tipo': 'Bacharelado'
                            })
                    
                    # Gerar lista de períodos
                    periodo_inicial_valor = converter_periodo_para_valor(periodos['inicial'])
                    periodo_final_valor = converter_periodo_para_valor(periodos['final'])
                    
                    periodos_lista = st.session_state.gerador.processar_periodos_intervalo(
                        periodo_inicial_valor, 
                        periodo_final_valor
                    )
                    
                    # Criar placeholder para progresso
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Gerar relatórios em lote
                    total_gerar = len(cursos_config) * len(periodos_lista)
                    gerados = 0
                    
                    for curso in cursos_config:
                        status_text.text(f"Gerando relatórios para: {curso['nome']}")
                        
                        for periodo in periodos_lista:
                            # Atualizar progresso
                            progresso = gerados / total_gerar
                            progress_bar.progress(progresso)
                            
                            status_text.text(f"Curso: {curso['nome']} - Período: {periodo[:4]}/{periodo[4:]}")
                            
                            # Gerar relatório individual
                            resultado = st.session_state.gerador.gerar_relatorio_individual(
                                curso, 
                                periodo, 
                                st.session_state.gerador._determinar_forma_ingresso(periodo)
                            )
                            
                            # Armazenar resultado
                            if curso['nome'] not in st.session_state.resultados_geracao:
                                st.session_state.resultados_geracao[curso['nome']] = []
                            
                            st.session_state.resultados_geracao[curso['nome']].append(resultado)
                            gerados += 1
                            
                            time.sleep(2)  # Aguardar entre requisições
                    
                    # Finalizar
                    progress_bar.progress(1.0)
                    status_text.text("✅ Geração de relatórios concluída!")
                    
                    st.session_state.consulta_concluida = True
                    time.sleep(2)
                    st.rerun()
                
                # Botão para refazer configuração
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.selected_periodos = {}
                    st.session_state.selected_cursos = []
                    st.session_state.etapa_atual = 2
                    st.rerun()
            
            # Se consulta foi concluída
            elif st.session_state.consulta_concluida:
                st.markdown("### 📊 Resultados da Geração")
                
                if st.session_state.resultados_geracao:
                    st.success("✅ Geração de relatórios concluída!")
                    
                    # Mostrar resultados
                    totais = {
                        'sucesso': 0,
                        'erro': 0,
                        'total': 0
                    }
                    
                    for curso_nome, resultados_curso in st.session_state.resultados_geracao.items():
                        st.markdown(f"**{curso_nome}:**")
                        
                        for resultado in resultados_curso:
                            periodo_display = resultado.get('periodo', 'Desconhecido')
                            if len(periodo_display) == 5:
                                periodo_display = f"{periodo_display[:4]}/{periodo_display[4:]}"
                            
                            if resultado.get('success'):
                                st.info(f"  ✅ Período {periodo_display}: Relatório gerado com sucesso")
                                totais['sucesso'] += 1
                            else:
                                st.error(f"  ❌ Período {periodo_display}: {resultado.get('error', 'Erro desconhecido')}")
                                totais['erro'] += 1
                            
                            totais['total'] += 1
                    
                    # Resumo
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Relatórios Gerados", totais['sucesso'])
                    with col2:
                        st.metric("Relatórios com Erro", totais['erro'])
                    with col3:
                        percentual = (totais['sucesso'] / totais['total'] * 100) if totais['total'] > 0 else 0
                        st.metric("Taxa de Sucesso", f"{percentual:.1f}%")
                    
                    # Botão para avançar
                    if st.button("📊 Processar Dados e Gerar Estatísticas", type="primary", use_container_width=True):
                        st.session_state.etapa_atual = 4
                        st.rerun()
                    
                    # Botão para refazer
                    if st.button("🔄 Gerar Novamente", type="secondary", use_container_width=True):
                        st.session_state.consulta_concluida = False
                        st.session_state.resultados_geracao = {}
                        st.rerun()
                else:
                    st.warning("Geração concluída, mas nenhum resultado encontrado.")
    
    # ========== ETAPA 4 - Processamento dos Dados ==========
    elif etapa_atual == 4:
        st.markdown("## ⚙️ Etapa 4 - Processamento dos Dados")
        
        if not st.session_state.resultados_geracao:
            st.error("Nenhum dado para processar. Volte para a Etapa 3.")
            if st.button("🔙 Voltar para Etapa 3"):
                st.session_state.etapa_atual = 3
                st.rerun()
        else:
            st.info("""
            **Processamento em andamento:**
            1. **Lendo relatórios** baixados
            2. **Extraindo dados** de matrículas, cancelamentos e situações
            3. **Classificando** por modalidade de ingresso (Ampla Concorrência / Ações Afirmativas)
            4. **Calculando percentuais** e estatísticas
            5. **Gerando planilha consolidada** com todas as informações
            """)
            
            if st.button("▶️ Iniciar Processamento", type="primary", use_container_width=True):
                with st.spinner("Processando dados dos relatórios..."):
                    # Processar dados
                    processador = ProcessadorDadosRelatorios()
                    
                    # Consolidar dados de todos os relatórios
                    st.session_state.dados_consolidados = processador.consolidar_dados_todos_relatorios(
                        st.session_state.resultados_geracao
                    )
                    
                    # Gerar planilha
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    caminho_planilha = os.path.join(PASTA_RELATORIOS, f"estatisticas_evasao_{timestamp}.xlsx")
                    
                    sucesso = processador.gerar_planilha_consolidada(
                        st.session_state.dados_consolidados,
                        caminho_planilha
                    )
                    
                    if sucesso:
                        st.session_state.planilha_gerada = True
                        st.session_state.caminho_planilha = caminho_planilha
                        st.session_state.etapa_atual = 5
                        st.success("✅ Processamento concluído com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Erro ao gerar planilha consolidada.")
            
            if st.button("🔙 Voltar para Etapa 3", type="secondary", use_container_width=True):
                st.session_state.etapa_atual = 3
                st.rerun()
    
    # ========== ETAPA 5 - Planilha Final ==========
    elif etapa_atual >= 5:
        st.markdown("## 📊 Etapa 5 - Planilha Consolidada")
        
        if st.session_state.planilha_gerada and st.session_state.caminho_planilha:
            st.success("✅ Planilha gerada com sucesso!")
            
            # Mostrar resumo dos dados
            if st.session_state.dados_consolidados:
                resumo = st.session_state.dados_consolidados.get('resumo_geral', {})
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de Cursos", resumo.get('total_cursos', 0))
                with col2:
                    st.metric("Total de Períodos", resumo.get('total_periodos', 0))
                with col3:
                    st.metric("Total de Matrículas", resumo.get('total_matriculas', 0))
                with col4:
                    st.metric("Total Cancelamentos", resumo.get('total_cancelamentos', 0))
                
                # Botão para download
                with open(st.session_state.caminho_planilha, 'rb') as f:
                    st.download_button(
                        label="📥 Baixar Planilha Consolidada",
                        data=f,
                        file_name=os.path.basename(st.session_state.caminho_planilha),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                
                # Mostrar preview da planilha
                with st.expander("🔍 Visualizar Estrutura da Planilha", expanded=False):
                    try:
                        # Ler a planilha para mostrar abas
                        xls = pd.ExcelFile(st.session_state.caminho_planilha)
                        st.info(f"**Abas disponíveis:** {', '.join(xls.sheet_names)}")
                        
                        # Mostrar preview da primeira aba
                        df_preview = pd.read_excel(st.session_state.caminho_planilha, sheet_name='RESUMO GERAL')
                        st.dataframe(df_preview, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Não foi possível visualizar a planilha: {str(e)}")
            
            # Botões de controle
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Processar Novamente", type="secondary", use_container_width=True):
                    st.session_state.planilha_gerada = False
                    st.session_state.caminho_planilha = ''
                    st.session_state.etapa_atual = 4
                    st.rerun()
            
            with col2:
                if st.button("🏁 Novo Processo", type="primary", use_container_width=True):
                    # Resetar apenas dados do processo atual
                    st.session_state.selected_periodos = {}
                    st.session_state.selected_cursos = []
                    st.session_state.consulta_concluida = False
                    st.session_state.resultados_geracao = {}
                    st.session_state.dados_consolidados = None
                    st.session_state.planilha_gerada = False
                    st.session_state.caminho_planilha = ''
                    st.session_state.etapa_atual = 2
                    st.rerun()
        else:
            st.warning("Planilha ainda não foi gerada.")
            if st.button("🔙 Voltar para Etapa 4"):
                st.session_state.etapa_atual = 4
                st.rerun()

# Rodapé
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col1:
    st.caption(f"🕒 {datetime.now().strftime('%H:%M:%S')}")
with footer_col2:
    st.caption("📊 Departamento de Química - UFF")
with footer_col3:
    st.caption("🔒 Sistema de automação seguro")

# Script de inicialização
if __name__ == "__main__":
    # Criar pastas necessárias
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
