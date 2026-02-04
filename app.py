"""
Aplicativo Streamlit para Cálculo de Evasão - Cursos de Química UFF
Este aplicativo realiza login no sistema acadêmico da UFF, consulta relatórios
e gera automaticamente planilhas de cálculo de evasão.
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
import re
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Cálculo de Evasão - Química UFF",
    page_icon="📊",
    layout="wide"
)

# URLs do sistema
BASE_URL = "https://app.uff.br"
LOGIN_URL = "https://app.uff.br/auth/realms/master/login-actions/authenticate"
ADMIN_ACAD_URL = "https://app.uff.br/graduacao/administracaoacademica"
RELATORIOS_URL = f"{ADMIN_ACAD_URL}/relatorios/listagens_alunos"

# Constantes de cursos e desdobramentos
CURSOS = {
    "Química": {
        "codigo": "quimica",
        "desdobramentos": {
            "Licenciatura": "12700",
            "Bacharelado": "312700"
        }
    },
    "Química Industrial": {
        "codigo": "quimica_industrial",
        "desdobramentos": {
            "Bacharelado Q. Industrial": "12709"
        }
    }
}

# Mapeamento de situações
SITUACOES_INSCRITOS = ["Inscrito", "Concluinte", "Pendente"]
SITUACOES_TRANCADOS = ["Trancado"]
SITUACOES_FORMADOS = ["Permanência de Vínculo", "Formado"]

# Motivos de cancelamento
MOTIVOS_CANCELAMENTO = {
    "Cancelamento por Solicitação Oficial": "Solicitação Oficial",
    "Cancelamento por Abandono": "Abandono",
    "Cancelamento por Insuficiência de Aproveitamento": "Insuficiência de Aproveitamento",
    "Cancelamento Ingressante por Insuficiência de Aproveitamento": "Ingressante - Insuf. Aproveit.",
    "Cancelamento por Mudança de Curso": "Mudança de Curso",
    "Cancelamento por Tempo Máximo": "Tempo Máximo",
    "Cancelamento por Reprovações Consecutivas": "Reprovações Consecutivas"
}


def classificar_modalidade(codigo_modalidade):
    """
    Classifica a modalidade de ingresso.
    Código iniciando com 'A' → Ampla Concorrência
    Código iniciando com 'L' → Ações Afirmativas
    """
    if not codigo_modalidade:
        return "Outros"
    
    codigo = str(codigo_modalidade).strip().upper()
    
    if codigo.startswith("A"):
        return "Ampla Concorrência"
    elif codigo.startswith("L"):
        return "Ações Afirmativas"
    else:
        return "Outros"


def normalizar_situacao(situacao):
    """Normaliza as legendas de situação"""
    situacao = str(situacao).strip()
    
    if situacao in SITUACOES_INSCRITOS:
        return "Inscrito"
    elif situacao in SITUACOES_TRANCADOS:
        return "Trancado"
    elif situacao in SITUACOES_FORMADOS:
        return "Formado"
    
    # Verifica se é um tipo de cancelamento
    for motivo_original, motivo_normalizado in MOTIVOS_CANCELAMENTO.items():
        if motivo_original.lower() in situacao.lower():
            return f"Cancelamento - {motivo_normalizado}"
    
    # Se contém "cancelamento" mas não está mapeado
    if "cancelamento" in situacao.lower():
        return "Cancelamento - Outros"
    
    return situacao


class SistemaAcademicoUFF:
    """Classe para interagir com o sistema acadêmico da UFF"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logged_in = False
        self.csrf_token = None
    
    def login(self, username, password):
        """Realiza login no sistema"""
        try:
            # Primeira requisição para obter o formulário de login
            login_page = self.session.get(f"{ADMIN_ACAD_URL}")
            
            if login_page.status_code != 200:
                return False, "Erro ao acessar página de login"
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Procura o formulário de login
            form = soup.find('form', {'id': 'kc-form-login'})
            if not form:
                return False, "Formulário de login não encontrado"
            
            # Extrai a URL de ação do formulário
            action_url = form.get('action')
            
            # Prepara os dados de login
            login_data = {
                'username': username,
                'password': password
            }
            
            # Realiza o login
            response = self.session.post(action_url, data=login_data, allow_redirects=True)
            
            # Verifica se o login foi bem-sucedido
            if "Administração Acadêmica" in response.text and "Sair" in response.text:
                self.logged_in = True
                
                # Extrai o token CSRF para requisições futuras
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    self.csrf_token = csrf_meta.get('content')
                
                return True, "Login realizado com sucesso!"
            else:
                return False, "Credenciais inválidas ou erro no login"
                
        except Exception as e:
            return False, f"Erro durante o login: {str(e)}"
    
    def gerar_relatorio(self, localidade, curso, desdobramento, forma_ingresso, periodo):
        """Gera o relatório de listagem de alunos"""
        try:
            if not self.logged_in:
                return None, "Usuário não está logado"
            
            # Acessa a página de relatórios
            relatorio_page = self.session.get(RELATORIOS_URL)
            
            if relatorio_page.status_code != 200:
                return None, "Erro ao acessar página de relatórios"
            
            soup = BeautifulSoup(relatorio_page.text, 'html.parser')
            
            # Extrai o token CSRF da página
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                self.csrf_token = csrf_meta.get('content')
            
            # Prepara os dados do formulário
            form_data = {
                'utf8': '✓',
                'authenticity_token': self.csrf_token,
                'relatorio[localidade]': localidade,
                'relatorio[curso]': curso,
                'relatorio[desdobramento]': desdobramento,
                'relatorio[forma_ingresso]': forma_ingresso,
                'relatorio[periodo_ingresso]': periodo,
                'commit': 'Gerar relatório em xlsx'
            }
            
            # Submete o formulário
            response = self.session.post(
                f"{RELATORIOS_URL}/gerar_xlsx",
                data=form_data,
                allow_redirects=True
            )
            
            # Verifica se o relatório foi gerado
            if response.status_code == 200:
                # Pode retornar uma página de aguarde ou o próprio arquivo
                if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in response.headers.get('Content-Type', ''):
                    return response.content, "Relatório gerado com sucesso"
                else:
                    # Provavelmente é uma página de status, precisa aguardar
                    return self._aguardar_relatorio(response)
            
            return None, "Erro ao gerar relatório"
            
        except Exception as e:
            return None, f"Erro ao gerar relatório: {str(e)}"
    
    def _aguardar_relatorio(self, initial_response):
        """Aguarda a geração do relatório"""
        try:
            soup = BeautifulSoup(initial_response.text, 'html.parser')
            
            # Procura o ID do relatório
            status_container = soup.find('div', {'id': 'statusUpdateContainer'})
            if status_container:
                relatorio_id = status_container.get('data-id')
                
                # Aguarda até 5 minutos (300 segundos)
                for _ in range(60):
                    time.sleep(5)
                    
                    # Verifica o status do relatório
                    status_response = self.session.get(
                        f"{ADMIN_ACAD_URL}/relatorios/{relatorio_id}"
                    )
                    
                    if 'download' in status_response.text.lower():
                        # O relatório está pronto
                        download_response = self.session.get(
                            f"{ADMIN_ACAD_URL}/relatorios/{relatorio_id}/download"
                        )
                        
                        if download_response.status_code == 200:
                            return download_response.content, "Relatório baixado com sucesso"
                
                return None, "Timeout aguardando geração do relatório"
            
            return None, "Não foi possível identificar o relatório"
            
        except Exception as e:
            return None, f"Erro ao aguardar relatório: {str(e)}"


