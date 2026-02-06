# main_simplificado.py
import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd
import time
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import UFFAuthenticator

# Configurações
PASTA_RELATORIOS = 'relatorios'

# Configurar página
st.set_page_config(
    page_title="Automação de Relatórios UFF - Química",
    page_icon="📊",
    layout="wide"
)

# Estado da sessão
def inicializar_estado():
    estados = {
        'authenticated': False,
        'authenticator': None,
        'username': '',
        'selected_cursos': [],
        'selected_periodos': {},
        'etapa_atual': 1,
        'geracao_concluida': False,
        'resultados': {},
        'geracao_em_andamento': False
    }
    
    for key, value in estados.items():
        if key not in st.session_state:
            st.session_state[key] = value

inicializar_estado()

# ================== MÓDULO SIMPLIFICADO DENTRO DO MAIN ==================

class GeradorRelatoriosStreamlit:
    """Versão simplificada do gerador de relatórios para Streamlit"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = "https://app.uff.br/graduacao/administracaoacademica"
    
    def extrair_csrf_token(self, html):
        """Extrai token CSRF do HTML"""
        import re
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Procurar input hidden
        input_token = soup.find('input', {'name': 'authenticity_token'})
        if input_token and input_token.get('value'):
            return input_token.get('value')
        
        # Procurar meta tag
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token and meta_token.get('content'):
            return meta_token.get('content')
        
        return None
    
    def carregar_pagina_formulario(self):
        """Carrega a página do formulário"""
        url = f"{self.base_url}/relatorios/listagens_alunos"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Erro ao carregar formulário: {str(e)}")
            return None
    
    def criar_parametros(self, curso_nome, periodo):
        """Cria parâmetros para o formulário"""
        
        # Mapeamento baseado no HTML fornecido
        mapeamento = {
            'Química (Licenciatura)': {
                'idcurso': '12700',
                'iddesdobramento': '12700'
            },
            'Química (Bacharelado)': {
                'idcurso': '12700',
                'iddesdobramento': '312700'
            },
            'Química Industrial': {
                'idcurso': '12709',
                'iddesdobramento': '12709'
            }
        }
        
        # Determinar forma de ingresso baseada no semestre
        semestre = int(periodo[4])  # Último dígito
        if semestre == 1:
            forma_ingresso = '125'  # SISU 1ª Edição
        else:
            forma_ingresso = '124'  # SISU 2ª Edição
        
        curso_info = mapeamento.get(curso_nome)
        if not curso_info:
            raise ValueError(f"Curso não mapeado: {curso_nome}")
        
        return {
            'authenticity_token': '',  # Será preenchido depois
            'idlocalidade': '1',  # Niterói
            'idcurso': curso_info['idcurso'],
            'iddesdobramento': curso_info['iddesdobramento'],
            'idturno': '',  # Todos
            'idstatusaluno': '',  # Todos
            'idsituacaoaluno': '',  # Todas
            'idformaingresso': forma_ingresso,
            'idacaoafirmativa': '',  # Todas
            'anosem_ingresso': periodo,  # Formato: 20251, 20252
            'anosem_desvinculacao': '',  # Não filtrar
            'format': 'xls'  # XLSX
        }
    
    def enviar_formulario(self, html_pagina, parametros):
        """Envia o formulário"""
        from bs4 import BeautifulSoup
        import re
        
        # Extrair tokens
        soup = BeautifulSoup(html_pagina, 'html.parser')
        
        # Token CSRF
        csrf_token = self.extrair_csrf_token(html_pagina)
        if not csrf_token:
            logger.error("CSRF token não encontrado")
            return None
        
        # Token utf8
        utf8_input = soup.find('input', {'name': 'utf8'})
        utf8_value = utf8_input.get('value') if utf8_input else '✓'
        
        # Atualizar parâmetros com tokens
        parametros_completos = parametros.copy()
        parametros_completos['authenticity_token'] = csrf_token
        parametros_completos['utf8'] = utf8_value
        
        # Enviar requisição
        url = f"{self.base_url}/relatorios/listagens_alunos"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': url
        }
        
        try:
            response = self.session.post(
                url,
                data=parametros_completos,
                headers=headers,
                allow_redirects=True,
                timeout=30
            )
            
            response.raise_for_status()
            
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url:
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    return {
                        'success': True,
                        'relatorio_id': match.group(1),
                        'url': response.url
                    }
            
            return {
                'success': False,
                'error': 'Não redirecionado para página de relatório'
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar formulário: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verificar_status_relatorio(self, relatorio_id):
        """Verifica status do relatório"""
        url = f"{self.base_url}/relatorios/{relatorio_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Verificar barra de progresso
            steps_bar = soup.find('div', {'id': 'relatorioStepsBar'})
            status = 'PROCESSANDO'
            
            if steps_bar:
                steps = steps_bar.find_all('div', class_='step')
                if steps and 'done' in steps[-1].get('class', []):
                    status = 'PRONTO'
            
            # Verificar link de download
            download_link = None
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if '.xlsx' in href.lower() or 'download' in href.lower():
                    download_link = href
                    if not href.startswith('http'):
                        download_link = f"{self.base_url}{href}"
                    status = 'PRONTO'
                    break
            
            return {
                'status': status,
                'download_url': download_link,
                'html': response.text[:1000]  # Para debug
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar status: {str(e)}")
            return {
                'status': 'ERRO',
                'error': str(e)
            }
    
    def baixar_relatorio(self, download_url, curso_nome, periodo):
        """Baixa o relatório"""
        try:
            # Criar nome do arquivo
            nome_arquivo = f"{curso_nome.replace(' ', '_')}_{periodo[:4]}_{periodo[4:]}.xlsx"
            caminho = os.path.join(PASTA_RELATORIOS, nome_arquivo)
            
            # Baixar
            response = self.session.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(caminho, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return {
                'success': True,
                'caminho': caminho,
                'tamanho': os.path.getsize(caminho)
            }
            
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def gerar_relatorio(self, curso_nome, periodo, progress_callback=None):
        """Fluxo completo para gerar um relatório"""
        
        # 1. Carregar página do formulário
        if progress_callback:
            progress_callback(f"Carregando formulário...", 10)
        
        html_pagina = self.carregar_pagina_formulario()
        if not html_pagina:
            return {
                'success': False,
                'error': 'Não foi possível carregar o formulário',
                'curso': curso_nome,
                'periodo': periodo
            }
        
        # 2. Criar parâmetros
        if progress_callback:
            progress_callback(f"Configurando filtros para {curso_nome}...", 20)
        
        try:
            parametros = self.criar_parametros(curso_nome, periodo)
        except Exception as e:
            return {
                'success': False,
                'error': f"Erro ao criar parâmetros: {str(e)}",
                'curso': curso_nome,
                'periodo': periodo
            }
        
        # 3. Enviar formulário
        if progress_callback:
            progress_callback(f"Enviando solicitação...", 30)
        
        resultado_envio = self.enviar_formulario(html_pagina, parametros)
        if not resultado_envio or not resultado_envio.get('success'):
            return {
                'success': False,
                'error': resultado_envio.get('error', 'Erro ao enviar formulário'),
                'curso': curso_nome,
                'periodo': periodo
            }
        
        relatorio_id = resultado_envio['relatorio_id']
        
        # 4. Monitorar processamento
        timeout = 1800  # 30 minutos
        inicio = time.time()
        tentativas = 0
        
        while time.time() - inicio < timeout:
            tentativas += 1
            
            if progress_callback:
                progresso = 30 + (min((time.time() - inicio) / timeout, 0.95) * 50)
                progress_callback(f"Aguardando processamento (tentativa {tentativas})...", progresso)
            
            # Verificar status
            status = self.verificar_status_relatorio(relatorio_id)
            
            if status['status'] == 'PRONTO' and status.get('download_url'):
                # 5. Baixar relatório
                if progress_callback:
                    progress_callback(f"Baixando arquivo...", 90)
                
                resultado_download = self.baixar_relatorio(
                    status['download_url'],
                    curso_nome,
                    periodo
                )
                
                if resultado_download.get('success'):
                    if progress_callback:
                        progress_callback("Concluído!", 100)
                    
                    return {
                        'success': True,
                        'relatorio_id': relatorio_id,
                        'caminho_arquivo': resultado_download['caminho'],
                        'curso': curso_nome,
                        'periodo': periodo,
                        'tentativas': tentativas
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Erro no download: {resultado_download.get('error')}",
                        'curso': curso_nome,
                        'periodo': periodo
                    }
            
            elif status['status'] == 'ERRO':
                return {
                    'success': False,
                    'error': f"Erro no processamento: {status.get('error')}",
                    'curso': curso_nome,
                    'periodo': periodo
                }
            
            # Aguardar antes de verificar novamente
            time.sleep(30)  # 30 segundos
        
        # Timeout
        return {
            'success': False,
            'error': f"Timeout após {timeout//60} minutos",
            'curso': curso_nome,
            'periodo': periodo
        }
    
    def processar_periodos_intervalo(self, periodo_inicial, periodo_final):
        """Gera lista de períodos"""
        ano_inicial = int(periodo_inicial[:4])
        sem_inicial = int(periodo_inicial[4])
        ano_final = int(periodo_final[:4])
        sem_final = int(periodo_final[4])
        
        periodos = []
        ano_atual = ano_inicial
        sem_atual = sem_inicial
        
        while (ano_atual < ano_final) or (ano_atual == ano_final and sem_atual <= sem_final):
            periodos.append(f"{ano_atual}{sem_atual}")
            
            if sem_atual == 1:
                sem_atual = 2
            else:
                sem_atual = 1
                ano_atual += 1
        
        return periodos


class InterfaceProgressoStreamlit:
    """Interface de progresso para Streamlit"""
    
    def __init__(self, container):
        self.container = container
        self.progress_bar = None
        self.status_text = None
        self.contadores = {'sucesso': 0, 'erro': 0, 'total': 0}
    
    def inicializar(self, total_tarefas):
        """Inicializa na interface do Streamlit"""
        self.contadores['total'] = total_tarefas
        
        with self.container:
            # Barra de progresso principal
            self.progress_bar = st.progress(0)
            self.status_text = st.empty()
            
            # Contadores
            cols = st.columns(4)
            self.col_total = cols[0].empty()
            self.col_sucesso = cols[1].empty()
            self.col_erro = cols[2].empty()
            self.col_restante = cols[3].empty()
            
            self.atualizar_contadores()
            
            # Área para logs
            st.markdown("---")
            st.subheader("📋 Log de Execução")
            self.log_container = st.empty()
            self.logs = []
    
    def atualizar(self, mensagem, progresso):
        """Atualiza barra e mensagem"""
        if self.progress_bar:
            self.progress_bar.progress(progresso / 100)
        if self.status_text:
            self.status_text.text(mensagem)
    
    def adicionar_log(self, mensagem):
        """Adiciona mensagem ao log"""
        self.logs.append(f"{time.strftime('%H:%M:%S')} - {mensagem}")
        
        # Atualizar container de logs (mantém apenas últimos 20 logs)
        if len(self.logs) > 20:
            self.logs = self.logs[-20:]
        
        with self.container:
            self.log_container.text("\n".join(self.logs))
    
    def adicionar_resultado(self, curso, periodo, sucesso, detalhe=""):
        """Registra resultado"""
        periodo_display = f"{periodo[:4]}/{periodo[4:]}"
        
        if sucesso:
            self.contadores['sucesso'] += 1
            log_msg = f"✅ {curso} - {periodo_display}: {detalhe}"
        else:
            self.contadores['erro'] += 1
            log_msg = f"❌ {curso} - {periodo_display}: {detalhe}"
        
        self.adicionar_log(log_msg)
        self.atualizar_contadores()
    
    def atualizar_contadores(self):
        """Atualiza contadores"""
        concluido = self.contadores['sucesso'] + self.contadores['erro']
        restante = self.contadores['total'] - concluido
        
        self.col_total.markdown(f"**Total:** {self.contadores['total']}")
        self.col_sucesso.markdown(f"**✅ {self.contadores['sucesso']}**")
        self.col_erro.markdown(f"**❌ {self.contadores['erro']}**")
        self.col_restante.markdown(f"**⏳ {restante}**")
    
    def exibir_resumo(self):
        """Exibe resumo final"""
        with self.container:
            st.markdown("---")
            st.subheader("📊 Resumo da Execução")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                taxa = (self.contadores['sucesso'] / self.contadores['total'] * 100) if self.contadores['total'] > 0 else 0
                st.metric("Taxa de Sucesso", f"{taxa:.1f}%")
            with col2:
                st.metric("Relatórios Gerados", self.contadores['sucesso'])
            with col3:
                st.metric("Relatórios com Erro", self.contadores['erro'])

# ================== INTERFACE PRINCIPAL ==================

st.title("📊 Sistema de Análise de Evasão - UFF (Simplificado)")
st.markdown("---")

# ETAPA 1 - LOGIN
if not st.session_state.authenticated:
    st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
    
    with st.form("login_form"):
        username = st.text_input("Identificação (idUFF)", placeholder="CPF, email ou passaporte")
        password = st.text_input("Senha", type="password", placeholder="Sua senha da UFF")
        
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

else:
    # Menu
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"✅ Logado como: {st.session_state.username}")
    with col2:
        if st.button("🚪 Sair", type="secondary", use_container_width=True):
            if st.session_state.authenticator:
                st.session_state.authenticator.logout()
            st.session_state.clear()
            inicializar_estado()
            st.rerun()
    
    st.markdown("---")
    
    # Barra de etapas
    etapas = [
        ("1. Configuração", 1),
        ("2. Geração", 2),
        ("3. Resultados", 3)
    ]
    
    cols = st.columns(3)
    for col, (nome, num) in zip(cols, etapas):
        with col:
            if st.session_state.etapa_atual == num:
                st.info(f"**🔄 {nome}**")
            elif st.session_state.etapa_atual > num:
                st.success(f"**✅ {nome}**")
            else:
                st.markdown(f"**⏳ {nome}**")
    
    st.markdown("---")
    
    # ETAPA 1 - CONFIGURAÇÃO
    if st.session_state.etapa_atual == 1:
        st.markdown("## 🎯 Configuração da Análise")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📅 Período")
            
            ano_inicial = st.number_input("Ano Inicial", min_value=2000, max_value=2030, value=2025)
            semestre_inicial = st.selectbox("Semestre Inicial", [1, 2], format_func=lambda x: f"{x}º Semestre")
            
            ano_final = st.number_input("Ano Final", min_value=2000, max_value=2030, value=2025)
            semestre_final = st.selectbox("Semestre Final", [1, 2], index=1, format_func=lambda x: f"{x}º Semestre")
            
            if ano_final < ano_inicial or (ano_final == ano_inicial and semestre_final < semestre_inicial):
                st.error("Período final deve ser igual ou posterior ao inicial")
        
        with col2:
            st.subheader("📚 Cursos")
            
            cursos_disponiveis = [
                'Química (Licenciatura)',
                'Química (Bacharelado)',
                'Química Industrial'
            ]
            
            cursos_selecionados = st.multiselect(
                "Selecione os cursos para análise:",
                options=cursos_disponiveis,
                default=cursos_disponiveis
            )
            
            if cursos_selecionados:
                st.success(f"✅ {len(cursos_selecionados)} curso(s) selecionado(s)")
        
        # Calcular total
        if st.button("📊 Calcular Total de Relatórios", type="secondary"):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso")
            else:
                periodo_inicial = f"{ano_inicial}{semestre_inicial}"
                periodo_final = f"{ano_final}{semestre_final}"
                
                gerador = GeradorRelatoriosStreamlit(st.session_state.authenticator.session)
                periodos = gerador.processar_periodos_intervalo(periodo_inicial, periodo_final)
                
                total = len(cursos_selecionados) * len(periodos)
                
                st.info(f"""
                **Resumo da configuração:**
                
                **Cursos selecionados:**
                {chr(10).join(f'- {curso}' for curso in cursos_selecionados)}
                
                **Períodos a processar:**
                {chr(10).join(f'- {p[:4]}/{p[4:]}' for p in periodos)}
                
                **Total de relatórios:** {total}
                
                **Tempo estimado:** ~{total * 3} minutos
                """)
        
        # Confirmar
        st.markdown("---")
        
        if st.button("✅ Confirmar e Iniciar Geração", type="primary", use_container_width=True):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso")
            else:
                st.session_state.selected_cursos = cursos_selecionados
                st.session_state.selected_periodos = {
                    'inicial': f"{ano_inicial}{semestre_inicial}",
                    'final': f"{ano_final}{semestre_final}"
                }
                
                st.session_state.etapa_atual = 2
                st.success("✅ Configuração salva!")
                time.sleep(1)
                st.rerun()
    
    # ETAPA 2 - GERAÇÃO
    elif st.session_state.etapa_atual == 2:
        st.markdown("## 🔍 Geração de Relatórios")
        
        # Mostrar configuração
        with st.expander("📋 Configuração Atual", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                periodos = st.session_state.selected_periodos
                st.markdown(f"**Período:** {periodos['inicial'][:4]}/{periodos['inicial'][4:]} a {periodos['final'][:4]}/{periodos['final'][4:]}")
                st.markdown(f"**Localidade:** Niterói")
                st.markdown(f"**Forma de Ingresso:** SISU (automático por semestre)")
            
            with col2:
                cursos = st.session_state.selected_cursos
                st.markdown("**Cursos:**")
                for curso in cursos:
                    st.markdown(f"- {curso}")
        
        # Calcular total
        gerador = GeradorRelatoriosStreamlit(st.session_state.authenticator.session)
        periodos_lista = gerador.processar_periodos_intervalo(
            st.session_state.selected_periodos['inicial'],
            st.session_state.selected_periodos['final']
        )
        
        total_relatorios = len(st.session_state.selected_cursos) * len(periodos_lista)
        
        st.info(f"""
        **Pronto para gerar {total_relatorios} relatório(s)**
        
        **Filtros que serão aplicados em CADA relatório:**
        1. Localidade: Niterói
        2. Curso específico selecionado
        3. Desdobramento correto do curso
        4. Forma de ingresso SISU (1ª ou 2ª edição conforme o semestre)
        5. Período de ingresso específico
        """)
        
        # Controles
        if not st.session_state.geracao_em_andamento:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Iniciar Geração de Relatórios", type="primary", use_container_width=True):
                    st.session_state.geracao_em_andamento = True
                    st.rerun()
            
            with col2:
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.etapa_atual = 1
                    st.rerun()
        
        # Geração em andamento
        if st.session_state.geracao_em_andamento:
            # Container para progresso
            progress_container = st.container()
            
            # Inicializar interface de progresso
            interface = InterfaceProgressoStreamlit(progress_container)
            interface.inicializar(total_relatorios)
            
            # Inicializar gerador
            gerador = GeradorRelatoriosStreamlit(st.session_state.authenticator.session)
            
            # Criar container para resultados
            resultados_container = st.container()
            
            # Processar cada curso e período
            resultados = {}
            
            for curso_nome in st.session_state.selected_cursos:
                resultados[curso_nome] = []
                
                for periodo in periodos_lista:
                    # Callback de progresso
                    def callback_progresso(mensagem, progresso):
                        interface.atualizar(mensagem, progresso)
                    
                    # Log inicial
                    interface.adicionar_log(f"Iniciando: {curso_nome} - {periodo[:4]}/{periodo[4:]}")
                    
                    # Gerar relatório
                    resultado = gerador.gerar_relatorio(
                        curso_nome,
                        periodo,
                        callback_progresso
                    )
                    
                    # Registrar resultado
                    resultados[curso_nome].append(resultado)
                    
                    # Atualizar interface
                    if resultado.get('success'):
                        interface.adicionar_resultado(
                            curso_nome,
                            periodo,
                            True,
                            f"Relatório gerado (ID: {resultado.get('relatorio_id')})"
                        )
                    else:
                        interface.adicionar_resultado(
                            curso_nome,
                            periodo,
                            False,
                            resultado.get('error', 'Erro desconhecido')
                        )
                    
                    # Aguardar entre requisições
                    time.sleep(5)
            
            # Finalizar
            st.session_state.resultados = resultados
            st.session_state.geracao_concluida = True
            st.session_state.geracao_em_andamento = False
            
            interface.atualizar("✅ Geração concluída!", 100)
            interface.exibir_resumo()
            
            time.sleep(2)
            
            # Exibir resultados detalhados
            with resultados_container:
                st.markdown("### 📋 Resultados Detalhados")
                
                dados_tabela = []
                for curso_nome, resultados_curso in resultados.items():
                    for resultado in resultados_curso:
                        periodo_display = f"{resultado.get('periodo', '')[0:4]}/{resultado.get('periodo', '')[4:]}"
                        
                        dados_tabela.append({
                            'Curso': curso_nome,
                            'Período': periodo_display,
                            'Status': '✅ Sucesso' if resultado.get('success') else '❌ Erro',
                            'Detalhes': resultado.get('error', 'Concluído')[:50],
                            'ID': resultado.get('relatorio_id', 'N/A')
                        })
                
                if dados_tabela:
                    df = pd.DataFrame(dados_tabela)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Botão para continuar
            if st.button("📊 Processar Dados e Gerar Estatísticas", type="primary", use_container_width=True):
                st.session_state.etapa_atual = 3
                st.rerun()
    
    # ETAPA 3 - RESULTADOS
    elif st.session_state.etapa_atual == 3:
        st.markdown("## 📊 Resultados e Estatísticas")
        
        if not st.session_state.get('resultados'):
            st.error("Nenhum dado para processar.")
            if st.button("🔙 Voltar para Geração"):
                st.session_state.etapa_atual = 2
                st.rerun()
        else:
            # Contar sucessos
            total_sucessos = 0
            total_relatorios = 0
            arquivos_sucesso = []
            
            for curso_nome, resultados_curso in st.session_state.resultados.items():
                for resultado in resultados_curso:
                    total_relatorios += 1
                    if resultado.get('success'):
                        total_sucessos += 1
                        arquivos_sucesso.append(resultado.get('caminho_arquivo'))
            
            st.success(f"✅ {total_sucessos} de {total_relatorios} relatórios gerados com sucesso")
            
            if arquivos_sucesso:
                st.info(f"**Arquivos gerados:**")
                for arquivo in arquivos_sucesso:
                    if arquivo and os.path.exists(arquivo):
                        tamanho_mb = os.path.getsize(arquivo) / (1024 * 1024)
                        st.markdown(f"- `{os.path.basename(arquivo)}` ({tamanho_mb:.1f} MB)")
            
            # Processador de dados simplificado
            if st.button("📈 Processar Dados dos Relatórios", type="primary"):
                with st.spinner("Processando dados..."):
                    dados_consolidados = []
                    
                    for curso_nome, resultados_curso in st.session_state.resultados.items():
                        for resultado in resultados_curso:
                            if resultado.get('success') and resultado.get('caminho_arquivo'):
                                caminho = resultado['caminho_arquivo']
                                periodo = resultado.get('periodo', '')
                                periodo_display = f"{periodo[:4]}/{periodo[4:]}" if len(periodo) == 5 else periodo
                                
                                try:
                                    # Ler Excel
                                    df = pd.read_excel(caminho)
                                    
                                    # Análise básica
                                    total = len(df)
                                    
                                    # Contar por modalidade (se existir coluna 'MODALIDADE')
                                    ampla = 0
                                    acoes = 0
                                    if 'MODALIDADE' in df.columns:
                                        modalidades = df['MODALIDADE'].fillna('')
                                        ampla = len(modalidades[modalidades.str.startswith('A', na=False)])
                                        acoes = len(modalidades[modalidades.str.startswith('L', na=False)])
                                    
                                    dados_consolidados.append({
                                        'Curso': curso_nome,
                                        'Período': periodo_display,
                                        'Total Matrículas': total,
                                        'Ampla Concorrência': ampla,
                                        'Ações Afirmativas': acoes,
                                        'Arquivo': os.path.basename(caminho)
                                    })
                                    
                                except Exception as e:
                                    st.warning(f"Erro ao processar {caminho}: {str(e)}")
                    
                    # Exibir resultados
                    if dados_consolidados:
                        df_resultados = pd.DataFrame(dados_consolidados)
                        
                        st.markdown("### 📊 Dados Consolidados")
                        st.dataframe(df_resultados, use_container_width=True)
                        
                        # Calcular totais
                        totais = df_resultados.groupby('Curso').agg({
                            'Total Matrículas': 'sum',
                            'Ampla Concorrência': 'sum',
                            'Ações Afirmativas': 'sum'
                        }).reset_index()
                        
                        st.markdown("### 📈 Totais por Curso")
                        st.dataframe(totais, use_container_width=True)
                        
                        # Botão para exportar
                        if st.button("📥 Exportar para Excel"):
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            caminho_export = os.path.join(PASTA_RELATORIOS, f"resultados_{timestamp}.xlsx")
                            
                            with pd.ExcelWriter(caminho_export, engine='openpyxl') as writer:
                                df_resultados.to_excel(writer, sheet_name='Detalhes', index=False)
                                totais.to_excel(writer, sheet_name='Totais', index=False)
                            
                            with open(caminho_export, 'rb') as f:
                                st.download_button(
                                    label="Baixar Planilha",
                                    data=f,
                                    file_name=f"resultados_evasao_{timestamp}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
            
            # Botões de controle
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Novo Processo", type="secondary", use_container_width=True):
                    st.session_state.selected_cursos = []
                    st.session_state.selected_periodos = {}
                    st.session_state.geracao_concluida = False
                    st.session_state.resultados = {}
                    st.session_state.etapa_atual = 1
                    st.rerun()
            
            with col2:
                if st.button("🔍 Ver Relatórios Gerados", type="primary", use_container_width=True):
                    st.markdown("### 📁 Relatórios na Pasta")
                    
                    if os.path.exists(PASTA_RELATORIOS):
                        arquivos = os.listdir(PASTA_RELATORIOS)
                        if arquivos:
                            for arquivo in sorted(arquivos):
                                if arquivo.endswith('.xlsx'):
                                    caminho = os.path.join(PASTA_RELATORIOS, arquivo)
                                    tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
                                    st.markdown(f"- **{arquivo}** ({tamanho_mb:.1f} MB)")
                        else:
                            st.info("Nenhum arquivo na pasta de relatórios")
                    else:
                        st.warning("Pasta de relatórios não existe")

# Rodapé
st.markdown("---")
st.caption(f"🕒 {datetime.now().strftime('%H:%M:%S')} | 📊 Departamento de Química - UFF | 🔒 Sistema de automação seguro")

# Inicialização
if __name__ == "__main__":
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
