# app.py - VERSÃO COM ETAPA 3 INICIADA
import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import json
import io
import os

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
if 'relatorios_baixados' not in st.session_state:
    st.session_state.relatorios_baixados = {}
if 'consulta_concluida' not in st.session_state:
    st.session_state.consulta_concluida = False
if 'dados_processados' not in st.session_state:
    st.session_state.dados_processados = {}

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
        if sem1 < sem2:
            return -1
        elif sem1 > sem2:
            return 1
        else:
            return 0

# Funções para ETAPA 3 - Consulta de Relatórios
def buscar_cursos_por_localidade(session, localidade_id):
    """Busca cursos disponíveis para uma localidade"""
    try:
        url = f"https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos/cursos?localidade={localidade_id}"
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
        st.error(f"Erro ao buscar cursos: {str(e)}")
    
    return []

def buscar_desdobramentos_por_curso(session, curso_id):
    """Busca desdobramentos disponíveis para um curso"""
    try:
        url = f"https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos/desdobramentos?curso={curso_id}"
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
        st.error(f"Erro ao buscar desdobramentos: {str(e)}")
    
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
        url = "https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos',
            'Origin': 'https://app.uff.br',
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
            stream=True
        )
        
        if response.status_code == 200:
            # Verificar se é um arquivo XLSX
            content_type = response.headers.get('content-type', '')
            content_disposition = response.headers.get('content-disposition', '')
            
            if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type or \
               'xlsx' in content_type or \
               '.xlsx' in content_disposition.lower():
                
                # Ler conteúdo
                content = response.content
                
                # Tentar carregar como DataFrame
                try:
                    df = pd.read_excel(io.BytesIO(content))
                    return df, content
                except Exception as e:
                    # Se não conseguir ler como Excel, retornar conteúdo bruto
                    return None, content
            else:
                # Pode ser HTML em caso de erro
                return None, response.content
        
        return None, None
        
    except Exception as e:
        st.error(f"Erro ao gerar relatório: {str(e)}")
        return None, None

