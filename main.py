# main.py - CÓDIGO COMPLETO COM TODAS AS FUNÇÕES
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

# ========== INICIALIZAÇÃO DO ESTADO DA SESSÃO ==========
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
if 'resultados_consulta' not in st.session_state:
    st.session_state.resultados_consulta = {}
if 'mostrar_detalhes' not in st.session_state:
    st.session_state.mostrar_detalhes = False

# ========== FUNÇÕES AUXILIARES ==========

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

# ========== FUNÇÕES PARA CONSULTA DE RELATÓRIOS ==========

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
        
        logger.info(f"Enviando formulário para: {url}")
        logger.info(f"Dados do formulário: {form_data}")
        
        response = session.post(
            url,
            data=form_data,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )
        
        logger.info(f"Resposta recebida. Status: {response.status_code}")
        logger.info(f"URL final: {response.url}")
        
        if response.status_code == 200:
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url and 'listagens_alunos' not in response.url:
                # Extrair ID do relatório da URL
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
            content_disposition = response.headers.get('content-disposition', '')
            
            logger.info(f"Content-Type: {content_type}")
            logger.info(f"Content-Disposition: {content_disposition}")
            
            if ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type or 
                'xlsx' in content_type.lower() or 
                'excel' in content_type.lower() or
                '.xlsx' in content_disposition.lower()):
                
                # Retornar conteúdo do arquivo
                return {
                    'success': True,
                    'conteudo': response.content,
                    'diretamente': True,
                    'tamanho': len(response.content)
                }
            
            # Verificar se há mensagem de erro
            soup = BeautifulSoup(response.text, 'html.parser')
            alert_error = soup.find('div', class_='alert-error') or soup.find('div', class_='alert-danger')
            if alert_error:
                error_msg = alert_error.get_text(strip=True)[:200]
                return {
                    'success': False,
                    'error': f"Erro no servidor: {error_msg}"
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

def verificar_status_relatorio(session, relatorio_id):
    """Verifica o status de processamento de um relatório"""
    try:
        url = f"{APLICACAO_URL}/relatorios/{relatorio_id}"
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Verificar se está pronto
            if 'O relatório está pronto!' in response.text or 'Download' in response.text:
                # Procurar link de download
                for link in soup.find_all('a', href=True):
                    if 'download' in link['href'].lower() or '.xlsx' in link['href'].lower():
                        download_url = link['href']
                        if not download_url.startswith('http'):
                            download_url = f"{APLICACAO_URL}{download_url}"
                        
                        return {
                            'success': True,
                            'pronto': True,
                            'download_url': download_url
                        }
            
            # Verificar se ainda está processando
            if 'Processando...' in response.text or 'Aguardando' in response.text:
                return {
                    'success': True,
                    'pronto': False,
                    'status': 'processando'
                }
            
            # Verificar se há erro
            if 'Erro' in response.text or 'error' in response.text.lower():
                return {
                    'success': False,
                    'error': 'Erro detectado no processamento'
                }
        
        return {
            'success': True,
            'pronto': False,
            'status': 'desconhecido'
        }
            
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def baixar_relatorio_xlsx(session, download_url):
    """Baixa o relatório XLSX"""
    try:
        logger.info(f"Baixando relatório de: {download_url}")
        
        response = session.get(download_url, timeout=30)
        
        if response.status_code == 200:
            # Criar pasta se não existir
            os.makedirs(PASTA_RELATORIOS, exist_ok=True)
            
            # Gerar nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_arquivo = f"relatorio_{timestamp}.xlsx"
            caminho_arquivo = os.path.join(PASTA_RELATORIOS, nome_arquivo)
            
            with open(caminho_arquivo, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Arquivo salvo: {caminho_arquivo} ({len(response.content)} bytes)")
            
            # Tentar ler como DataFrame para verificação
            try:
                df = pd.read_excel(caminho_arquivo, nrows=5)
                return {
                    'success': True,
                    'caminho': caminho_arquivo,
                    'df': df,
                    'tamanho': len(response.content),
                    'amostra': df.head(3) if not df.empty else None
                }
            except Exception as e:
                logger.warning(f"Não foi possível ler como Excel: {str(e)}")
                return {
                    'success': True,
                    'caminho': caminho_arquivo,
                    'df': None,
                    'tamanho': len(response.content),
                    'erro_leitura': str(e)
                }
        else:
            return {
                'success': False,
                'error': f"Erro HTTP {response.status_code} ao baixar"
            }
            
    except Exception as e:
        logger.error(f"Erro ao baixar relatório: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def processar_consulta_completa():
    """Processa a consulta completa de relatórios"""
    
    # Inicializar resultados
    resultados = {}
    
    # Obter configurações
    localidade_id = st.session_state.localidade_selecionada['value']
    formas_ingresso = st.session_state.formas_ingresso_selecionadas
    periodo_inicial = st.session_state.selected_periodos['valor_inicial']
    csrf_token = st.session_state.form_params['csrf_token']
    
    # Para cada curso selecionado
    cursos = st.session_state.selected_cursos
    total_cursos = len(cursos)
    
    # Criar interface de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()
    
    with log_container:
        for idx, curso in enumerate(cursos):
            curso_nome = curso['nome']
            codigo_curso = curso['codigo']
            desdobramento_texto = curso['desdobramento']
            
            # Atualizar progresso
            progresso_atual = idx / total_cursos
            progress_bar.progress(progresso_atual)
            status_text.text(f"Processando: {curso_nome} ({idx+1}/{total_cursos})")
            
            st.write(f"**{curso_nome}**")
            
            try:
                # 1. Buscar cursos disponíveis
                st.write("🔍 Buscando cursos disponíveis...")
                cursos_disponiveis = buscar_cursos_por_localidade(
                    st.session_state.authenticator.session, 
                    localidade_id
                )
                
                if not cursos_disponiveis:
                    resultados[curso_nome] = {
                        'status': 'erro',
                        'mensagem': 'Nenhum curso encontrado para a localidade'
                    }
                    st.error("❌ Nenhum curso encontrado")
                    continue
                
                # 2. Encontrar curso específico
                curso_encontrado = None
                for curso_disp in cursos_disponiveis:
                    if codigo_curso in curso_disp['text'] or curso_nome.lower() in curso_disp['text'].lower():
                        curso_encontrado = curso_disp
                        break
                
                if not curso_encontrado:
                    resultados[curso_nome] = {
                        'status': 'erro',
                        'mensagem': f'Curso não encontrado no sistema'
                    }
                    st.error("❌ Curso não encontrado no sistema")
                    # Mostrar opções disponíveis para debug
                    with st.expander("Cursos disponíveis"):
                        for c in cursos_disponiveis[:10]:
                            st.write(f"- {c['text']}")
                    continue
                
                st.success(f"✅ Curso encontrado: {curso_encontrado['text']}")
                
                # 3. Buscar desdobramentos
                st.write("🔍 Buscando desdobramentos...")
                desdobramentos = buscar_desdobramentos_por_curso(
                    st.session_state.authenticator.session,
                    curso_encontrado['value']
                )
                
                if not desdobramentos:
                    resultados[curso_nome] = {
                        'status': 'erro',
                        'mensagem': 'Nenhum desdobramento encontrado'
                    }
                    st.error("❌ Nenhum desdobramento encontrado")
                    continue
                
                # 4. Encontrar desdobramento específico
                desdobramento_encontrado = encontrar_desdobramento_curso(
                    desdobramentos,
                    desdobramento_texto
                )
                
                if not desdobramento_encontrado:
                    desdobramento_encontrado = desdobramentos[0]
                    st.warning(f"⚠️ Usando desdobramento alternativo: {desdobramento_encontrado['text']}")
                else:
                    st.success(f"✅ Desdobramento encontrado: {desdobramento_encontrado['text']}")
                
                # 5. Preparar dados do formulário
                form_data = {
                    'authenticity_token': csrf_token,
                    'utf8': '✓',
                    'idlocalidade': localidade_id,
                    'idcurso': curso_encontrado['value'],
                    'iddesdobramento': desdobramento_encontrado['value'],
                    'idturno': '',  # Todos
                    'idstatusaluno': '',  # Todos
                    'idsituacaoaluno': '',  # Todos
                    'idformaingresso': formas_ingresso[0],  # Primeiro SISU
                    'idacaoafirmativa': '',  # Todos
                    'anosem_ingresso': periodo_inicial,
                    'anosem_desvinculacao': ''  # Todos
                }
                
                # 6. Gerar relatório
                st.write("🚀 Gerando relatório...")
                resultado_geracao = gerar_relatorio_xlsx(
                    st.session_state.authenticator.session,
                    form_data
                )
                
                if not resultado_geracao['success']:
                    resultados[curso_nome] = {
                        'status': 'erro',
                        'mensagem': f"Erro na geração: {resultado_geracao.get('error', 'Erro desconhecido')}"
                    }
                    st.error(f"❌ Erro na geração: {resultado_geracao.get('error')}")
                    continue
                
                # 7. Processar resultado
                if resultado_geracao.get('diretamente'):
                    # Download direto
                    st.write("📥 Download direto do arquivo...")
                    
                    # Salvar arquivo
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    nome_arquivo = f"relatorio_{curso_nome.replace(' ', '_')}_{timestamp}.xlsx"
                    caminho_arquivo = os.path.join(PASTA_RELATORIOS, nome_arquivo)
                    
                    with open(caminho_arquivo, 'wb') as f:
                        f.write(resultado_geracao['conteudo'])
                    
                    st.success(f"✅ Arquivo salvo: {nome_arquivo} ({resultado_geracao.get('tamanho', 0)} bytes)")
                    
                    # Tentar ler como DataFrame
                    try:
                        df = pd.read_excel(caminho_arquivo)
                        resultados[curso_nome] = {
                            'status': 'sucesso',
                            'mensagem': f'Relatório baixado ({len(df)} registros)',
                            'caminho': caminho_arquivo,
                            'df': df,
                            'registros': len(df)
                        }
                        st.success(f"✅ {len(df)} registros lidos com sucesso")
                    except Exception as e:
                        resultados[curso_nome] = {
                            'status': 'sucesso',
                            'mensagem': 'Arquivo baixado (não pôde ser lido como Excel)',
                            'caminho': caminho_arquivo
                        }
                        st.warning(f"⚠️ Arquivo baixado mas não pôde ser lido como Excel: {str(e)}")
                
                elif resultado_geracao.get('relatorio_id'):
                    # Relatório assíncrono
                    relatorio_id = resultado_geracao['relatorio_id']
                    st.info(f"📋 Relatório #{relatorio_id} em processamento...")
                    
                    # Monitorar processamento
                    for tentativa in range(30):  # 30 tentativas (5 minutos)
                        st.write(f"⏳ Verificando status... (tentativa {tentativa+1}/30)")
                        
                        resultado_status = verificar_status_relatorio(
                            st.session_state.authenticator.session,
                            relatorio_id
                        )
                        
                        if resultado_status['success'] and resultado_status.get('pronto'):
                            # Baixar relatório
                            st.write("📥 Baixando relatório pronto...")
                            resultado_download = baixar_relatorio_xlsx(
                                st.session_state.authenticator.session,
                                resultado_status['download_url']
                            )
                            
                            if resultado_download['success']:
                                if resultado_download.get('df') is not None:
                                    resultados[curso_nome] = {
                                        'status': 'sucesso',
                                        'mensagem': f'Relatório #{relatorio_id} baixado ({len(resultado_download["df"])} registros)',
                                        'caminho': resultado_download['caminho'],
                                        'df': resultado_download['df'],
                                        'registros': len(resultado_download['df']),
                                        'relatorio_id': relatorio_id
                                    }
                                    st.success(f"✅ {len(resultado_download['df'])} registros baixados com sucesso")
                                else:
                                    resultados[curso_nome] = {
                                        'status': 'sucesso',
                                        'mensagem': f'Arquivo #{relatorio_id} baixado',
                                        'caminho': resultado_download['caminho'],
                                        'relatorio_id': relatorio_id
                                    }
                                    st.success("✅ Arquivo baixado")
                            else:
                                resultados[curso_nome] = {
                                    'status': 'erro',
                                    'mensagem': f"Erro no download: {resultado_download.get('error')}"
                                }
                                st.error(f"❌ Erro no download: {resultado_download.get('error')}")
                            
                            break
                        elif not resultado_status['success']:
                            resultados[curso_nome] = {
                                'status': 'erro',
                                'mensagem': f"Erro ao verificar status: {resultado_status.get('error')}"
                            }
                            st.error(f"❌ Erro ao verificar status: {resultado_status.get('error')}")
                            break
                        
                        # Aguardar antes de verificar novamente
                        time.sleep(10)
                    
                    else:
                        # Timeout
                        resultados[curso_nome] = {
                            'status': 'erro',
                            'mensagem': 'Timeout no processamento do relatório'
                        }
                        st.error("❌ Timeout no processamento")
                
                else:
                    resultados[curso_nome] = {
                        'status': 'erro',
                        'mensagem': 'Formato de resposta inesperado'
                    }
                    st.error("❌ Formato de resposta inesperado")
                
            except Exception as e:
                logger.error(f"Erro processando {curso_nome}: {str(e)}", exc_info=True)
                resultados[curso_nome] = {
                    'status': 'erro',
                    'mensagem': f'Erro: {str(e)}'
                }
                st.error(f"❌ Erro: {str(e)}")
            
            # Separador entre cursos
            st.markdown("---")
            
            # Pequena pausa entre requisições
            time.sleep(2)
    
    # Finalizar progresso
    progress_bar.progress(1.0)
    status_text.text("Consulta concluída!")
    
    return resultados

# ========== INTERFACE PRINCIPAL ==========

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
    else:
        st.session_state.etapa_atual = 4
    
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
                                    'valor_ordenacao': ano * 10 +
                                                                        'valor_ordenacao': ano * 10 + semestre
                                })
                        
                        # Ordenar por ano/semestre (crescente)
                        periodos_com_info.sort(key=lambda x: x['valor_ordenacao'])
                        
                        # Criar lista ordenada de textos
                        periodo_textos_ordenados = [p['texto'] for p in periodos_com_info]
                        
                        # Seleção do período inicial
                        periodo_inicial = st.selectbox(
                            "Período Inicial da Consulta:",
                            options=periodo_textos_ordenados,
                            index=0,  # Primeiro (mais antigo) por padrão
                            help="Selecione o período letivo inicial para a consulta"
                        )
                        
                        # Seleção do período final (opcional)
                        st.markdown("**Período Final (opcional):**")
                        periodo_final = st.selectbox(
                            "Deixe em branco para consultar apenas o período inicial:",
                            options=['--- Consultar apenas período inicial ---'] + periodo_textos_ordenados,
                            index=0,
                            label_visibility='collapsed'
                        )
                        
                        # Botão para alternar entre "Apenas inicial" e "Intervalo"
                        if periodo_final == '--- Consultar apenas período inicial ---':
                            periodo_final = None
                            st.info(f"ℹ️ Consultando apenas: **{periodo_inicial}**")
                        else:
                            st.info(f"ℹ️ Consultando intervalo: **{periodo_inicial}** → **{periodo_final}**")
            
            st.markdown("---")
            
            # ========== SELEÇÃO DE CURSOS ==========
            st.markdown("## 🎓 Seleção de Cursos")
            st.markdown("Selecione os cursos de Química para consulta:")
            
            # Lista de cursos de Química pré-definidos
            cursos_quimica = [
                {
                    'nome': 'Química - Niterói (Presencial - 1ª Entrada SISU)',
                    'codigo': '1525',
                    'desdobramento': 'Química - Niterói (Presencial)',
                    'habilitacao': 'Graduação',
                    'modalidade': 'Presencial'
                },
                {
                    'nome': 'Química - Niterói (Presencial - 2ª Entrada SISU)',
                    'codigo': '1525',
                    'desdobramento': 'Química - Niterói (Presencial)',
                    'habilitacao': 'Graduação',
                    'modalidade': 'Presencial'
                },
                {
                    'nome': 'Química - Niterói (EaD)',
                    'codigo': '1526',
                    'desdobramento': 'Química - Niterói (EaD)',
                    'habilitacao': 'Graduação',
                    'modalidade': 'EaD'
                }
            ]
            
            # Container para seleção de cursos
            cursos_container = st.container()
            
            with cursos_container:
                # Selecionar todos por padrão
                st.info("ℹ️ Todos os cursos de Química estão pré-selecionados")
                
                cursos_selecionados = []
                for curso in cursos_quimica:
                    if st.checkbox(
                        f"**{curso['nome']}** - {curso['modalidade']}",
                        value=True,
                        key=f"curso_{curso['codigo']}_{curso['modalidade']}"
                    ):
                        cursos_selecionados.append(curso)
                
                if not cursos_selecionados:
                    st.warning("⚠️ Selecione pelo menos um curso para continuar")
            
            st.markdown("---")
            
            # ========== RESUMO E CONFIRMAÇÃO ==========
            if cursos_selecionados:
                st.markdown("## 📋 Resumo da Configuração")
                
                col_res1, col_res2, col_res3 = st.columns(3)
                
                with col_res1:
                    st.markdown("**Localidade**")
                    st.success(f"{localidade_niteroi['text']}")
                
                with col_res2:
                    st.markdown("**Formas de Ingresso**")
                    for forma in formas_selecionadas:
                        st.success(f"• {forma}")
                
                with col_res3:
                    st.markdown("**Período**")
                    if periodo_final:
                        st.success(f"{periodo_inicial} → {periodo_final}")
                    else:
                        st.success(f"{periodo_inicial}")
                
                st.markdown("**Cursos Selecionados**")
                for curso in cursos_selecionados:
                    st.info(f"• {curso['nome']}")
                
                # Botão de confirmação
                confirmar = st.button("✅ Confirmar e Prosseguir para Consulta", 
                                    type="primary", 
                                    use_container_width=True)
                
                if confirmar:
                    # Salvar configurações na sessão
                    st.session_state.localidade_selecionada = {
                        'value': localidade_value,
                        'text': localidade_niteroi['text']
                    }
                    
                    st.session_state.formas_ingresso_selecionadas = formas_valores
                    st.session_state.formas_ingresso_texto = formas_selecionadas
                    
                    st.session_state.selected_periodos = {
                        'texto_inicial': periodo_inicial,
                        'valor_inicial': periodo_valores.get(periodo_inicial, ''),
                        'texto_final': periodo_final if periodo_final else None,
                        'valor_final': periodo_valores.get(periodo_final, '') if periodo_final else None
                    }
                    
                    st.session_state.selected_cursos = cursos_selecionados
                    st.session_state.etapa_atual = 3
                    
                    st.success("✅ Configuração salva! Próxima etapa: Consulta de Relatórios")
                    time.sleep(1)
                    st.rerun()

# ========== ETAPA 3 - Consulta de Relatórios ==========
elif etapa_atual == 3:
    st.markdown("## 📊 Etapa 3 - Consulta de Relatórios")
    
    # Exibir configuração atual
    with st.expander("📋 Configuração Atual", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Localidade**")
            st.success(st.session_state.localidade_selecionada['text'])
        
        with col2:
            st.markdown("**Formas de Ingresso**")
            formas_texto = getattr(st.session_state, 'formas_ingresso_texto', ['SISU 1ª Edição', 'SISU 2ª Edição'])
            for forma in formas_texto:
                st.success(f"• {forma}")
        
        with col3:
            st.markdown("**Período**")
            periodo_inicial = st.session_state.selected_periodos['texto_inicial']
            periodo_final = st.session_state.selected_periodos['texto_final']
            if periodo_final:
                st.success(f"{periodo_inicial} → {periodo_final}")
            else:
                st.success(periodo_inicial)
        
        st.markdown("**Cursos Selecionados**")
        for curso in st.session_state.selected_cursos:
            st.info(f"• {curso['nome']}")
    
    st.markdown("---")
    
    # Botões de ação
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    
    with col_btn1:
        voltar = st.button("↩️ Voltar para Configuração", use_container_width=True)
        if voltar:
            st.session_state.etapa_atual = 2
            st.rerun()
    
    with col_btn2:
        if st.session_state.consulta_em_andamento:
            st.button("⏸️ Pausar Consulta", disabled=True, use_container_width=True)
        else:
            iniciar_consulta = st.button("🚀 Iniciar Consulta", 
                                        type="primary", 
                                        use_container_width=True)
    
    with col_btn3:
        if st.session_state.consulta_concluida:
            avancar = st.button("➡️ Avançar para Processamento", 
                               type="primary", 
                               use_container_width=True)
            if avancar:
                st.session_state.etapa_atual = 4
                st.rerun()
    
    # Área de execução da consulta
    if 'iniciar_consulta' in locals() and iniciar_consulta:
        st.session_state.consulta_em_andamento = True
        
        # Container para resultados em tempo real
        resultados_container = st.container()
        
        with resultados_container:
            st.markdown("### 🔄 Executando Consulta")
            st.info("A consulta pode levar vários minutos. Não feche esta página.")
            
            try:
                # Executar consulta completa
                resultados = processar_consulta_completa()
                
                # Salvar resultados na sessão
                st.session_state.resultados_consulta = resultados
                st.session_state.consulta_concluida = True
                st.session_state.consulta_em_andamento = False
                
                # Resumo dos resultados
                st.markdown("### 📈 Resumo da Consulta")
                
                total_cursos = len(resultados)
                sucessos = sum(1 for r in resultados.values() if r.get('status') == 'sucesso')
                erros = total_cursos - sucessos
                
                col_res1, col_res2, col_res3 = st.columns(3)
                
                with col_res1:
                    st.metric("Total de Cursos", total_cursos)
                
                with col_res2:
                    st.metric("Sucessos", sucessos, delta_color="normal")
                
                with col_res3:
                    st.metric("Erros", erros, delta_color="inverse")
                
                # Detalhes dos resultados
                st.markdown("#### 📋 Detalhes por Curso")
                
                for curso_nome, resultado in resultados.items():
                    with st.expander(f"{curso_nome} - {resultado.get('status', 'desconhecido').upper()}"):
                        if resultado.get('status') == 'sucesso':
                            st.success("✅ Sucesso na consulta")
                            if resultado.get('mensagem'):
                                st.info(f"Mensagem: {resultado['mensagem']}")
                            
                            if resultado.get('registros'):
                                st.metric("Registros Obtidos", resultado['registros'])
                            
                            if resultado.get('caminho'):
                                st.info(f"Arquivo: {resultado['caminho']}")
                                
                                # Botão para visualizar amostra
                                if resultado.get('df') is not None:
                                    if st.button(f"👁️ Ver Amostra - {curso_nome}", 
                                                 key=f"ver_{curso_nome}"):
                                        st.dataframe(resultado['df'].head(10))
                                        st.download_button(
                                            label=f"📥 Download {curso_nome}",
                                            data=open(resultado['caminho'], 'rb').read(),
                                            file_name=os.path.basename(resultado['caminho']),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            key=f"download_{curso_nome}"
                                        )
                        else:
                            st.error("❌ Erro na consulta")
                            if resultado.get('mensagem'):
                                st.error(f"Erro: {resultado['mensagem']}")
                
                # Sucesso geral
                if sucessos > 0:
                    st.success(f"✅ Consulta concluída! {sucessos}/{total_cursos} cursos processados com sucesso.")
                    st.balloons()
                else:
                    st.error("❌ Nenhum curso foi processado com sucesso. Verifique os erros acima.")
                
            except Exception as e:
                st.error(f"❌ Erro durante a consulta: {str(e)}")
                logger.error(f"Erro na consulta: {str(e)}", exc_info=True)
                st.session_state.consulta_em_andamento = False
    
    # Mostrar resultados anteriores se já concluído
    elif st.session_state.consulta_concluida and st.session_state.resultados_consulta:
        st.markdown("### 📊 Resultados da Consulta Anterior")
        
        resultados = st.session_state.resultados_consulta
        
        total_cursos = len(resultados)
        sucessos = sum(1 for r in resultados.values() if r.get('status') == 'sucesso')
        erros = total_cursos - sucessos
        
        col_res1, col_res2, col_res3 = st.columns(3)
        
        with col_res1:
            st.metric("Total de Cursos", total_cursos)
        
        with col_res2:
            st.metric("Sucessos", sucessos, delta_color="normal")
        
        with col_res3:
            st.metric("Erros", erros, delta_color="inverse")
        
        # Lista detalhada
        st.markdown("#### 📋 Cursos Processados")
        
        for curso_nome, resultado in resultados.items():
            status_icon = "✅" if resultado.get('status') == 'sucesso' else "❌"
            st.write(f"{status_icon} **{curso_nome}**: {resultado.get('mensagem', 'Sem detalhes')}")

# ========== ETAPA 4 - Processamento e Análise ==========
elif etapa_atual == 4:
    st.markdown("## 📈 Etapa 4 - Processamento e Análise de Dados")
    
    # Verificar se há resultados para processar
    if not st.session_state.resultados_consulta:
        st.warning("⚠️ Nenhum resultado de consulta disponível. Volte à etapa 3 para executar a consulta.")
        
        if st.button("↩️ Voltar para Consulta"):
            st.session_state.etapa_atual = 3
            st.rerun()
    else:
        # Filtrar apenas resultados com sucesso
        resultados_sucesso = {
            nome: resultado for nome, resultado in st.session_state.resultados_consulta.items()
            if resultado.get('status') == 'sucesso' and resultado.get('df') is not None
        }
        
        if not resultados_sucesso:
            st.error("❌ Nenhum arquivo foi processado com sucesso. Não há dados para análise.")
            
            if st.button("↩️ Voltar para Consulta"):
                st.session_state.etapa_atual = 3
                st.rerun()
        else:
            st.success(f"✅ {len(resultados_sucesso)} arquivos disponíveis para análise")
            
            # Container principal de análise
            analise_container = st.container()
            
            with analise_container:
                # Seção 1: Seleção de cursos para análise
                st.markdown("### 🎯 Seleção para Análise")
                
                cursos_disponiveis = list(resultados_sucesso.keys())
                cursos_selecionados_analise = st.multiselect(
                    "Selecione os cursos para análise:",
                    options=cursos_disponiveis,
                    default=cursos_disponiveis[:2] if len(cursos_disponiveis) >= 2 else cursos_disponiveis,
                    help="Selecione os cursos que deseja incluir na análise combinada"
                )
                
                if not cursos_selecionados_analise:
                    st.warning("Selecione pelo menos um curso para análise")
                else:
                    # Seção 2: Opções de processamento
                    st.markdown("### ⚙️ Configurações de Processamento")
                    
                    col_proc1, col_proc2 = st.columns(2)
                    
                    with col_proc1:
                        # Opção de unificar dados
                        unificar_dados = st.checkbox(
                            "Unificar todos os dados em uma única planilha",
                            value=True,
                            help="Combina os dados de todos os cursos selecionados em uma planilha única"
                        )
                        
                        # Opção de análise de evasão
                        analisar_evasao = st.checkbox(
                            "Realizar análise de evasão",
                            value=True,
                            help="Identifica alunos evadidos e classifica por motivo"
                        )
                    
                    with col_proc2:
                        # Opção de exportação
                        formato_exportacao = st.selectbox(
                            "Formato de exportação:",
                            options=['Excel (.xlsx)', 'CSV (.csv)', 'Ambos'],
                            index=0
                        )
                    
                    # Botão de processamento
                    processar = st.button("🔧 Processar e Analisar Dados", 
                                         type="primary", 
                                         use_container_width=True)
                    
                    if processar:
                        try:
                            # Inicializar lista para armazenar DataFrames processados
                            dfs_processados = []
                            infos_cursos = []
                            
                            with st.spinner("Processando dados..."):
                                progress_bar = st.progress(0)
                                
                                for idx, curso_nome in enumerate(cursos_selecionados_analise):
                                    # Atualizar progresso
                                    progresso = (idx + 1) / len(cursos_selecionados_analise)
                                    progress_bar.progress(progresso)
                                    
                                    resultado = resultados_sucesso[curso_nome]
                                    df = resultado['df']
                                    
                                    # Adicionar coluna de identificação do curso
                                    df['CURSO_ORIGEM'] = curso_nome
                                    df['CURSO_MODALIDADE'] = resultado.get('modalidade', 'Desconhecido')
                                    
                                    # Adicionar aos DataFrames processados
                                    dfs_processados.append(df)
                                    
                                    # Coletar informações do curso
                                    infos_cursos.append({
                                        'curso': curso_nome,
                                        'registros': len(df),
                                        'modalidade': resultado.get('modalidade', 'Desconhecido')
                                    })
                                
                                # Unificar dados se solicitado
                                if unificar_dados and len(dfs_processados) > 1:
                                    st.info("Unificando dados de múltiplos cursos...")
                                    df_unificado = pd.concat(dfs_processados, ignore_index=True)
                                    
                                    # Salvar DataFrame unificado
                                    st.session_state.dados_processados['unificado'] = {
                                        'df': df_unificado,
                                        'cursos': [info['curso'] for info in infos_cursos],
                                        'total_registros': len(df_unificado)
                                    }
                                    
                                    # Exibir informações
                                    st.success(f"✅ Dados unificados: {len(df_unificado)} registros de {len(cursos_selecionados_analise)} cursos")
                                    
                                    # Mostrar amostra dos dados
                                    with st.expander("👁️ Visualizar Dados Unificados", expanded=False):
                                        st.dataframe(df_unificado.head(20))
                                
                                # Realizar análise de evasão se solicitado
                                if analisar_evasao:
                                    st.info("Realizando análise de evasão...")
                                    
                                    # Verificar colunas disponíveis para análise de evasão
                                    df_analise = st.session_state.dados_processados.get('unificado', {}).get('df')
                                    if df_analise is None and dfs_processados:
                                        df_analise = dfs_processados[0]
                                    
                                    if df_analise is not None:
                                        # Identificar alunos evadidos (exemplo simplificado)
                                        # Esta lógica deve ser adaptada conforme as colunas reais do seu dataset
                                        colunas_evasao = ['SITUACAO', 'STATUS', 'SITUACAO_ALUNO', 'SITUACAO_CURSO']
                                        coluna_encontrada = None
                                        
                                        for col in colunas_evasao:
                                            if col in df_analise.columns:
                                                coluna_encontrada = col
                                                break
                                        
                                        if coluna_encontrada:
                                            # Contar por situação
                                            contagem_situacao = df_analise[coluna_encontrada].value_counts()
                                            
                                            st.markdown("#### 📊 Distribuição por Situação")
                                            st.bar_chart(contagem_situacao)
                                            
                                            # Salvar resultados da análise
                                            st.session_state.dados_processados['analise_evasao'] = {
                                                'coluna_analise': coluna_encontrada,
                                                'contagem': contagem_situacao.to_dict(),
                                                'total_alunos': len(df_analise)
                                            }
                                            
                                            st.success(f"✅ Análise de evasão concluída usando coluna: {coluna_encontrada}")
                                        else:
                                            st.warning("⚠️ Não foi possível identificar coluna para análise de evasão")
                                
                                # Preparar exportação
                                st.markdown("### 📤 Exportação de Dados")
                                
                                # Criar pasta de exportação
                                pasta_export = 'exportados'
                                os.makedirs(pasta_export, exist_ok=True)
                                
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                arquivos_exportados = []
                                
                                # Exportar dados unificados
                                if 'unificado' in st.session_state.dados_processados:
                                    df_unificado = st.session_state.dados_processados['unificado']['df']
                                    
                                    if formato_exportacao in ['Excel (.xlsx)', 'Ambos']:
                                        caminho_excel = os.path.join(pasta_export, f'dados_unificados_{timestamp}.xlsx')
                                        df_unificado.to_excel(caminho_excel, index=False)
                                        arquivos_exportados.append(('Excel', caminho_excel))
                                    
                                    if formato_exportacao in ['CSV (.csv)', 'Ambos']:
                                        caminho_csv = os.path.join(pasta_export, f'dados_unificados_{timestamp}.csv')
                                        df_unificado.to_csv(caminho_csv, index=False, encoding='utf-8-sig')
                                        arquivos_exportados.append(('CSV', caminho_csv))
                                
                                # Exportar dados individuais
                                for idx, (curso_nome, df) in enumerate(zip(cursos_selecionados_analise, dfs_processados)):
                                    if formato_exportacao in ['Excel (.xlsx)', 'Ambos']:
                                        caminho_excel = os.path.join(pasta_export, f'{curso_nome.replace(" ", "_")}_{timestamp}.xlsx')
                                        df.to_excel(caminho_excel, index=False)
                                    
                                    if formato_exportacao in ['CSV (.csv)', 'Ambos']:
                                        caminho_csv = os.path.join(pasta_export, f'{curso_nome.replace(" ", "_")}_{timestamp}.csv')
                                        df.to_csv(caminho_csv, index=False, encoding='utf-8-sig')
                                
                                # Botões de download
                                if arquivos_exportados:
                                    st.success("✅ Arquivos exportados com sucesso!")
                                    
                                    for formato, caminho in arquivos_exportados:
                                        with open(caminho, 'rb') as f:
                                            st.download_button(
                                                label=f"📥 Download {formato} Unificado",
                                                data=f.read(),
                                                file_name=os.path.basename(caminho),
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == 'Excel' else "text/csv"
                                            )
                                    
                                    # Avançar para próxima etapa
                                    st.markdown("---")
                                    avancar = st.button("➡️ Continuar para Análise Detalhada", 
                                                       type="primary", 
                                                       use_container_width=True)
                                    if avancar:
                                        st.session_state.etapa_atual = 5
                                        st.rerun()
                                else:
                                    st.warning("⚠️ Nenhum arquivo foi exportado")
                        
                        except Exception as e:
                            st.error(f"❌ Erro durante o processamento: {str(e)}")
                            logger.error(f"Erro no processamento: {str(e)}", exc_info=True)

# ========== ETAPA 5 - Análise Detalhada e Relatório ==========
elif etapa_atual == 5:
    st.markdown("## 📋 Etapa 5 - Análise Detalhada e Relatório Final")
    
    # Verificar se há dados processados
    if not st.session_state.dados_processados:
        st.warning("⚠️ Nenhum dado processado disponível. Volte à etapa 4.")
        
        if st.button("↩️ Voltar para Processamento"):
            st.session_state.etapa_atual = 4
            st.rerun()
    else:
        st.success("✅ Dados processados disponíveis para análise detalhada")
        
        # Opções de análise
        st.markdown("### 📊 Tipos de Análise")
        
        tipo_analise = st.selectbox(
            "Selecione o tipo de análise:",
            options=[
                "Visão Geral dos Dados",
                "Análise de Evasão",
                "Distribuição por Período",
                "Comparativo entre Cursos",
                "Relatório Completo"
            ],
            index=0
        )
        
        if tipo_analise == "Visão Geral dos Dados":
            if 'unificado' in st.session_state.dados_processados:
                df = st.session_state.dados_processados['unificado']['df']
                
                st.markdown("#### 📈 Estatísticas Descritivas")
                
                col_est1, col_est2, col_est3 = st.columns(3)
                
                with col_est1:
                    st.metric("Total de Registros", len(df))
                
                with col_est2:
                    st.metric("Total de Cursos", len(st.session_state.dados_processados['unificado']['cursos']))
                
                with col_est3:
                    # Contar alunos únicos (se houver coluna de matrícula)
                    col_matricula = None
                    for col in ['MATRICULA', 'MATRÍCULA', 'ID_ALUNO']:
                        if col in df.columns:
                            col_matricula = col
                            break
                    
                    if col_matricula:
                        alunos_unicos = df[col_matricula].nunique()
                        st.metric("Alunos Únicos", alunos_unicos)
                    else:
                        st.metric("Colunas", len(df.columns))
                
                # Distribuição por curso
                st.markdown("#### 🎓 Distribuição por Curso")
                if 'CURSO_ORIGEM' in df.columns:
                    distribuicao_curso = df['CURSO_ORIGEM'].value_counts()
                    st.bar_chart(distribuicao_curso)
                    
                    # Tabela de distribuição
                    st.dataframe(distribuicao_curso)
        
        elif tipo_analise == "Análise de Evasão":
            st.markdown("#### 📉 Análise de Evasão")
            
            if 'analise_evasao' in st.session_state.dados_processados:
                analise = st.session_state.dados_processados['analise_evasao']
                
                col_ev1, col_ev2 = st.columns(2)
                
                with col_ev1:
                    st.metric("Total de Alunos", analise['total_alunos'])
                    st.metric("Coluna Analisada", analise['coluna_analise'])
                
                with col_ev2:
                    # Calcular taxa de evasão (exemplo)
                    situacoes_evasao = ['EVADIDO', 'DESLIGADO', 'CANCELADO', 'ABANDONO']
                    total_evadidos = 0
                    
                    for situacao, quantidade in analise['contagem'].items():
                        if any(termo in str(situacao).upper() for termo in situacoes_evasao):
                            total_evadidos += quantidade
                    
                    if analise['total_alunos'] > 0:
                        taxa_evasao = (total_evadidos / analise['total_alunos']) * 100
                        st.metric("Taxa de Evasão Estimada", f"{taxa_evasao:.1f}%")
                    else:
                        st.metric("Taxa de Evasão", "0%")
                
                # Gráfico de distribuição
                st.markdown("##### Distribuição por Situação")
                
                # Converter para DataFrame para gráfico
                df_contagem = pd.DataFrame(
                    list(analise['contagem'].items()),
                    columns=['Situação', 'Quantidade']
                )
                
                st.bar_chart(df_contagem.set_index('Situação'))
                
                # Tabela detalhada
                st.markdown("##### Tabela de Situações")
                st.dataframe(df_contagem)
            
            else:
                st.info("ℹ️ Execute a análise de evasão na etapa anterior para visualizar os resultados.")
        
        # Seção de geração de relatório
        st.markdown("---")
        st.markdown("### 📄 Gerar Relatório Final")
        
        col_rel1, col_rel2 = st.columns(2)
        
        with col_rel1:
            formato_relatorio = st.selectbox(
                "Formato do relatório:",
                options=['PDF', 'Excel', 'HTML'],
                index=0
            )
        
        with col_rel2:
            incluir_graficos = st.checkbox("Incluir gráficos", value=True)
            incluir_dados_brutos = st.checkbox("Incluir dados brutos", value=False)
        
        gerar_relatorio = st.button("📄 Gerar Relatório Final", 
                                   type="primary", 
                                   use_container_width=True)
        
        if gerar_relatorio:
            with st.spinner("Gerando relatório..."):
                try:
                    # Simular geração de relatório
                    time.sleep(2)
                    
                    # Criar nome do arquivo
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    nome_arquivo = f"relatorio_final_{timestamp}"
                    
                    # Simular arquivo gerado
                    caminho_simulado = f"relatorios/{nome_arquivo}.{formato_relatorio.lower()}"
                    
                    st.success(f"✅ Relatório gerado com sucesso: {nome_arquivo}.{formato_relatorio.lower()}")
                    
                    # Simular download (em produção, você geraria o arquivo real)
                    st.info("📥 Em um ambiente real, o arquivo seria disponibilizado para download aqui.")
                    
                    # Botão simulado de download
                    if st.button("📥 Download Relatório (Simulado)", use_container_width=True):
                        st.info("ℹ️ Em produção, isso baixaria o arquivo real.")
                
                except Exception as e:
                    st.error(f"❌ Erro ao gerar relatório: {str(e)}")

# ========== RODAPÉ ==========
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p style='color: #666; font-size: 0.9em'>
    Sistema de Análise de Evasão - Departamento de Química UFF<br>
    Desenvolvido para fins acadêmicos e de pesquisa
    </p>
</div>
""", unsafe_allow_html=True)

# Script JavaScript para melhorar a experiência
st.markdown("""
<script>
// Auto-rolar para o topo quando mudar de etapa
if (window.location.hash) {
    window.scrollTo(0, 0);
}
</script>
""", unsafe_allow_html=True)