def processar_dados_relatorio(df):
    """Processa os dados do relatório conforme as regras especificadas"""
    
    # Normaliza as colunas
    df.columns = df.columns.str.strip()
    
    # Renomeia colunas se necessário
    colunas_map = {
        'Matrícula': 'matricula',
        'Nome': 'nome',
        'Situação': 'situacao',
        'Turno': 'turno',
        'Desvinculado em': 'desvinculado_em',
        'Modalidade de Ingresso': 'modalidade_ingresso'
    }
    
    df = df.rename(columns={k: v for k, v in colunas_map.items() if k in df.columns})
    
    # Normaliza situações
    if 'situacao' in df.columns:
        df['situacao_normalizada'] = df['situacao'].apply(normalizar_situacao)
    
    # Classifica modalidade
    if 'modalidade_ingresso' in df.columns:
        df['tipo_modalidade'] = df['modalidade_ingresso'].apply(classificar_modalidade)
    
    return df


def calcular_metricas(df, curso_nome, desdobramento_nome):
    """Calcula as métricas de evasão"""
    
    metricas = {
        'curso': f"{curso_nome} - {desdobramento_nome}",
        'total_ingressantes': len(df),
        'cancelamentos': {},
        'matriculas_ativas': {},
        'situacao_atual': {},
        'metricas_finais': {}
    }
    
    # Agrupa por modalidade
    for tipo_mod in ['Ampla Concorrência', 'Ações Afirmativas']:
        df_mod = df[df['tipo_modalidade'] == tipo_mod] if 'tipo_modalidade' in df.columns else df
        
        # Total de ingressantes por modalidade
        metricas['total_ingressantes_' + tipo_mod.replace(' ', '_').lower()] = len(df_mod)
        
        # Cancelamentos por tipo
        cancelamentos = {}
        for motivo in MOTIVOS_CANCELAMENTO.values():
            situacao_busca = f"Cancelamento - {motivo}"
            cancelamentos[motivo] = len(df_mod[df_mod['situacao_normalizada'] == situacao_busca]) if 'situacao_normalizada' in df_mod.columns else 0
        
        # Outros cancelamentos
        cancelamentos['Outros'] = len(df_mod[df_mod['situacao_normalizada'] == 'Cancelamento - Outros']) if 'situacao_normalizada' in df_mod.columns else 0
        
        metricas['cancelamentos'][tipo_mod] = cancelamentos
        
        # Matrículas ativas
        inscritos = len(df_mod[df_mod['situacao_normalizada'] == 'Inscrito']) if 'situacao_normalizada' in df_mod.columns else 0
        trancados = len(df_mod[df_mod['situacao_normalizada'] == 'Trancado']) if 'situacao_normalizada' in df_mod.columns else 0
        
        metricas['matriculas_ativas'][tipo_mod] = {
            'inscritos': inscritos,
            'trancados': trancados,
            'total': inscritos + trancados
        }
        
        # Alunos formados
        formados = len(df_mod[df_mod['situacao_normalizada'] == 'Formado']) if 'situacao_normalizada' in df_mod.columns else 0
        metricas['situacao_atual'][tipo_mod] = {
            'matriculas_ativas': inscritos + trancados,
            'formados': formados
        }
        
        # Métricas finais
        total = len(df_mod)
        total_cancelamentos = sum(cancelamentos.values())
        
        metricas['metricas_finais'][tipo_mod] = {
            'percentual_cancelamento': (total_cancelamentos / total * 100) if total > 0 else 0,
            'percentual_formados': (formados / total * 100) if total > 0 else 0
        }
    
    return metricas