def processar_consulta_relatorios():
    """Processa a consulta de relatórios para todos os cursos selecionados"""
    
    st.session_state.relatorios_baixados = {}
    st.session_state.dados_processados = {}
    
    # Configurações base
    config = {
        'localidade': '1',  # Niterói
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
    
    # Para cada curso selecionado
    cursos = st.session_state.selected_cursos
    total_cursos = len(cursos)
    
    for idx, curso in enumerate(cursos):
        curso_nome = curso['nome']
        codigo_curso = curso['codigo']
        desdobramento_texto = curso['desdobramento']
        
        # Atualizar status
        status_text.text(f"Consultando curso: {curso_nome}...")
        progress_bar.progress((idx) / total_cursos)
        
        try:
            # 1. Buscar cursos disponíveis para Niterói
            status_text.text(f"Buscando cursos disponíveis para {curso_nome}...")
            cursos_disponiveis = buscar_cursos_por_localidade(
                st.session_state.session, 
                config['localidade']
            )
            
            if not cursos_disponiveis:
                status_cursos[curso_nome] = {
                    'status': 'erro',
                    'mensagem': 'Nenhum curso encontrado para Niterói'
                }
                continue
            
            # 2. Encontrar o curso específico
            curso_encontrado = None
            for curso_disp in cursos_disponiveis:
                if codigo_curso in curso_disp['text'] or curso_nome.lower() in curso_disp['text'].lower():
                    curso_encontrado = curso_disp
                    break
            
            if not curso_encontrado:
                status_cursos[curso_nome] = {
                    'status': 'erro', 
                    'mensagem': f'Curso {curso_nome} não encontrado no sistema'
                }
                continue
            
            # 3. Buscar desdobramentos para o curso
            status_text.text(f"Buscando desdobramentos para {curso_nome}...")
            desdobramentos = buscar_desdobramentos_por_curso(
                st.session_state.session,
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
            df_relatorio, conteudo = gerar_relatorio_xlsx(
                st.session_state.session,
                form_data
            )
            
            if df_relatorio is not None:
                # Armazenar DataFrame
                st.session_state.relatorios_baixados[curso_nome] = {
                    'df': df_relatorio,
                    'conteudo': conteudo,
                    'curso_id': curso_encontrado['value'],
                    'desdobramento_id': desdobramento_encontrado['value'],
                    'status': 'sucesso',
                    'linhas': len(df_relatorio)
                }
                
                status_cursos[curso_nome] = {
                    'status': 'sucesso',
                    'mensagem': f'Relatório com {len(df_relatorio)} linhas baixado'
                }
                
                # Pré-processar dados
                dados_processados = preprocessar_dados_relatorio(df_relatorio)
                st.session_state.dados_processados[curso_nome] = dados_processados
                
            else:
                status_cursos[curso_nome] = {
                    'status': 'erro',
                    'mensagem': 'Falha ao gerar relatório'
                }
                
        except Exception as e:
            status_cursos[curso_nome] = {
                'status': 'erro',
                'mensagem': f'Erro: {str(e)}'
            }
        
        # Pequena pausa entre requisições
        time.sleep(1)
    
    # Finalizar barra de progresso
    progress_bar.progress(1.0)
    status_text.text("Consulta concluída!")
    
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

# Interface de seleção de período - AJUSTADA PARA COMEÇAR EM 2013
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
            return False
    
    with col2:
        st.subheader("🎯 Seleção de Períodos")
        
        # Períodos disponíveis
        periodos = form_params.get('periodos', [])
        
        if not periodos:
            st.error("Nenhum período disponível")
            return False
        
        # Filtrar apenas períodos válidos (remover "--- Todos ---")
        periodos_validos = [p for p in periodos if p['text'] != '--- Todos ---']
        
        # Converter para lista de textos
        periodo_textos = [p['text'] for p in periodos_validos]
        periodo_valores = {p['text']: p['value'] for p in periodos_validos}
        
        if not periodo_textos:
            st.error("Períodos não disponíveis")
            return False
        
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
        
        # Validação
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
        
        # Validar intervalo
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

# Interface da Etapa 3 - Consulta de Relatórios
def etapa_consulta_relatorios():
    """Interface para consulta de relatórios"""
    
    st.markdown("## 🔍 Etapa 3 - Consulta de Relatórios")
    
    # Verificar se há configuração salva
    if not st.session_state.selected_periodos or not st.session_state.selected_cursos:
        st.error("Configure primeiro os períodos e cursos na Etapa 2")
        return False
    
    # Mostrar resumo da configuração
    with st.expander("📋 Configuração Atual", expanded=True):
        periodos = st.session_state.selected_periodos
        cursos = st.session_state.selected_cursos
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Período:** {periodos['inicial']} a {periodos['final']}")
            st.markdown(f"**Localidade:** Niterói")
        
        with col2:
            st.markdown("**Cursos:**")
            for curso in cursos:
                st.markdown(f"- {curso['nome']}")
    
    st.markdown("---")
    
    # Botão para iniciar consulta
    if not st.session_state.consulta_concluida:
        st.markdown("### ⚙️ Preparar Consulta")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Iniciar Consulta de Relatórios", type="primary", use_container_width=True):
                with st.spinner("Iniciando consulta..."):
                    # Executar consulta
                    resultados = processar_consulta_relatorios()
                    st.session_state.consulta_concluida = True
                    st.rerun()
        
        with col2:
            if st.button("🔄 Voltar para Configuração", type="secondary", use_container_width=True):
                st.session_state.selected_periodos = {}
                st.session_state.selected_cursos = []
                st.rerun()
    
    # Mostrar resultados da consulta
    if st.session_state.consulta_concluida:
        st.markdown("### 📊 Resultados da Consulta")
        
        # Resumo geral
        total_cursos = len(st.session_state.selected_cursos)
        relatorios_sucesso = sum(1 for curso in st.session_state.selected_cursos 
                               if curso['nome'] in st.session_state.relatorios_baixados and 
                               st.session_state.relatorios_baixados[curso['nome']]['status'] == 'sucesso')
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Cursos Configurados", total_cursos)
        with col_s2:
            st.metric("Relatórios Baixados", relatorios_sucesso)
        with col_s3:
            st.metric("Status", "✅ Concluído" if relatorios_sucesso == total_cursos else "⚠️ Parcial")
        
        # Detalhes por curso
        st.markdown("#### 📋 Detalhes por Curso")
        
        for curso in st.session_state.selected_cursos:
            curso_nome = curso['nome']
            
            with st.expander(f"📁 {curso_nome}", expanded=True):
                if curso_nome in st.session_state.relatorios_baixados:
                    dados = st.session_state.relatorios_baixados[curso_nome]
                    
                    if dados['status'] == 'sucesso':
                        st.success("✅ Relatório baixado com sucesso")
                        
                        # Informações do DataFrame
                        df = dados['df']
                        st.markdown(f"**Total de registros:** {len(df)}")
                        st.markdown(f"**Colunas disponíveis:** {len(df.columns)}")
                        
                        # Pré-visualização dos dados
                        st.markdown("**Pré-visualização dos dados:**")
                        st.dataframe(df.head(), use_container_width=True)
                        
                        # Colunas identificadas
                        if curso_nome in st.session_state.dados_processados:
                            proc = st.session_state.dados_processados[curso_nome]
                            st.markdown("**Colunas identificadas:**")
                            for chave, coluna in proc['colunas_mapeadas'].items():
                                st.markdown(f"- `{chave}`: {coluna}")
                        
                        # Botão para download
                        col_d1, col_d2 = st.columns(2)
                        with col_d1:
                            # Criar DataFrame para download
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download CSV",
                                data=csv,
                                file_name=f"relatorio_{curso_nome.replace(' ', '_').lower()}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        
                        with col_d2:
                            # Botão para visualizar mais
                            if st.button("📊 Ver mais dados", key=f"ver_mais_{curso_nome}", use_container_width=True):
                                st.session_state[f'ver_detalhes_{curso_nome}'] = True
                        
                        # Mostrar detalhes expandidos se solicitado
                        if st.session_state.get(f'ver_detalhes_{curso_nome}', False):
                            st.markdown("**Estatísticas das colunas:**")
                            st.write(df.describe(include='all'))
                            
                            st.markdown("**Tipos de dados:**")
                            tipos = pd.DataFrame(df.dtypes, columns=['Tipo'])
                            st.dataframe(tipos)
                    
                    else:
                        st.error(f"❌ Falha: {dados.get('mensagem', 'Erro desconhecido')}")
                else:
                    st.warning("⏳ Relatório não disponível")
        
        # Botões de controle
        st.markdown("---")
        col_b1, col_b2, col_b3 = st.columns(3)
        
        with col_b1:
            if st.button("🔄 Refazer Consulta", type="secondary", use_container_width=True):
                st.session_state.consulta_concluida = False
                st.session_state.relatorios_baixados = {}
                st.session_state.dados_processados = {}
                st.rerun()
        
        with col_b2:
            if st.button("⚙️ Alterar Configuração", type="secondary", use_container_width=True):
                st.session_state.selected_periodos = {}
                st.session_state.selected_cursos = []
                st.session_state.consulta_concluida = False
                st.session_state.relatorios_baixados = {}
                st.session_state.dados_processados = {}
                st.rerun()
        
        with col_b3:
            if relatorios_sucesso > 0:
                if st.button("🚀 Avançar para Processamento", type="primary", use_container_width=True):
                    st.session_state.etapa_atual = 4
                    st.success("Pronto para Etapa 4 - Processamento dos Dados!")
                    st.rerun()
    
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
        
        # Progresso das etapas
        st.markdown("### 📋 Progresso do Processo")
        
        # Definir etapa atual
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
        
        # Conteúdo principal baseado na etapa atual
        if not st.session_state.selected_periodos:
            etapa_selecao_periodo()
        elif not st.session_state.consulta_concluida:
            etapa_consulta_relatorios()
        else:
            # Preparar para Etapa 4
            st.markdown("## ⚙️ Etapa 4 - Processamento dos Dados")
            
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
                    st.session_state.consulta_concluida = False
                    st.rerun()
            
            with col_b3:
                if st.button("⚙️ Iniciar Processamento", type="primary", use_container_width=True):
                    # Aqui iniciará a Etapa 4
                    st.info("Iniciando processamento dos dados...")
                    # Placeholder para processamento real
                    
            # Mostrar dados coletados se solicitado
            if st.session_state.get('mostrar_dados_coletados', False):
                st.markdown("---")
                st.markdown("### 📋 Dados Coletados por Curso")
                
                for curso_nome, dados in st.session_state.relatorios_baixados.items():
                    if dados['status'] == 'sucesso':
                        with st.expander(f"📊 {curso_nome} - {len(dados['df'])} registros"):
                            st.dataframe(dados['df'].head(10), use_container_width=True)
                            
                            # Estatísticas básicas
                            st.markdown(f"**Colunas:** {', '.join(dados['df'].columns.tolist()[:5])}...")
                            if len(dados['df'].columns) > 5:
                                st.markdown(f"**Total de colunas:** {len(dados['df'].columns)}")

if __name__ == "__main__":
    main()
