# main_otimizado.py
import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd
import time
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import UFFAuthenticator
from gerador_relatorios_otimizado import (
    GeradorRelatoriosOtimizado, 
    ProcessadorDadosOtimizado,
    InterfaceProgresso
)

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
    """Inicializa o estado da sessão"""
    estados_padrao = {
        'authenticated': False,
        'authenticator': None,
        'username': '',
        'selected_cursos': [],
        'selected_periodos': {},
        'etapa_atual': 1,
        'consulta_concluida': False,
        'resultados_geracao': {},
        'dados_consolidados': None,
        'planilha_gerada': False,
        'caminho_planilha': '',
        'geracao_em_andamento': False,
        'progress_bar': None,
        'status_text': None,
        'tabela_resultados': []
    }
    
    for key, value in estados_padrao.items():
        if key not in st.session_state:
            st.session_state[key] = value

inicializar_estado()

# Funções auxiliares
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

def converter_periodo_para_valor(periodo_texto):
    """Converte texto de período para valor do sistema"""
    ano, semestre = parse_periodo_texto(periodo_texto)
    if ano and semestre:
        return f"{ano}{semestre}"
    return None

# Interface principal
st.title("📊 Sistema de Análise de Evasão - UFF")
st.markdown("---")

# ETAPA 1 - LOGIN
if not st.session_state.authenticated:
    st.markdown("### 🔐 Login no Sistema Acadêmico da UFF")
    
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
    
    st.info("""
    **Sistema de Análise de Evasão - Departamento de Química UFF**
    
    Este sistema automatiza a geração e análise de relatórios de ingressantes do SISU.
    """)

