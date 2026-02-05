"""
main.py - Aplicação Streamlit principal para automação de relatórios UFF
"""
import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd
import time

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
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'authenticator' not in st.session_state:
        st.session_state.authenticator = None
    if 'relatorios_em_processamento' not in st.session_state:
        st.session_state.relatorios_em_processamento = []
    if 'relatorios_concluidos' not in st.session_state:
        st.session_state.relatorios_concluidos = []
    if 'credentials' not in st.session_state:
        st.session_state.credentials = {'username': '', 'password': ''}
    if 'ultima_atualizacao' not in st.session_state:
        st.session_state.ultima_atualizacao = None

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
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("📊 Automação de Relatórios UFF - Departamento de Química")
st.markdown("---")

# Sidebar - Login e Configurações
with st.sidebar:
    st.header("🔐 Autenticação")
    
    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("ID UFF", placeholder="seu.iduff")
            password = st.text_input("Senha", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("Login", type="primary", use_container_width=True)
            with col2:
                limpar_button = st.form_submit_button("Limpar", type="secondary", use_container_width=True)
            
            if login_button and username and password:
                with st.spinner("Autenticando..."):
                    authenticator = UFFAuthenticator(username, password)
                    if authenticator.login():
                        st.session_state.authenticator = authenticator
                        st.session_state.authenticated = True
                        st.session_state.credentials = {'username': username, 'password': password}
                        st.success("✅ Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Falha na autenticação. Verifique suas credenciais.")
    else:
        st.success(f"✅ Autenticado como: {st.session_state.credentials['username']}")
        
        if st.button("Logout", type="secondary", use_container_width=True):
            if st.session_state.authenticator:
                st.session_state.authenticator.logout()
            st.session_state.authenticated = False
            st.session_state.authenticator = None
            st.rerun()
    
    st.markdown("---")
    st.header("⚙️ Configurações")
    
    # Configurações de processamento
    intervalo = st.slider("Intervalo de verificação (s)", 10, 120, INTERVALO_VERIFICACAO)
    timeout = st.slider("Timeout máximo (min)", 5, 120, TIMEOUT_PROCESSAMENTO // 60)
    
    # Pasta de destino
    pasta_destino = st.text_input("Pasta para salvar relatórios", PASTA_RELATORIOS)
    
    st.markdown("---")
    st.header("ℹ️ Informações")
    st.caption(f"Versão: 1.0.0")
    st.caption(f"Última atualização: {st.session_state.ultima_atualizacao or 'N/A'}")

# Conteúdo principal baseado no estado de autenticação
if not st.session_state.authenticated:
    st.warning("🔒 Por favor, faça login para acessar as funcionalidades.")
    
    # Informações sobre o sistema
    with st.expander("ℹ️ Sobre este sistema", expanded=True):
        st.markdown("""
        ### Sistema de Automação de Relatórios UFF
        
        Este sistema automatiza a geração e download de relatórios do sistema de 
        **Administração Acadêmica** da UFF para o **Departamento de Química**.
        
        #### Funcionalidades:
        1. **Autenticação segura** no sistema UFF
        2. **Configuração automatizada** de parâmetros de relatório
        3. **Geração em lote** de relatórios por curso/ingresso
        4. **Monitoramento automático** do processamento
        5. **Download organizado** dos arquivos XLSX
        
        #### Cursos suportados:
        - Química (Licenciatura)
        - Química (Bacharelado) 
        - Química Industrial
        
        #### Parâmetros configuráveis:
        - Localidade (Niterói)
        - Ano/Semestre de ingresso
        - Forma de ingresso (SISU 1ª/2ª Edição)
        - Desdobramento do curso
        """)
        
    st.markdown("---")
    st.info("👈 Use a sidebar para fazer login com suas credenciais UFF.")
    
else:
    # Menu principal (abas)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Gerar Relatório", 
        "🔄 Monitorar", 
        "📊 Relatórios", 
        "⚙️ Configurações Avançadas"
    ])
    
    with tab1:
        st.header("Gerar Novo Relatório")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Seleção do curso
            curso = st.selectbox(
                "Selecione o Curso:",
                ["Química", "Química Industrial"],
                key="curso_select"
            )
            
            # Desdobramento baseado no curso
            if curso == "Química":
                desdobramento = st.selectbox(
                    "Desdobramento:",
                    [
                        "Química (Licenciatura) (12700)",
                        "Química (Bacharelado) (312700)"
                    ],
                    key="desdobramento_select"
                )
            else:  # Química Industrial
                desdobramento = "Química Industrial (12709)"
                st.info(f"**Desdobramento:** {desdobramento}")
            
            # Localidade (fixa)
            st.info(f"**Localidade:** Niterói")
        
        with col2:
            # Ano/Semestre de Ingresso
            ano_col, semestre_col = st.columns(2)
            with ano_col:
                ano = st.selectbox(
                    "Ano:",
                    list(range(2015, 2027)),
                    index=10,  # 2025 como default
                    key="ano_select"
                )
            with semestre_col:
                semestre = st.selectbox(
                    "Semestre:",
                    ["1º", "2º"],
                    key="semestre_select"
                )
            
            # Forma de Ingresso
            forma_ingresso = st.selectbox(
                "Forma de Ingresso:",
                ["SISU 1ª Edição", "SISU 2ª Edição", "-"],
                key="forma_ingresso_select"
            )
            
            # Botão de geração
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Gerar Relatório", type="primary", use_container_width=True):
                # Preparar filtros
                filtros = {
                    'localidade': 'Niterói',
                    'curso': curso,
                    'desdobramento': desdobramento,
                    'ano_semestre_ingresso': f"{ano} / {semestre}",
                    'forma_ingresso': forma_ingresso if forma_ingresso != '-' else '',
                    'tipo_saida': 'xlsx'
                }
                
                # Iniciar processo de geração
                with st.spinner("Enviando solicitação de relatório..."):
                    try:
                        # Criar handler de formulário
                        handler = FormularioHandler(st.session_state.authenticator.session)
                        
                        # Gerar relatório
                        resultado = handler.gerar_relatorio(filtros)
                        
                        if resultado and resultado.get('success'):
                            relatorio_id = resultado.get('relatorio_id')
                            url_relatorio = resultado.get('url_relatorio')
                            
                            # Adicionar à lista de relatórios em processamento
                            novo_relatorio = {
                                'id': relatorio_id,
                                'url': url_relatorio,
                                'filtros': filtros,
                                'status': 'ENVIADO',
                                'timestamp': datetime.now().isoformat(),
                                'caminho_arquivo': None
                            }
                            
                            st.session_state.relatorios_em_processamento.append(novo_relatorio)
                            st.session_state.ultima_atualizacao = datetime.now().strftime("%H:%M:%S")
                            
                            st.success(f"✅ Relatório #{relatorio_id} enviado para processamento!")
                            st.info(f"**URL:** {url_relatorio}")
                            
                            # Mostrar resumo
                            with st.expander("📋 Resumo do Relatório", expanded=True):
                                st.json(filtros, expanded=False)
                        else:
                            st.error(f"❌ Erro ao gerar relatório: {resultado.get('error', 'Erro desconhecido')}")
                            
                    except Exception as e:
                        st.error(f"❌ Erro no processo: {str(e)}")
        
        # Instruções
        with st.expander("ℹ️ Instruções de Uso", expanded=False):
            st.markdown("""
            1. **Selecione o curso** desejado (Química ou Química Industrial)
            2. **Escolha o desdobramento** (para Química: Licenciatura ou Bacharelado)
            3. **Defina o ano/semestre** de ingresso dos alunos
            4. **Selecione a forma de ingresso** (SISU 1ª/2ª Edição ou '-' para todas)
            5. **Clique em "Gerar Relatório"** para enviar a solicitação
            
            ⚠️ **Atenção:** O processamento pode levar vários minutos dependendo da quantidade de dados.
            """)
    
    with tab2:
        st.header("Monitorar Relatórios em Processamento")
        
        if st.session_state.relatorios_em_processamento:
            # Botão para atualizar todos
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if st.button("🔄 Atualizar Status de Todos", type="secondary"):
                    st.rerun()
            with col3:
                if st.button("🗑️ Limpar Concluídos", type="secondary"):
                    # Manter apenas relatórios não concluídos
                    st.session_state.relatorios_em_processamento = [
                        r for r in st.session_state.relatorios_em_processamento 
                        if r.get('status') not in ['PRONTO', 'ERRO', 'CONCLUIDO']
                    ]
                    st.rerun()
            
            st.markdown("---")
            
            # Listar relatórios
            for i, relatorio in enumerate(st.session_state.relatorios_em_processamento):
                with st.container():
                    # Card do relatório
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.markdown(f"### Relatório #{relatorio['id']}")
                        st.caption(f"Enviado em: {relatorio['timestamp'][:19].replace('T', ' ')}")
                        
                        # Exibir filtros principais
                        filtros = relatorio.get('filtros', {})
                        st.write(f"**Curso:** {filtros.get('curso', 'N/A')}")
                        st.write(f"**Ingresso:** {filtros.get('ano_semestre_ingresso', 'N/A')}")
                    
                    with col2:
                        # Status com cor
                        status = relatorio.get('status', 'DESCONHECIDO')
                        if status == 'PRONTO':
                            st.markdown('<p class="status-pronto">✅ PRONTO</p>', unsafe_allow_html=True)
                        elif status in ['ENVIADO', 'EM_PROCESSAMENTO']:
                            st.markdown('<p class="status-processando">⏳ PROCESSANDO</p>', unsafe_allow_html=True)
                        elif status == 'ERRO':
                            st.markdown('<p class="status-erro">❌ ERRO</p>', unsafe_allow_html=True)
                        else:
                            st.write(f"Status: {status}")
                    
                    with col3:
                        # Botão de ação
                        if status == 'PRONTO':
                            if st.button("⬇️ Baixar", key=f"download_{i}"):
                                with st.spinner("Baixando..."):
                                    automator = RelatorioUFFAutomator(st.session_state.authenticator.session)
                                    
                                    # Verificar status atual
                                    status_info = automator.verificar_status_relatorio(relatorio['id'])
                                    if status_info and status_info.get('download_url'):
                                        caminho = automator.baixar_relatorio(status_info, pasta_destino)
                                        if caminho:
                                            relatorio['caminho_arquivo'] = caminho
                                            relatorio['status'] = 'CONCLUIDO'
                                            
                                            # Mover para concluídos
                                            st.session_state.relatorios_concluidos.append(relatorio)
                                            st.session_state.relatorios_em_processamento.pop(i)
                                            
                                            st.success(f"✅ Baixado: {os.path.basename(caminho)}")
                                            st.rerun()
                        elif status == 'ENVIADO':
                            if st.button("🔍 Verificar", key=f"check_{i}"):
                                with st.spinner("Verificando status..."):
                                    automator = RelatorioUFFAutomator(st.session_state.authenticator.session)
                                    status_info = automator.verificar_status_relatorio(relatorio['id'])
                                    
                                    if status_info:
                                        relatorio['status'] = status_info.get('status', 'DESCONHECIDO')
                                        relatorio['status_info'] = status_info
                                        st.rerun()
                    
                    # Barra de progresso e detalhes
                    if relatorio.get('status') in ['ENVIADO', 'EM_PROCESSAMENTO']:
                        # Iniciar monitoramento automático
                        if st.button("▶️ Monitorar Automaticamente", key=f"monitor_{i}"):
                            placeholder = st.empty()
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            def callback_progresso(progresso, mensagem, concluido):
                                progress_bar.progress(progresso)
                                status_text.text(mensagem)
                                if concluido:
                                    relatorio['status'] = 'PRONTO'
                            
                            automator = RelatorioUFFAutomator(st.session_state.authenticator.session)
                            resultado = automator.aguardar_conclusao(
                                relatorio['id'],
                                callback_progresso=callback_progresso,
                                intervalo=intervalo,
                                timeout=timeout * 60
                            )
                            
                            if resultado:
                                relatorio['status'] = 'PRONTO'
                                relatorio['status_info'] = resultado
                                st.rerun()
                    
                    # Mostrar informações detalhadas
                    if relatorio.get('status_info'):
                        with st.expander("📋 Detalhes do Status", expanded=False):
                            st.json(relatorio['status_info'], expanded=False)
                    
                    st.markdown("---")
        
        else:
            st.info("📭 Nenhum relatório em processamento. Gere um novo relatório na aba anterior.")
    
    with tab3:
        st.header("Relatórios Concluídos e Baixados")
        
        if st.session_state.relatorios_concluidos:
            # Estatísticas
            total = len(st.session_state.relatorios_concluidos)
            concluidos = len([r for r in st.session_state.relatorios_concluidos if r.get('caminho_arquivo')])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Relatórios", total)
            with col2:
                st.metric("Baixados com Sucesso", concluidos)
            with col3:
                st.metric("Taxa de Sucesso", f"{(concluidos/total*100):.1f}%" if total > 0 else "0%")
            
            st.markdown("---")
            
            # Tabela de relatórios
            dados_tabela = []
            for relatorio in st.session_state.relatorios_concluidos:
                dados_tabela.append({
                    'ID': relatorio['id'],
                    'Curso': relatorio.get('filtros', {}).get('curso', 'N/A'),
                    'Ingresso': relatorio.get('filtros', {}).get('ano_semestre_ingresso', 'N/A'),
                    'Status': relatorio.get('status', 'N/A'),
                    'Arquivo': os.path.basename(relatorio['caminho_arquivo']) if relatorio.get('caminho_arquivo') else 'Não baixado',
                    'Data': relatorio['timestamp'][:10]
                })
            
            if dados_tabela:
                df = pd.DataFrame(dados_tabela)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Opções de exportação
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📄 Exportar Lista como CSV"):
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=csv,
                            file_name=f"relatorios_concluidos_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                
                # Lista detalhada
                st.markdown("### 📁 Arquivos Baixados")
                for relatorio in st.session_state.relatorios_concluidos:
                    if relatorio.get('caminho_arquivo'):
                        with st.expander(f"📄 {os.path.basename(relatorio['caminho_arquivo'])}", expanded=False):
                            col1, col2, col3 = st.columns([3, 2, 1])
                            
                            with col1:
                                st.write(f"**ID:** {relatorio['id']}")
                                st.write(f"**Caminho:** {relatorio['caminho_arquivo']}")
                                st.write(f"**Tamanho:** {os.path.getsize(relatorio['caminho_arquivo']) / 1024 / 1024:.2f} MB")
                            
                            with col2:
                                # Verificar conteúdo do Excel
                                try:
                                    df_excel = pd.read_excel(relatorio['caminho_arquivo'], nrows=5)
                                    st.write(f"**Colunas:** {len(df_excel.columns)}")
                                    st.write(f"**Linhas (primeiras 5):**")
                                    st.dataframe(df_excel, hide_index=True)
                                except Exception as e:
                                    st.warning(f"Não foi possível ler o arquivo: {str(e)}")
                            
                            with col3:
                                # Botões de ação
                                if st.button("🗑️", key=f"delete_{relatorio['id']}"):
                                    try:
                                        os.remove(relatorio['caminho_arquivo'])
                                        st.success("Arquivo excluído!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao excluir: {str(e)}")
        else:
            st.info("📭 Nenhum relatório concluído ainda. Os relatórios aparecerão aqui após serem baixados.")
    
    with tab4:
        st.header("Configurações Avançadas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Configurações de Sistema")
            
            # Modo debug
            debug_mode = st.toggle("Modo Debug", value=False)
            if debug_mode:
                st.session_state.debug = True
                st.info("Modo debug ativado. Logs detalhados serão exibidos.")
            else:
                st.session_state.debug = False
            
            # Limpar cache
            if st.button("🧹 Limpar Cache da Sessão", type="secondary"):
                for key in list(st.session_state.keys()):
                    if key not in ['authenticated', 'credentials']:
                        del st.session_state[key]
                st.success("Cache limpo!")
                st.rerun()
        
        with col2:
            st.subheader("Informações da Sessão")
            
            if st.session_state.authenticator:
                st.write(f"**Usuário:** {st.session_state.credentials['username']}")
                st.write(f"**Autenticado desde:** {st.session_state.ultima_atualizacao or 'N/A'}")
                
                # Verificar sessão
                if st.button("🔍 Verificar Sessão", type="secondary"):
                    if st.session_state.authenticator.check_session():
                        st.success("✅ Sessão válida")
                    else:
                        st.error("❌ Sessão expirada")
            
            # Logs
            with st.expander("📝 Últimos Logs", expanded=False):
                st.code("""
                [INFO] Sistema iniciado
                [INFO] Usuário autenticado: usuario@id.uff.br
                [INFO] Relatório #60927 enviado para processamento
                [INFO] Monitorando status do relatório...
                """)

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
        logger.info(f"Sistema iniciado para usuário: {st.session_state.credentials['username']}")