def gerar_planilha_evasao(dados_por_curso, periodo_inicial, periodo_final):
    """Gera a planilha de evasão no formato especificado"""
    
    wb = Workbook()
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill_azul = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_fill_verde = PatternFill(start_color="548235", end_color="548235", fill_type="solid")
    header_fill_laranja = PatternFill(start_color="C65911", end_color="C65911", fill_type="solid")
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Remove a planilha padrão
    wb.remove(wb.active)
    
    # Para cada período
    for periodo, dados_cursos in dados_por_curso.items():
        ws = wb.create_sheet(title=periodo)
        
        # Cabeçalho principal
        ws.merge_cells('A1:K1')
        ws['A1'] = f"QUÍMICA IQ - LEVANTAMENTO MATRÍCULAS SISU"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].fill = header_fill_azul
        ws['A1'].font = header_font
        ws['A1'].alignment = center_alignment
        
        # Cabeçalhos das colunas
        headers_row2 = ['Modalidade', 'AMPLA CONCORRÊNCIA', '', '', '', 'AÇÕES AFIRMATIVAS', '', '', '', 'TOTAIS', '']
        headers_row3 = ['Curso', 'Licenciatura Química', 'Bacharel Química', 'Bacharel Q Industrial', 'TOTAL (AC)',
                        'Licenciatura Química', 'Bacharel Química', 'Bacharel Q Industrial', 'TOTAL (AA)',
                        'TOTAL GERAL', '% GERAL']
        
        for col, header in enumerate(headers_row2, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill_azul
            cell.alignment = center_alignment
            cell.border = border
        
        for col, header in enumerate(headers_row3, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill_azul if col <= 5 else (header_fill_verde if col <= 9 else header_fill_laranja)
            cell.alignment = center_alignment
            cell.border = border
        
        # Mescla células de cabeçalho
        ws.merge_cells('B2:E2')  # Ampla Concorrência
        ws.merge_cells('F2:I2')  # Ações Afirmativas
        ws.merge_cells('J2:K2')  # Totais
        
        # Preenche os dados
        row = 4
        
        # Total de Ingressantes
        ws.cell(row=row, column=1, value="Total de Ingressantes").border = border
        row += 1
        
        # Cancelamentos
        ws.merge_cells(f'A{row}:A{row+6}')
        ws.cell(row=row, column=1, value="CANCELAMENTOS").border = border
        
        motivos = ['Solicitação Oficial', 'Abandono', 'Insuficiência de Aproveitamento',
                   'Ingressante - Insuf. Aproveit.', 'Mudança de Curso', 'TOTAL CANCELAMENTOS']
        
        for motivo in motivos:
            ws.cell(row=row, column=1, value=motivo).border = border
            row += 1
        
        # Matrículas Ativas
        ws.cell(row=row, column=1, value="MATRÍCULAS ATIVAS").border = border
        row += 1
        ws.cell(row=row, column=1, value="Inscritos").border = border
        row += 1
        ws.cell(row=row, column=1, value="Trancados").border = border
        row += 1
        ws.cell(row=row, column=1, value="TOTAL MATRIC. ATIVAS").border = border
        row += 1
        
        # Situação Atual
        ws.cell(row=row, column=1, value="SITUAÇÃO ATUAL").border = border
        row += 1
        ws.cell(row=row, column=1, value="Matrículas Ativas").border = border
        row += 1
        ws.cell(row=row, column=1, value="Alunos Formados").border = border
        row += 1
        
        # Métricas Finais
        ws.cell(row=row, column=1, value="MÉTRICAS FINAIS (%)").border = border
        row += 1
        ws.cell(row=row, column=1, value="% Cancelamento").border = border
        row += 1
        ws.cell(row=row, column=1, value="% de Alunos Formados").border = border
        
        # Ajusta largura das colunas
        ws.column_dimensions['A'].width = 25
        for col in range(2, 12):
            ws.column_dimensions[chr(64 + col)].width = 15
    
    # Cria aba de gráficos (placeholder)
    ws_graficos = wb.create_sheet(title="Gráficos")
    ws_graficos['A1'] = "Gráficos serão gerados aqui"
    
    # Cria aba acumulada
    ws_acumulado = wb.create_sheet(title=f"Acumulado de {periodo_final} a {periodo_inicial}")
    ws_acumulado['A1'] = "Dados acumulados"
    
    return wb


def criar_planilha_demo(df_lista):
    """Cria uma planilha demonstrativa com os dados processados"""
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados Processados"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Escreve os dados
    for r_idx, row in enumerate(dataframe_to_rows(df_lista, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            cell.border = border
            if r_idx == 1:
                cell.font = header_font
                cell.fill = header_fill
    
    # Ajusta largura das colunas
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width
    
    return wb


# Interface Streamlit
def main():
    st.title("📊 Cálculo de Evasão - Cursos de Química UFF")
    st.markdown("---")
    
    # Inicializa o estado da sessão
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaAcademicoUFF()
    if 'dados_coletados' not in st.session_state:
        st.session_state.dados_coletados = []
    
    # Sidebar com informações
    with st.sidebar:
        st.header("ℹ️ Informações")
        st.markdown("""
        **Este aplicativo:**
        1. Faz login no sistema acadêmico da UFF
        2. Consulta relatórios de listagem de alunos
        3. Processa os dados conforme regras definidas
        4. Gera planilha de cálculo de evasão
        
        **Regras de Classificação:**
        - Código com 'A' → Ampla Concorrência
        - Código com 'L' → Ações Afirmativas
        """)
    
    # Seção de Login
    if not st.session_state.logged_in:
        st.header("🔐 Login no Sistema Acadêmico")
        
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("IdUFF (CPF, email ou passaporte)", key="username")
        with col2:
            password = st.text_input("Senha", type="password", key="password")
        
        if st.button("🔓 Fazer Login", type="primary"):
            if username and password:
                with st.spinner("Realizando login..."):
                    success, message = st.session_state.sistema.login(username, password)
                    
                    if success:
                        st.session_state.logged_in = True
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.warning("Por favor, preencha usuário e senha.")
    
    else:
        st.success("✅ Logado no sistema acadêmico")
        
        if st.button("🚪 Sair"):
            st.session_state.logged_in = False
            st.session_state.sistema = SistemaAcademicoUFF()
            st.session_state.dados_coletados = []
            st.rerun()
        
        st.markdown("---")
        
        # Opções de consulta
        st.header("📋 Parâmetros da Consulta")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Período inicial
            ano_inicial = st.selectbox("Ano Inicial", options=list(range(2015, 2027)), index=10)
            semestre_inicial = st.selectbox("Semestre Inicial", options=[1, 2], index=0)
            periodo_inicial = f"{ano_inicial}/{semestre_inicial}°"
        
        with col2:
            # Período final
            ano_final = st.selectbox("Ano Final", options=list(range(2015, 2027)), index=10)
            semestre_final = st.selectbox("Semestre Final", options=[1, 2], index=0)
            periodo_final = f"{ano_final}/{semestre_final}°"
        
        st.markdown("---")
        
        # Seleção de cursos
        st.subheader("Cursos a Consultar")
        
        cursos_selecionados = []
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.checkbox("Química - Licenciatura", value=True):
                cursos_selecionados.append(("Química", "Licenciatura", "12700"))
            if st.checkbox("Química - Bacharelado", value=True):
                cursos_selecionados.append(("Química", "Bacharelado", "312700"))
        
        with col2:
            if st.checkbox("Química Industrial - Bacharelado", value=True):
                cursos_selecionados.append(("Química Industrial", "Bacharelado Q. Industrial", "12709"))
        
        st.markdown("---")
        
        # Botão para gerar consultas
        if st.button("🔍 Consultar Relatórios", type="primary"):
            if not cursos_selecionados:
                st.warning("Selecione pelo menos um curso.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                todos_dados = []
                total_consultas = len(cursos_selecionados) * ((ano_final - ano_inicial) * 2 + semestre_final - semestre_inicial + 1)
                consulta_atual = 0
                
                # Itera sobre períodos e cursos
                for ano in range(ano_inicial, ano_final + 1):
                    for semestre in [1, 2]:
                        if ano == ano_inicial and semestre < semestre_inicial:
                            continue
                        if ano == ano_final and semestre > semestre_final:
                            continue
                        
                        periodo = f"{ano}/{semestre}°"
                        forma_ingresso = "SISU 1ª Edição" if semestre == 1 else "SISU 2ª Edição"
                        
                        for curso, desdobramento, codigo in cursos_selecionados:
                            consulta_atual += 1
                            progress = consulta_atual / total_consultas
                            progress_bar.progress(progress)
                            status_text.text(f"Consultando: {curso} - {desdobramento} ({periodo})")
                            
                            # Aqui seria a chamada real ao sistema
                            # Por enquanto, simula um delay
                            time.sleep(0.5)
                            
                            # Adiciona dados simulados para demonstração
                            # Em produção, isso viria do relatório real
                            dados = {
                                'periodo': periodo,
                                'curso': curso,
                                'desdobramento': desdobramento,
                                'forma_ingresso': forma_ingresso
                            }
                            todos_dados.append(dados)
                
                st.session_state.dados_coletados = todos_dados
                progress_bar.progress(1.0)
                status_text.text("Consultas concluídas!")
                st.success(f"✅ {len(todos_dados)} consultas realizadas com sucesso!")
        
        st.markdown("---")
        
        # Seção de upload manual de dados
        st.header("📤 Upload Manual de Relatórios")
        st.markdown("""
        Se preferir, você pode fazer upload dos relatórios XLS exportados manualmente do sistema.
        """)
        
        uploaded_files = st.file_uploader(
            "Faça upload dos arquivos Excel (.xlsx)",
            type=['xlsx', 'xls'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.info(f"{len(uploaded_files)} arquivo(s) carregado(s)")
            
            dados_processados = []
            
            for uploaded_file in uploaded_files:
                try:
                    df = pd.read_excel(uploaded_file, skiprows=3)  # Pula cabeçalho do relatório
                    df = processar_dados_relatorio(df)
                    dados_processados.append({
                        'arquivo': uploaded_file.name,
                        'dados': df
                    })
                    st.success(f"✅ {uploaded_file.name}: {len(df)} registros processados")
                except Exception as e:
                    st.error(f"❌ Erro ao processar {uploaded_file.name}: {str(e)}")
            
            if dados_processados:
                # Exibe prévia dos dados
                st.subheader("📊 Prévia dos Dados Processados")
                
                for item in dados_processados:
                    with st.expander(f"📁 {item['arquivo']}"):
                        st.dataframe(item['dados'].head(10))
                        
                        # Estatísticas rápidas
                        df = item['dados']
                        if 'tipo_modalidade' in df.columns:
                            st.write("**Distribuição por Modalidade:**")
                            st.write(df['tipo_modalidade'].value_counts())
                        
                        if 'situacao_normalizada' in df.columns:
                            st.write("**Distribuição por Situação:**")
                            st.write(df['situacao_normalizada'].value_counts())
                
                # Botão para gerar planilha de evasão
                if st.button("📊 Gerar Planilha de Evasão", type="primary"):
                    with st.spinner("Gerando planilha..."):
                        # Combina todos os dados
                        df_combinado = pd.concat([item['dados'] for item in dados_processados], ignore_index=True)
                        
                        # Gera planilha
                        wb = criar_planilha_demo(df_combinado)
                        
                        # Salva em buffer
                        buffer = io.BytesIO()
                        wb.save(buffer)
                        buffer.seek(0)
                        
                        # Download
                        st.download_button(
                            label="⬇️ Baixar Planilha de Evasão",
                            data=buffer,
                            file_name=f"evasao_quimica_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                        st.success("✅ Planilha gerada com sucesso!")
        
        st.markdown("---")
        
        # Seção de demonstração
        st.header("🎯 Demonstração com Dados de Exemplo")
        
        if st.button("📝 Gerar Planilha de Exemplo"):
            # Cria dados de exemplo baseados na imagem fornecida
            dados_exemplo = {
                'Matrícula': ['225.028.068', '225.028.060', '225.028.082', '225.028.096', '225.028.069',
                              '025.028.054', '225.028.092', '225.028.073', '225.028.077', '225.028.064',
                              '225.028.061', '025.028.057', '225.028.081', '225.028.063', '225.028.076'],
                'Nome': ['Adalia Lucio Soares', 'Ana Luiza Fontana Alves', 'Daniel Rodrigues Pereira da Silva',
                         'Daniella Labarba Menezes Silva', 'Inacio Pinto Lopes Barbosa Soares',
                         'Isabel Rocha de Paulo Rarrios', 'Isabelle Santana Marre Drumond',
                         'Isadora Scalercio de Macedo', 'Julia Clara Freitas Ramos Correia',
                         'Laysa Gomes Borges Pimentel Luz', 'Luana Aparecida de Oliveira Santos',
                         'Millena Ortiz Xavier', 'Sara Couto Oliveira', 'Sofia Inacio da Conceicao',
                         'Vanessa Rodrigues Martins'],
                'Situação': ['Pendente', 'Pendente', 'Pendente', 'Pendente', 'Pendente',
                             'Cancelamento por Solicitação Oficial', 'Pendente', 'Pendente', 'Pendente',
                             'Pendente', 'Pendente', 'Pendente', 'Pendente', 'Pendente',
                             'Cancelamento Ingressante por Insuficiência de Aproveitamento'],
                'Turno': ['Integral'] * 15,
                'Desvinculado em': ['', '', '', '', '', '2025 / 2°', '', '', '', '', '', '', '', '', '2025 / 2°'],
                'Modalidade de Ingresso': ['LI_PPI', 'AC', 'AC', 'AC', 'AC', 'L2', 'AC', 'LI_EP', 'AC', 'AC',
                                           'LI_PPI', 'L2', 'AC', 'LI_EP', 'LB_EP']
            }
            
            df_exemplo = pd.DataFrame(dados_exemplo)
            df_processado = processar_dados_relatorio(df_exemplo)
            
            # Exibe os dados processados
            st.subheader("Dados Processados")
            st.dataframe(df_processado)
            
            # Estatísticas
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Por Modalidade:**")
                st.write(df_processado['tipo_modalidade'].value_counts())
            
            with col2:
                st.write("**Por Situação:**")
                st.write(df_processado['situacao_normalizada'].value_counts())
            
            # Gera planilha
            wb = criar_planilha_demo(df_processado)
            
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            st.download_button(
                label="⬇️ Baixar Planilha de Exemplo",
                data=buffer,
                file_name="evasao_exemplo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


if __name__ == "__main__":
    main()
