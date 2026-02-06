# main_corrigido.py
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
from gerador_relatorios_corrigido import (
    GeradorRelatoriosCorrigido, 
    InterfaceProgressoMelhorada
)

# Configurações
PASTA_RELATORIOS = 'relatorios'

# Configurar página
st.set_page_config(
    page_title="Automação de Relatórios UFF - Química (Corrigido)",
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
        'consulta_concluida': False,
        'resultados_geracao': {},
        'geracao_em_andamento': False,
        'interface_progresso': None
    }
    
    for key, value in estados.items():
        if key not in st.session_state:
            st.session_state[key] = value

inicializar_estado()

# Interface principal
st.title("📊 Sistema de Análise de Evasão - UFF (Corrigido)")
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
    st.markdown("### 📋 Progresso")
    
    etapas = [
        ("1. Configuração", 1, st.session_state.etapa_atual >= 1),
        ("2. Geração", 2, st.session_state.etapa_atual >= 2),
        ("3. Resultados", 3, st.session_state.etapa_atual >= 3)
    ]
    
    cols = st.columns(3)
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
        st.markdown("## 🎯 Configuração da Análise")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📅 Período")
            
            # Período inicial
            ano_inicial = st.number_input("Ano Inicial", min_value=2000, max_value=2030, value=2025)
            semestre_inicial = st.selectbox("Semestre Inicial", [1, 2], format_func=lambda x: f"{x}º Semestre")
            
            # Período final
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
            
            st.markdown("---")
            st.subheader("⚙️ Configurações Avançadas")
            
            intervalo_verificacao = st.slider(
                "Intervalo entre verificações (segundos)",
                min_value=10,
                max_value=120,
                value=30,
                help="Tempo entre verificações do status do relatório"
            )
        
        # Calcular total
        if st.button("📊 Calcular Total de Relatórios", type="secondary"):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso")
            else:
                periodo_inicial = f"{ano_inicial}{semestre_inicial}"
                periodo_final = f"{ano_final}{semestre_final}"
                
                gerador = GeradorRelatoriosCorrigido(st.session_state.authenticator.session)
                periodos = gerador.processar_periodos_intervalo(periodo_inicial, periodo_final)
                
                total = len(cursos_selecionados) * len(periodos)
                
                st.info(f"""
                **Resumo da configuração:**
                
                **Cursos selecionados:**
                {chr(10).join(f'- {curso}' for curso in cursos_selecionados)}
                
                **Períodos a processar:**
                {chr(10).join(f'- {p[:4]}/{p[4:]}' for p in periodos)}
                
                **Total de relatórios:** {total}
                
                **Tempo estimado:** ~{total * 2} minutos
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
                    'final': f"{ano_final}{semestre_final}",
                    'intervalo_verificacao': intervalo_verificacao
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
                st.markdown(f"**Forma de Ingresso:** SISU 1ª e 2ª Edição (automático por semestre)")
            
            with col2:
                cursos = st.session_state.selected_cursos
                st.markdown("**Cursos:**")
                for curso in cursos:
                    st.markdown(f"- {curso}")
        
        # Calcular total
        gerador = GeradorRelatoriosCorrigido(st.session_state.authenticator.session)
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
        
        **Isso garantirá que cada relatório contenha APENAS os dados do curso/período especificado.**
        """)
        
        # Controles
        if not st.session_state.geracao_em_andamento:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Iniciar Geração de Relatórios", type="primary", use_container_width=True):
                    st.session_state.geracao_em_andamento = True
                    st.session_state.interface_progresso = InterfaceProgressoMelhorada()
                    st.rerun()
            
            with col2:
                if st.button("🔄 Alterar Configuração", type="secondary", use_container_width=True):
                    st.session_state.etapa_atual = 1
                    st.rerun()
        
        # Geração em andamento
        if st.session_state.geracao_em_andamento:
            if not st.session_state.interface_progresso:
                st.session_state.interface_progresso = InterfaceProgressoMelhorada()
            
            interface = st.session_state.interface_progresso
            interface.inicializar(total_relatorios)
            
            # Callback para progresso
            def callback_progresso(mensagem, progresso):
                interface.atualizar(mensagem, progresso)
            
            # Iniciar geração
            gerador = GeradorRelatoriosCorrigido(st.session_state.authenticator.session)
            cursos_config = gerador.obter_cursos_configurados(st.session_state.selected_cursos)
            
            resultados = {}
            
            for curso_config in cursos_config:
                curso_nome = curso_config['nome']
                resultados[curso_nome] = []
                
                for periodo in periodos_lista:
                    inicio_tarefa = time.time()
                    
                    # Determinar forma de ingresso
                    forma_ingresso = gerador._determinar_forma_ingresso(periodo)
                    
                    # Gerar relatório
                    resultado = gerador.gerar_relatorio_corretamente(
                        curso_config,
                        periodo,
                        forma_ingresso,
                        callback_progresso
                    )
                    
                    # Calcular tempo
                    tempo_decorrido = time.time() - inicio_tarefa
                    tempo_formatado = f"{tempo_decorrido:.1f}s"
                    
                    # Registrar resultado
                    resultados[curso_nome].append(resultado)
                    
                    # Atualizar interface
                    if resultado.get('success'):
                        interface.adicionar_resultado(
                            curso_nome,
                            periodo,
                            True,
                            "Relatório gerado com sucesso",
                            tempo_formatado
                        )
                    else:
                        interface.adicionar_resultado(
                            curso_nome,
                            periodo,
                            False,
                            resultado.get('error', 'Erro desconhecido'),
                            tempo_formatado
                        )
                    
                    # Aguardar entre requisições
                    time.sleep(5)
            
            # Finalizar
            st.session_state.resultados_geracao = resultados
            st.session_state.consulta_concluida = True
            st.session_state.geracao_em_andamento = False
            
            interface.atualizar("✅ Geração concluída!", 100)
            time.sleep(2)
            
            # Exibir resultados
            interface.exibir_resultados_finais()
            
            # Botão para continuar
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Processar Dados e Gerar Estatísticas", type="primary", use_container_width=True):
                    st.session_state.etapa_atual = 3
                    st.rerun()
            
            with col2:
                if st.button("🔄 Gerar Novamente", type="secondary", use_container_width=True):
                    st.session_state.consulta_concluida = False
                    st.session_state.resultados_geracao = {}
                    st.session_state.geracao_em_andamento = False
                    st.rerun()
    
    # ETAPA 3 - RESULTADOS
    elif st.session_state.etapa_atual == 3:
        st.markdown("## 📊 Resultados e Estatísticas")
        
        if not st.session_state.resultados_geracao:
            st.error("Nenhum dado para processar.")
            if st.button("🔙 Voltar para Geração"):
                st.session_state.etapa_atual = 2
                st.rerun()
        else:
            # Processar dados
            from gerador_relatorios_corrigido import ProcessadorDadosOtimizado
            
            processador = ProcessadorDadosOtimizado()
            dados_consolidados = processador.processar_todos_relatorios(
                st.session_state.resultados_geracao
            )
            
            # Mostrar resumo
            resumo = dados_consolidados.get('resumo_geral', {})
            
            st.success(f"✅ Dados processados: {resumo.get('total_matriculas', 0)} matrículas analisadas")
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Cursos", resumo.get('total_cursos', 0))
            with col2:
                st.metric("Períodos", resumo.get('total_periodos', 0))
            with col3:
                st.metric("Matrículas", resumo.get('total_matriculas', 0))
            with col4:
                cancelamentos = resumo.get('total_cancelamentos', 0)
                total = resumo.get('total_matriculas', 1)
                percentual = (cancelamentos / total * 100) if total > 0 else 0
                st.metric("Cancelamentos", f"{cancelamentos} ({percentual:.1f}%)")
            
            # Tabela por curso
            st.markdown("### 📈 Estatísticas por Curso")
            
            dados_tabela = []
            for curso_nome, dados_curso in dados_consolidados.get('por_curso', {}).items():
                totais = dados_curso['totais']
                total_mat = totais['matriculas']
                
                if total_mat > 0:
                    dados_tabela.append({
                        'Curso': curso_nome,
                        'Matrículas': total_mat,
                        'Ativos': totais['ativos'],
                        '% Ativos': (totais['ativos'] / total_mat * 100),
                        'Cancelamentos': totais['cancelamentos'],
                        '% Cancelamentos': (totais['cancelamentos'] / total_mat * 100),
                        'Formados': totais['formados'],
                        '% Formados': (totais['formados'] / total_mat * 100),
                        'Ampla Concorrência': totais['ampla_concorrencia'],
                        'Ações Afirmativas': totais['acoes_afirmativas']
                    })
            
            if dados_tabela:
                df = pd.DataFrame(dados_tabela)
                st.dataframe(df.style.format({
                    '% Ativos': '{:.1f}%',
                    '% Cancelamentos': '{:.1f}%',
                    '% Formados': '{:.1f}%'
                }), use_container_width=True)
            
            # Botões
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Novo Processo", type="secondary", use_container_width=True):
                    st.session_state.selected_cursos = []
                    st.session_state.selected_periodos = {}
                    st.session_state.consulta_concluida = False
                    st.session_state.resultados_geracao = {}
                    st.session_state.etapa_atual = 1
                    st.rerun()
            
            with col2:
                if st.button("📥 Gerar Planilha Detalhada", type="primary", use_container_width=True):
                    # Gerar planilha
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    caminho = os.path.join(PASTA_RELATORIOS, f"estatisticas_detalhadas_{timestamp}.xlsx")
                    
                    with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                        # Resumo
                        df_resumo = pd.DataFrame(dados_tabela)
                        df_resumo.to_excel(writer, sheet_name='RESUMO', index=False)
                        
                        # Detalhes por período
                        dados_detalhes = []
                        for curso_nome, dados_curso in dados_consolidados.get('por_curso', {}).items():
                            for periodo, dados_periodo in dados_curso['periodos'].items():
                                periodo_display = f"{periodo[:4]}/{periodo[4:]}"
                                
                                linha = {
                                    'Curso': curso_nome,
                                    'Período': periodo_display,
                                    'Total': dados_periodo['total_registros'],
                                    'Ativos': dados_periodo['matriculas_ativas'],
                                    'Cancelamentos': dados_periodo['total_cancelamentos'],
                                    'Ampla Concorrência': dados_periodo['ampla_concorrencia'],
                                    'Ações Afirmativas': dados_periodo['acoes_afirmativas']
                                }
                                
                                dados_detalhes.append(linha)
                        
                        if dados_detalhes:
                            df_detalhes = pd.DataFrame(dados_detalhes)
                            df_detalhes.to_excel(writer, sheet_name='DETALHES', index=False)
                    
                    st.success(f"✅ Planilha gerada: {caminho}")
                    
                    # Botão de download
                    with open(caminho, 'rb') as f:
                        st.download_button(
                            label="📥 Baixar Planilha",
                            data=f,
                            file_name=os.path.basename(caminho),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

# Rodapé
st.markdown("---")
st.caption(f"🕒 {datetime.now().strftime('%H:%M:%S')} | 📊 Departamento de Química - UFF | 🔒 Sistema de automação seguro")

# Inicialização
if __name__ == "__main__":
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