else:
    # Menu principal
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
    
    # Barra de progresso das etapas
    st.markdown("### 📋 Progresso do Processo")
    
    # Determinar etapa atual
    if not st.session_state.selected_periodos:
        st.session_state.etapa_atual = 1
    elif not st.session_state.consulta_concluida:
        st.session_state.etapa_atual = 2
    elif not st.session_state.planilha_gerada:
        st.session_state.etapa_atual = 3
    else:
        st.session_state.etapa_atual = 4
    
    etapas = [
        ("1. Configuração", 1, st.session_state.etapa_atual >= 1),
        ("2. Geração", 2, st.session_state.etapa_atual >= 2),
        ("3. Processamento", 3, st.session_state.etapa_atual >= 3),
        ("4. Resultados", 4, st.session_state.etapa_atual >= 4)
    ]
    
    cols = st.columns(4)
    for col, (nome, num, concluida) in zip(cols, etapas):
        with col:
            st.markdown(f"**{nome}**")
            if concluida:
                st.success("✅")
            elif st.session_state.etapa_atual == num:
                st.info("🔄")
            else:
                st.info("⏳")
    
    st.markdown("---")
    
    # ETAPA 1 - CONFIGURAÇÃO
    if st.session_state.etapa_atual == 1:
        st.markdown("## 🎯 Etapa 1 - Configuração")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📅 Período de Análise")
            
            # Período inicial
            ano_inicial = st.number_input(
                "Ano Inicial",
                min_value=2010,
                max_value=2030,
                value=2025,
                step=1
            )
            semestre_inicial = st.selectbox(
                "Semestre Inicial",
                options=[1, 2],
                format_func=lambda x: f"{x}º Semestre"
            )
            
            # Período final
            ano_final = st.number_input(
                "Ano Final",
                min_value=2010,
                max_value=2030,
                value=2025,
                step=1
            )
            semestre_final = st.selectbox(
                "Semestre Final",
                options=[1, 2],
                index=1,
                format_func=lambda x: f"{x}º Semestre"
            )
            
            # Validar intervalo
            if ano_final < ano_inicial or (ano_final == ano_inicial and semestre_final < semestre_inicial):
                st.error("Período final deve ser igual ou posterior ao inicial")
        
        with col2:
            st.subheader("📚 Cursos para Análise")
            
            cursos_disponiveis = [
                'Química (Licenciatura)',
                'Química (Bacharelado)',
                'Química Industrial'
            ]
            
            cursos_selecionados = st.multiselect(
                "Selecione os cursos:",
                options=cursos_disponiveis,
                default=cursos_disponiveis,
                help="Selecione os cursos para análise"
            )
            
            if cursos_selecionados:
                st.success(f"✅ {len(cursos_selecionados)} curso(s) selecionado(s)")
        
        # Calcular total de relatórios
        if st.button("📊 Calcular Total de Relatórios", type="secondary"):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso")
            else:
                periodo_inicial_valor = f"{ano_inicial}{semestre_inicial}"
                periodo_final_valor = f"{ano_final}{semestre_final}"
                
                # Calcular períodos
                gerador = GeradorRelatoriosOtimizado(st.session_state.authenticator.session)
                periodos_lista = gerador.processar_periodos_intervalo(
                    periodo_inicial_valor, 
                    periodo_final_valor
                )
                
                total_relatorios = len(cursos_selecionados) * len(periodos_lista)
                
                st.info(f"""
                **Resumo da configuração:**
                - Cursos: {len(cursos_selecionados)}
                - Períodos: {len(periodos_lista)} ({periodo_inicial_valor[:4]}/{periodo_inicial_valor[4:]} a {periodo_final_valor[:4]}/{periodo_final_valor[4:]})
                - **Total de relatórios a gerar:** {total_relatorios}
                """)
        
        # Botão para confirmar
        st.markdown("---")
        
        if st.button("✅ Confirmar e Prosseguir para Geração", type="primary", use_container_width=True):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso")
            else:
                # Salvar configuração
                st.session_state.selected_cursos = cursos_selecionados
                st.session_state.selected_periodos = {
                    'inicial': f"{ano_inicial}{semestre_inicial}",
                    'final': f"{ano_final}{semestre_final}",
                    'inicial_display': f"{ano_inicial}/{semestre_inicial}º",
                    'final_display': f"{ano_final}/{semestre_final}º"
                }
                
                logger.info(f"Configuração salva: {len(cursos_selecionados)} cursos, período {ano_inicial}{semestre_inicial} a {ano_final}{semestre_final}")
                
                st.session_state.etapa_atual = 2
                st.success("✅ Configuração salva com sucesso!")
                time.sleep(1)
                st.rerun()
    
    # ETAPA 2 - GERAÇÃO DE RELATÓRIOS
    elif st.session_state.etapa_atual == 2:
        st.markdown("## 🔍 Etapa 2 - Geração de Relatórios")
        
        # Mostrar configuração atual
        with st.expander("📋 Configuração Atual", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                periodos = st.session_state.selected_periodos
                st.markdown(f"**Período:** {periodos['inicial_display']} a {periodos['final_display']}")
                st.markdown(f"**Localidade:** Niterói")
                st.markdown(f"**Formas de Ingresso:** SISU 1ª e 2ª Edição")
            
            with col2:
                cursos = st.session_state.selected_cursos
                st.markdown("**Cursos:**")
                for curso in cursos:
                    st.markdown(f"- {curso}")
        
        # Calcular total
        gerador = GeradorRelatoriosOtimizado(st.session_state.authenticator.session)
        periodos_lista = gerador.processar_periodos_intervalo(
            st.session_state.selected_periodos['inicial'],
            st.session_state.selected_periodos['final']
        )
        
        total_relatorios = len(st.session_state.selected_cursos) * len(periodos_lista)
        
        st.info(f"""
        **Pronto para gerar {total_relatorios} relatório(s):**
        - Para cada curso, será gerado 1 relatório por período
        - Cada relatório inclui **todas as modalidades** (Ampla Concorrência + Ações Afirmativas)
        - O sistema separará as modalidades automaticamente após o download
        - Tempo estimado: ~2-5 minutos por relatório
        """)
        
        # Controles de geração
        if not st.session_state.geracao_em_andamento:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Iniciar Geração de Relatórios", type="primary", use_container_width=True):
                    st.session_state.geracao_em_andamento = True
                    logger.info(f"Iniciando geração de {total_relatorios} relatórios")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.etapa_atual = 1
                    st.rerun()
        
        # Se geração em andamento
        if st.session_state.geracao_em_andamento:
            # Criar os elementos de UI diretamente no contexto do Streamlit
            progress_bar = st.progress(0)
            status_text = st.empty()
            resultados_container = st.container()
            
            # Criar colunas para contadores
            col_status, col_sucesso, col_erro = st.columns(3)
            with col_status:
                st.markdown("**Status**")
                status_counter = st.empty()
            with col_sucesso:
                st.markdown("**✅ Sucesso**")
                sucesso_counter = st.empty()
            with col_erro:
                st.markdown("**❌ Erro**")
                erro_counter = st.empty()
            
            # Inicializar contadores
            status_counter.markdown("**Total:** 0")
            sucesso_counter.markdown("**✅ 0**")
            erro_counter.markdown("**❌ 0**")
            
            # Inicializar lista de resultados
            tabela_resultados = []
            
            # Função de callback para progresso
            def callback_progresso(mensagem, progresso):
                progress_bar.progress(progresso / 100)
                status_text.text(mensagem)
            
            # Função para adicionar resultado
            def adicionar_resultado(curso, periodo, sucesso, mensagem=None):
                periodo_display = f"{periodo[:4]}/{periodo[4:]}" if len(periodo) == 5 else periodo
                
                if sucesso:
                    emoji = "✅"
                    status = "Sucesso"
                else:
                    emoji = "❌"
                    status = "Erro"
                
                tabela_resultados.append({
                    'Curso': curso,
                    'Período': periodo_display,
                    'Status': f"{emoji} {status}",
                    'Detalhe': mensagem or ''
                })
                
                # Atualizar contadores
                sucessos = sum(1 for r in tabela_resultados if '✅' in r['Status'])
                erros = sum(1 for r in tabela_resultados if '❌' in r['Status'])
                total = len(tabela_resultados)
                
                status_counter.markdown(f"**Total:** {total}")
                sucesso_counter.markdown(f"**✅ {sucessos}**")
                erro_counter.markdown(f"**❌ {erros}**")
            
            # Gerar relatórios
            gerador = GeradorRelatoriosOtimizado(st.session_state.authenticator.session)
            
            # Obter cursos configurados
            cursos_config = gerador.obter_cursos_predefinidos(st.session_state.selected_cursos)
            
            # Processar cada curso e período
            resultados = {}
            sucessos = 0
            erros = 0
            
            for i, curso_config in enumerate(cursos_config):
                curso_nome = curso_config['nome']
                resultados[curso_nome] = []
                
                for periodo in periodos_lista:
                    # Atualizar status
                    callback_progresso(
                        f"Gerando {curso_nome} - {periodo[:4]}/{periodo[4:]}",
                        0
                    )
                    
                    # Determinar forma de ingresso
                    forma_ingresso = gerador._determinar_forma_ingresso(periodo)
                    logger.info(f"Gerando relatório: {curso_nome} - {periodo} - Forma ingresso: {forma_ingresso}")
                    
                    # Gerar relatório
                    resultado = gerador.gerar_relatorio_individual_com_progresso(
                        curso_config,
                        periodo,
                        forma_ingresso,
                        callback_progresso
                    )
                    
                    # Adicionar resultado
                    resultados[curso_nome].append(resultado)
                    
                    # Atualizar interface
                    if resultado.get('success'):
                        sucessos += 1
                        adicionar_resultado(
                            curso_nome,
                            periodo,
                            True,
                            "Relatório gerado com sucesso"
                        )
                    else:
                        erros += 1
                        adicionar_resultado(
                            curso_nome,
                            periodo,
                            False,
                            resultado.get('error', 'Erro desconhecido')
                        )
                    
                    # Aguardar entre requisições
                    time.sleep(3)
            
            # Finalizar
            st.session_state.resultados_geracao = resultados
            st.session_state.consulta_concluida = True
            st.session_state.geracao_em_andamento = False
            
            logger.info(f"Geração concluída: {sucessos} sucessos, {erros} erros")
            
            # Exibir resumo
            callback_progresso("✅ Geração concluída!", 100)
            time.sleep(2)
            
            # Mostrar tabela de resultados
            with resultados_container:
                if tabela_resultados:
                    st.markdown("### 📋 Resultados Detalhados")
                    df = pd.DataFrame(tabela_resultados)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Botão para continuar
            if st.button("📊 Processar Dados e Gerar Estatísticas", type="primary", use_container_width=True):
                st.session_state.etapa_atual = 3
                st.rerun()
    
    # ETAPA 3 - PROCESSAMENTO DE DADOS
    elif st.session_state.etapa_atual == 3:
        st.markdown("## ⚙️ Etapa 3 - Processamento de Dados")
        
        if not st.session_state.resultados_geracao:
            st.error("Nenhum dado para processar. Volte para a Etapa 2.")
            if st.button("🔙 Voltar para Etapa 2"):
                st.session_state.etapa_atual = 2
                st.rerun()
        else:
            # Contar relatórios bem-sucedidos
            total_sucessos = 0
            total_relatorios = 0
            
            for curso_nome, resultados in st.session_state.resultados_geracao.items():
                for resultado in resultados:
                    total_relatorios += 1
                    if resultado.get('success'):
                        total_sucessos += 1
            
            st.info(f"""
            **{total_sucessos} de {total_relatorios}** relatórios foram baixados com sucesso.
            
            O sistema irá agora:
            1. Ler e analisar cada arquivo XLSX
            2. Separar dados por modalidade de ingresso
            3. Classificar situações e cancelamentos
            4. Calcular percentuais e estatísticas
            5. Gerar planilha consolidada
            """)
            
            # Botão para processar
            if st.button("▶️ Iniciar Processamento", type="primary", use_container_width=True):
                with st.spinner("Processando dados..."):
                    # Processar dados
                    processador = ProcessadorDadosOtimizado()
                    dados_consolidados = processador.processar_todos_relatorios(
                        st.session_state.resultados_geracao
                    )
                    
                    # Gerar planilha
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    caminho_planilha = os.path.join(PASTA_RELATORIOS, f"estatisticas_evasao_{timestamp}.xlsx")
                    
                    # Criar planilha simplificada
                    with pd.ExcelWriter(caminho_planilha, engine='xlsxwriter') as writer:
                        # RESUMO GERAL
                        dados_resumo = []
                        for curso_nome, dados_curso in dados_consolidados['por_curso'].items():
                            totais = dados_curso['totais']
                            dados_resumo.append({
                                'Curso': curso_nome,
                                'Total Matrículas': totais['matriculas'],
                                'Matrículas Ativas': totais['ativos'],
                                'Cancelamentos': totais['cancelamentos'],
                                '% Cancelamentos': round((totais['cancelamentos'] / totais['matriculas'] * 100), 2) if totais['matriculas'] > 0 else 0,
                                'Formados': totais['formados'],
                                '% Formados': round((totais['formados'] / totais['matriculas'] * 100), 2) if totais['matriculas'] > 0 else 0,
                                'Ampla Concorrência': totais['ampla_concorrencia'],
                                'Ações Afirmativas': totais['acoes_afirmativas']
                            })
                        
                        df_resumo = pd.DataFrame(dados_resumo)
                        df_resumo.to_excel(writer, sheet_name='RESUMO GERAL', index=False)
                        
                        # DETALHES POR PERÍODO
                        dados_detalhes = []
                        for curso_nome, dados_curso in dados_consolidados['por_curso'].items():
                            for periodo, dados_periodo in dados_curso['periodos'].items():
                                periodo_display = f"{periodo[:4]}/{periodo[4:]}"
                                
                                linha = {
                                    'Curso': curso_nome,
                                    'Período': periodo_display,
                                    'Total': dados_periodo['total_registros'],
                                    'Ativos': dados_periodo['matriculas_ativas'],
                                    'Cancelamentos': dados_periodo['total_cancelamentos'],
                                    '% Cancelamentos': dados_periodo.get('percentual_cancelamentos', 0),
                                    'Ampla Concorrência': dados_periodo['ampla_concorrencia'],
                                    '% Ampla': dados_periodo.get('percentual_ampla', 0),
                                    'Ações Afirmativas': dados_periodo['acoes_afirmativas'],
                                    '% Ações': dados_periodo.get('percentual_acoes', 0)
                                }
                                
                                # Adicionar categorias de situação
                                for cat, dados_cat in dados_periodo['categorias_situacao'].items():
                                    linha[f'{cat}'] = dados_cat['quantidade']
                                    linha[f'% {cat}'] = dados_cat['percentual']
                                
                                dados_detalhes.append(linha)
                        
                        if dados_detalhes:
                            df_detalhes = pd.DataFrame(dados_detalhes)
                            df_detalhes.to_excel(writer, sheet_name='DETALHES', index=False)
                    
                    st.session_state.dados_consolidados = dados_consolidados
                    st.session_state.caminho_planilha = caminho_planilha
                    st.session_state.planilha_gerada = True
                    st.session_state.etapa_atual = 4
                    
                    st.success("✅ Processamento concluído!")
                    time.sleep(1)
                    st.rerun()
            
            if st.button("🔙 Voltar para Etapa 2", type="secondary", use_container_width=True):
                st.session_state.etapa_atual = 2
                st.rerun()
    
    # ETAPA 4 - RESULTADOS
    elif st.session_state.etapa_atual == 4:
        st.markdown("## 📊 Etapa 4 - Resultados")
        
        if st.session_state.planilha_gerada and st.session_state.caminho_planilha:
            st.success("✅ Planilha gerada com sucesso!")
            
            # Mostrar resumo
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
            
            # Preview da planilha
            with st.expander("🔍 Visualizar Dados", expanded=True):
                try:
                    df_resumo = pd.read_excel(st.session_state.caminho_planilha, sheet_name='RESUMO GERAL')
                    st.dataframe(df_resumo, use_container_width=True)
                except Exception as e:
                    st.warning(f"Não foi possível visualizar os dados: {str(e)}")
            
            # Botões de controle
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Novo Processo", type="secondary", use_container_width=True):
                    # Limpar dados do processo atual
                    st.session_state.selected_cursos = []
                    st.session_state.selected_periodos = {}
                    st.session_state.consulta_concluida = False
                    st.session_state.resultados_geracao = {}
                    st.session_state.dados_consolidados = None
                    st.session_state.planilha_gerada = False
                    st.session_state.caminho_planilha = ''
                    st.session_state.etapa_atual = 1
                    st.rerun()
            
            with col2:
                if st.button("📈 Gerar Gráficos", type="primary", use_container_width=True):
                    st.info("Funcionalidade de gráficos será implementada em breve.")

# Rodapé
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col1:
    st.caption(f"🕒 {datetime.now().strftime('%H:%M:%S')}")
with footer_col2:
    st.caption("📊 Departamento de Química - UFF")
with footer_col3:
    st.caption("🔒 Sistema de automação seguro")

# Inicialização
if __name__ == "__main__":
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
