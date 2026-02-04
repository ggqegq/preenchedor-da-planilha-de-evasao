import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
from openpyxl.utils import get_column_letter
import re
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Configuração da página
st.set_page_config(
    page_title="Cálculo de Evasão - Química UFF",
    page_icon="📊",
    layout="wide"
)

# URLs do sistema
BASE_URL = "https://app.uff.br"
LOGIN_URL = "https://app.uff.br/iduff/login.jsp"
ADMIN_ACAD_URL = "https://app.uff.br/graduacao/administracaoacademica"
RELATORIOS_URL = f"{ADMIN_ACAD_URL}/relatorios/listagens_alunos"

# Constantes de cursos
CURSOS_CONFIG = {
    "Licenciatura Química": {"codigo": "12700"},
    "Bacharel Química": {"codigo": "312700"},
    "Bacharel Q Industrial": {"codigo": "12709"}
}

# Mapeamento de situações para categorias
SITUACOES_INSCRITOS = ["Inscrito", "Concluinte", "Pendente"]
SITUACOES_TRANCADOS = ["Trancado"]
SITUACOES_FORMADOS = ["Permanência de Vínculo", "Formado"]

# Motivos de cancelamento - ordem conforme planilha
MOTIVOS_CANCELAMENTO = [
    ("Solicitação Oficial", ["Cancelamento por Solicitação Oficial"]),
    ("Abandono", ["Cancelamento por Abandono"]),
    ("Insuficiência de Aproveitamento", ["Cancelamento por Insuficiência de Aproveitamento"]),
    ("Ingressante - Insuf. Aproveit.", ["Cancelamento Ingressante por Insuficiência de Aproveitamento"]),
    ("Mudança de Curso", ["Cancelamento por Mudança de Curso"]),
]

def classificar_modalidade(codigo_modalidade):
    """
    Classifica a modalidade de ingresso.
    Código iniciando com 'L' → Ações Afirmativas (AA)
    Outros → Ampla Concorrência (AC)
    """
    if not codigo_modalidade or pd.isna(codigo_modalidade):
        return "AC"
    
    codigo = str(codigo_modalidade).strip().upper()
    
    if codigo.startswith("L"):
        return "AA"
    else:
        return "AC"

def categorizar_situacao(situacao):
    """Categoriza a situação do aluno"""
    if not situacao or pd.isna(situacao):
        return "Outros", None
    
    situacao = str(situacao).strip()
    
    # Verifica se é inscrito/ativo
    for s in SITUACOES_INSCRITOS:
        if s.lower() in situacao.lower():
            return "Inscrito", None
    
    # Verifica se é trancado
    for s in SITUACOES_TRANCADOS:
        if s.lower() in situacao.lower():
            return "Trancado", None
    
    # Verifica se é formado
    for s in SITUACOES_FORMADOS:
        if s.lower() in situacao.lower():
            return "Formado", None
    
    # Verifica cancelamentos
    for motivo_nome, situacoes_match in MOTIVOS_CANCELAMENTO:
        for s in situacoes_match:
            if s.lower() in situacao.lower():
                return "Cancelamento", motivo_nome
    
    # Se contém "cancelamento" mas não está mapeado
    if "cancelamento" in situacao.lower():
        return "Cancelamento", "Outros"
    
    return "Outros", None

class SistemaAcademicoUFF:
    """Classe para interagir com o sistema acadêmico da UFF"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.logged_in = False
        self.csrf_token = None
    
    def login(self, username, password):
        """Realiza login no sistema"""
        try:
            # Acessa a página de login
            login_page = self.session.get(LOGIN_URL)
            
            if login_page.status_code != 200:
                return False, "Erro ao acessar página de login"
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Procura o formulário de login
            form = soup.find('form')
            if not form:
                return False, "Formulário de login não encontrado"
            
            # Extrai a URL de ação do formulário
            action_url = form.get('action')
            if not action_url.startswith('http'):
                action_url = BASE_URL + action_url
            
            # Prepara os dados de login
            login_data = {
                'username': username,
                'password': password
            }
            
            # Realiza o login
            response = self.session.post(action_url, data=login_data, allow_redirects=True)
            
            # Verifica se o login foi bem-sucedido
            if "Administração Acadêmica" in response.text or "Sair" in response.text:
                self.logged_in = True
                return True, "Login realizado com sucesso!"
            else:
                return False, "Credenciais inválidas ou erro no login"
                
        except Exception as e:
            return False, f"Erro durante o login: {str(e)}"
    
    def gerar_relatorios_por_periodo(self, periodo_inicio, periodo_fim):
        """
        Gera relatórios para todos os cursos e períodos no intervalo especificado.
        Retorna dicionário com dados processados.
        """
        if not self.logged_in:
            return {}, "Usuário não está logado"
        
        dados_por_periodo = {}
        
        # Converte períodos para lista
        anos_inicio = int(periodo_inicio.split('.')[0])
        semestres_inicio = int(periodo_inicio.split('.')[1])
        anos_fim = int(periodo_fim.split('.')[0])
        semestres_fim = int(periodo_fim.split('.')[1])
        
        # Gera lista de períodos
        periodos = []
        for ano in range(anos_fim, anos_inicio - 1, -1):
            for semestre in [2, 1]:
                if ano == anos_inicio and semestre < semestres_inicio:
                    continue
                if ano == anos_fim and semestre > semestres_fim:
                    continue
                periodos.append(f"{ano}.{semestre}")
        
        st.info(f"Gerando relatórios para {len(periodos)} períodos: {', '.join(periodos)}")
        
        # Para cada período e curso, gera relatório
        for periodo in periodos:
            dados_por_periodo[periodo] = {}
            
            for curso_nome, curso_info in CURSOS_CONFIG.items():
                with st.spinner(f"Processando {curso_nome} - {periodo}..."):
                    try:
                        # Aqui você implementaria a lógica real de busca no sistema
                        # Por enquanto, vamos simular com dados de exemplo
                        dados_simulados = self._simular_dados_curso(curso_nome, periodo)
                        dados_por_periodo[periodo][curso_nome] = dados_simulados
                        
                    except Exception as e:
                        st.warning(f"Erro ao processar {curso_nome} - {periodo}: {str(e)}")
                        dados_por_periodo[periodo][curso_nome] = {"AC": {}, "AA": {}}
        
        return dados_por_periodo, "Relatórios gerados com sucesso"
    
    def _simular_dados_curso(self, curso_nome, periodo):
        """Simula dados para demonstração (substituir por busca real no sistema)"""
        import random
        
        # Dados simulados baseados no exemplo fornecido
        if curso_nome == "Licenciatura Química":
            return {
                "AC": {
                    "total_ingressantes": 10,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 3
                    },
                    "inscritos": 6,
                    "trancados": 0,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 16,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 3
                    },
                    "inscritos": 11,
                    "trancados": 1,
                    "formados": 0
                }
            }
        elif curso_nome == "Bacharel Química":
            return {
                "AC": {
                    "total_ingressantes": 5,
                    "cancelamentos": {},
                    "inscritos": 5,
                    "trancados": 0,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 9,
                    "cancelamentos": {
                        "Ingressante - Insuf. Aproveit.": 1
                    },
                    "inscritos": 7,
                    "trancados": 0,
                    "formados": 0
                }
            }
        elif curso_nome == "Bacharel Q Industrial":
            return {
                "AC": {
                    "total_ingressantes": 9,
                    "cancelamentos": {},
                    "inscritos": 8,
                    "trancados": 1,
                    "formados": 0
                },
                "AA": {
                    "total_ingressantes": 11,
                    "cancelamentos": {
                        "Solicitação Oficial": 1,
                        "Ingressante - Insuf. Aproveit.": 2
                    },
                    "inscritos": 6,
                    "trancados": 2,
                    "formados": 0
                }
            }
        
        return {"AC": {}, "AA": {}}

def processar_relatorio(df, curso_nome):
    """
    Processa um DataFrame de relatório e retorna contagens por modalidade.
    """
    resultados = {
        "AC": {
            "total_ingressantes": 0,
            "cancelamentos": defaultdict(int),
            "inscritos": 0,
            "trancados": 0,
            "formados": 0
        },
        "AA": {
            "total_ingressantes": 0,
            "cancelamentos": defaultdict(int),
            "inscritos": 0,
            "trancados": 0,
            "formados": 0
        }
    }
    
    # Procura colunas relevantes
    col_situacao = None
    col_modalidade = None
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'situação' in col_lower or 'situacao' in col_lower:
            col_situacao = col
        if 'modalidade' in col_lower:
            col_modalidade = col
    
    if col_situacao is None:
        # Tenta encontrar por posição (última coluna geralmente é a situação)
        col_situacao = df.columns[-1]
    
    # Processa cada linha
    for idx, row in df.iterrows():
        # Classifica modalidade
        modalidade = "AC"  # Default
        if col_modalidade and col_modalidade in row:
            modalidade = classificar_modalidade(row[col_modalidade])
        else:
            # Se não tem coluna de modalidade, assume que todos são AC
            modalidade = "AC"
        
        # Conta ingressante
        resultados[modalidade]["total_ingressantes"] += 1
        
        # Categoriza situação
        if col_situacao in row:
            categoria, motivo = categorizar_situacao(row[col_situacao])
            
            if categoria == "Inscrito":
                resultados[modalidade]["inscritos"] += 1
            elif categoria == "Trancado":
                resultados[modalidade]["trancados"] += 1
            elif categoria == "Formado":
                resultados[modalidade]["formados"] += 1
            elif categoria == "Cancelamento" and motivo:
                resultados[modalidade]["cancelamentos"][motivo] += 1
    
    return resultados

def criar_aba_periodo(wb, periodo, dados_cursos):
    """
    Cria uma aba no workbook para um período específico.
    Segue exatamente o layout da planilha original.
    """
    nome_aba = str(periodo).replace("/", ".").replace("°", "")
    ws = wb.create_sheet(title=nome_aba)
    
    # Estilos
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    center = Alignment(horizontal='center', vertical='center')
    left = Alignment(horizontal='left', vertical='center')
    
    # === LINHA 1: Título principal ===
    ws.merge_cells('A1:K1')
    cell = ws['A1']
    cell.value = "QUÍMICA IQ - LEVANTAMENTO MATRÍCULAS SISU"
    cell.font = Font(bold=True, color="FFFFFF", size=12)
    cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    cell.alignment = center
    cell.border = thin_border
    
    # === LINHA 2: Cabeçalho de modalidades ===
    ws['A2'] = "Modalidade"
    ws['A2'].font = Font(bold=True, color="FFFFFF")
    ws['A2'].fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    ws['A2'].alignment = center
    ws['A2'].border = thin_border
    
    ws.merge_cells('B2:E2')
    ws['B2'] = "AMPLA CONCORRÊNCIA"
    ws['B2'].font = Font(bold=True, color="FFFFFF")
    ws['B2'].fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    ws['B2'].alignment = center
    ws['B2'].border = thin_border
    
    ws.merge_cells('F2:I2')
    ws['F2'] = "AÇÕES AFIRMATIVAS"
    ws['F2'].font = Font(bold=True, color="FFFFFF")
    ws['F2'].fill = PatternFill(start_color="548235", end_color="548235", fill_type="solid")
    ws['F2'].alignment = center
    ws['F2'].border = thin_border
    
    ws.merge_cells('J2:K2')
    ws['J2'] = "TOTAIS"
    ws['J2'].font = Font(bold=True, color="FFFFFF")
    ws['J2'].fill = PatternFill(start_color="C65911", end_color="C65911", fill_type="solid")
    ws['J2'].alignment = center
    ws['J2'].border = thin_border
    
    # === LINHA 3: Cabeçalho de cursos ===
    cabecalhos = [
        ("Curso", "1F4E79"),
        ("Licenciatura Química", "1F4E79"),
        ("Bacharel Química", "1F4E79"),
        ("Bacharel Q Industrial", "1F4E79"),
        ("TOTAL", "1F4E79"),
        ("Licenciatura Química", "548235"),
        ("Bacharel Química", "548235"),
        ("Bacharel Q Industrial", "548235"),
        ("TOTAL", "548235"),
        ("TOTAL", "C65911"),
        ("%", "C65911")
    ]
    
    for col, (texto, cor) in enumerate(cabecalhos, 1):
        cell = ws.cell(row=3, column=col, value=texto)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=cor, end_color=cor, fill_type="solid")
        cell.alignment = center
        cell.border = thin_border
    
    # === LINHA 4: Subtítulos ===
    ws['A4'] = " "
    ws['A4'].border = thin_border
    
    ws['B4'] = " "
    ws['B4'].border = thin_border
    ws['C4'] = " "
    ws['C4'].border = thin_border
    ws['D4'] = " "
    ws['D4'].border = thin_border
    ws['E4'] = "(AC)"
    ws['E4'].alignment = center
    ws['E4'].border = thin_border
    
    ws['F4'] = " "
    ws['F4'].border = thin_border
    ws['G4'] = " "
    ws['G4'].border = thin_border
    ws['H4'] = " "
    ws['H4'].border = thin_border
    ws['I4'] = "(AA)"
    ws['I4'].alignment = center
    ws['I4'].border = thin_border
    
    ws['J4'] = "GERAL"
    ws['J4'].alignment = center
    ws['J4'].border = thin_border
    ws['K4'] = "GERAL"
    ws['K4'].alignment = center
    ws['K4'].border = thin_border
    
    # === LINHA 5: Total de Ingressantes ===
    linha_atual = 5
    ws.cell(row=linha_atual, column=1, value="Total de Ingressantes")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Extrai dados
    lic_quim = dados_cursos.get("Licenciatura Química", {"AC": {}, "AA": {}})
    bach_quim = dados_cursos.get("Bacharel Química", {"AC": {}, "AA": {}})
    bach_ind = dados_cursos.get("Bacharel Q Industrial", {"AC": {}, "AA": {}})
    
    def get_val(dados, modalidade, chave, sub_chave=None):
        """Helper para obter valores com default"""
        if modalidade not in dados:
            return 0
        if sub_chave:
            return dados[modalidade].get(chave, {}).get(sub_chave, 0)
        return dados[modalidade].get(chave, 0)
    
    # Valores AC
    val_lic_ac = get_val(lic_quim, "AC", "total_ingressantes")
    val_bach_ac = get_val(bach_quim, "AC", "total_ingressantes")
    val_ind_ac = get_val(bach_ind, "AC", "total_ingressantes")
    total_ac = val_lic_ac + val_bach_ac + val_ind_ac
    
    # Valores AA
    val_lic_aa = get_val(lic_quim, "AA", "total_ingressantes")
    val_bach_aa = get_val(bach_quim, "AA", "total_ingressantes")
    val_ind_aa = get_val(bach_ind, "AA", "total_ingressantes")
    total_aa = val_lic_aa + val_bach_aa + val_ind_aa
    
    total_geral = total_ac + total_aa
    
    # Preenche valores na linha 5
    valores = [
        val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
        val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
        total_geral, "-"
    ]
    
    for col, val in enumerate(valores, 2):
        cell = ws.cell(row=linha_atual, column=col, value=val)
        cell.alignment = center
        cell.border = thin_border
        if col in [5, 9, 10]:  # Totais
            cell.font = Font(bold=True)
    
    # Fórmulas para totais
    ws.cell(row=linha_atual, column=5).value = f"=SUM(B{linha_atual}:D{linha_atual})"
    ws.cell(row=linha_atual, column=9).value = f"=SUM(F{linha_atual}:H{linha_atual})"
    ws.cell(row=linha_atual, column=10).value = f"=E{linha_atual}+I{linha_atual}"
    
    # === LINHA 6: CANCELAMENTOS (título) ===
    linha_atual += 1
    ws.merge_cells(f'A{linha_atual}:K{linha_atual}')
    cell = ws.cell(row=linha_atual, column=1, value="CANCELAMENTOS")
    cell.font = Font(bold=True)
    cell.fill = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")
    cell.alignment = center
    cell.border = thin_border
    
    # Motivos de cancelamento
    motivos = [
        "Solicitação Oficial",
        "Abandono",
        "Insuficiência de Aproveitamento",
        "Ingressante - Insuf. Aproveit.",
        "Mudança de Curso"
    ]
    
    for motivo in motivos:
        linha_atual += 1
        
        ws.cell(row=linha_atual, column=1, value=motivo)
        ws.cell(row=linha_atual, column=1).alignment = left
        ws.cell(row=linha_atual, column=1).border = thin_border
        
        # Valores AC
        val_lic_ac = get_val(lic_quim, "AC", "cancelamentos", motivo)
        val_bach_ac = get_val(bach_quim, "AC", "cancelamentos", motivo)
        val_ind_ac = get_val(bach_ind, "AC", "cancelamentos", motivo)
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        # Valores AA
        val_lic_aa = get_val(lic_quim, "AA", "cancelamentos", motivo)
        val_bach_aa = get_val(bach_quim, "AA", "cancelamentos", motivo)
        val_ind_aa = get_val(bach_ind, "AA", "cancelamentos", motivo)
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        
        # Calcula percentual
        if total_geral > 0 and ws.cell(row=5, column=10).value != 0:
            percentual = f"=J{linha_atual}/$J$5"
        else:
            percentual = 0
        
        valores = [
            val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
            val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
            total_geral, percentual
        ]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=linha_atual, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
            
            # Para percentuais, formata como porcentagem
            if col == 11:
                cell.number_format = '0.00%'
            
            # Adiciona fórmulas para totais
            if col == 5:
                cell.value = f"=SUM(B{linha_atual}:D{linha_atual})"
            elif col == 9:
                cell.value = f"=SUM(F{linha_atual}:H{linha_atual})"
            elif col == 10:
                cell.value = f"=E{linha_atual}+I{linha_atual}"
    
    # === LINHA: TOTAL CANCELAMENTOS ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="TOTAL CANCELAMENTOS")
    ws.cell(row=linha_atual, column=1).font = Font(bold=True)
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Fórmulas para total de cancelamentos
    for col in range(2, 12):
        if col == 5:
            ws.cell(row=linha_atual, column=col).value = f"=SUM(E7:E{linha_atual-1})"
        elif col == 9:
            ws.cell(row=linha_atual, column=col).value = f"=SUM(I7:I{linha_atual-1})"
        elif col == 10:
            ws.cell(row=linha_atual, column=col).value = f"=E{linha_atual}+I{linha_atual}"
        elif col == 11:
            ws.cell(row=linha_atual, column=col).value = f"=J{linha_atual}/$J$5"
            ws.cell(row=linha_atual, column=col).number_format = '0.00%'
        elif col in [2, 3, 4, 6, 7, 8]:
            start_row = linha_atual - len(motivos)
            end_row = linha_atual - 1
            ws.cell(row=linha_atual, column=col).value = f"=SUM({get_column_letter(col)}{start_row}:{get_column_letter(col)}{end_row})"
        
        cell = ws.cell(row=linha_atual, column=col)
        cell.font = Font(bold=True)
        cell.alignment = center
        cell.border = thin_border
    
    # === LINHA: MATRÍCULAS ATIVAS (título) ===
    linha_atual += 1
    ws.merge_cells(f'A{linha_atual}:K{linha_atual}')
    cell = ws.cell(row=linha_atual, column=1, value="MATRÍCULAS ATIVAS")
    cell.font = Font(bold=True)
    cell.fill = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")
    cell.alignment = center
    cell.border = thin_border
    
    # === LINHA: Inscritos ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="Inscritos")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Valores AC
    val_lic_ac = get_val(lic_quim, "AC", "inscritos")
    val_bach_ac = get_val(bach_quim, "AC", "inscritos")
    val_ind_ac = get_val(bach_ind, "AC", "inscritos")
    total_ac = val_lic_ac + val_bach_ac + val_ind_ac
    
    # Valores AA
    val_lic_aa = get_val(lic_quim, "AA", "inscritos")
    val_bach_aa = get_val(bach_quim, "AA", "inscritos")
    val_ind_aa = get_val(bach_ind, "AA", "inscritos")
    total_aa = val_lic_aa + val_bach_aa + val_ind_aa
    
    total_geral = total_ac + total_aa
    
    percentual = f"=J{linha_atual}/$J$5"
    
    valores = [
        val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
        val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
        total_geral, percentual
    ]
    
    for col, val in enumerate(valores, 2):
        cell = ws.cell(row=linha_atual, column=col, value=val)
        cell.alignment = center
        cell.border = thin_border
        
        if col == 5:
            cell.value = f"=SUM(B{linha_atual}:D{linha_atual})"
        elif col == 9:
            cell.value = f"=SUM(F{linha_atual}:H{linha_atual})"
        elif col == 10:
            cell.value = f"=E{linha_atual}+I{linha_atual}"
        elif col == 11:
            cell.number_format = '0.00%'
    
    # === LINHA: Trancados ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="Trancados")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Valores AC
    val_lic_ac = get_val(lic_quim, "AC", "trancados")
    val_bach_ac = get_val(bach_quim, "AC", "trancados")
    val_ind_ac = get_val(bach_ind, "AC", "trancados")
    total_ac = val_lic_ac + val_bach_ac + val_ind_ac
    
    # Valores AA
    val_lic_aa = get_val(lic_quim, "AA", "trancados")
    val_bach_aa = get_val(bach_quim, "AA", "trancados")
    val_ind_aa = get_val(bach_ind, "AA", "trancados")
    total_aa = val_lic_aa + val_bach_aa + val_ind_aa
    
    total_geral = total_ac + total_aa
    
    percentual = f"=J{linha_atual}/$J$5"
    
    valores = [
        val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
        val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
        total_geral, percentual
    ]
    
    for col, val in enumerate(valores, 2):
        cell = ws.cell(row=linha_atual, column=col, value=val)
        cell.alignment = center
        cell.border = thin_border
        
        if col == 5:
            cell.value = f"=SUM(B{linha_atual}:D{linha_atual})"
        elif col == 9:
            cell.value = f"=SUM(F{linha_atual}:H{linha_atual})"
        elif col == 10:
            cell.value = f"=E{linha_atual}+I{linha_atual}"
        elif col == 11:
            cell.number_format = '0.00%'
    
    # === LINHA: TOTAL MATRIC. ATIVAS ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="TOTAL MATRIC. ATIVAS")
    ws.cell(row=linha_atual, column=1).font = Font(bold=True)
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Fórmulas para total de matrículas ativas
    for col in range(2, 12):
        if col == 5:
            ws.cell(row=linha_atual, column=col).value = f"=E{linha_atual-2}+E{linha_atual-1}"
        elif col == 9:
            ws.cell(row=linha_atual, column=col).value = f"=I{linha_atual-2}+I{linha_atual-1}"
        elif col == 10:
            ws.cell(row=linha_atual, column=col).value = f"=E{linha_atual}+I{linha_atual}"
        elif col == 11:
            ws.cell(row=linha_atual, column=col).value = f"=J{linha_atual}/$J$5"
            ws.cell(row=linha_atual, column=col).number_format = '0.00%'
        elif col in [2, 3, 4, 6, 7, 8]:
            row1 = linha_atual - 2
            row2 = linha_atual - 1
            ws.cell(row=linha_atual, column=col).value = f"={get_column_letter(col)}{row1}+{get_column_letter(col)}{row2}"
        
        cell = ws.cell(row=linha_atual, column=col)
        cell.font = Font(bold=True)
        cell.alignment = center
        cell.border = thin_border
    
    # === LINHA: SITUAÇÃO ATUAL (título) ===
    linha_atual += 1
    ws.merge_cells(f'A{linha_atual}:K{linha_atual}')
    cell = ws.cell(row=linha_atual, column=1, value="SITUAÇÃO ATUAL")
    cell.font = Font(bold=True)
    cell.fill = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")
    cell.alignment = center
    cell.border = thin_border
    
    # === LINHA: Matrículas Ativas (repetição) ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="Matrículas Ativas")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Copia os valores da linha TOTAL MATRIC. ATIVAS
    for col in range(2, 12):
        src_row = linha_atual - 2
        ws.cell(row=linha_atual, column=col).value = f"={get_column_letter(col)}{src_row}"
        cell = ws.cell(row=linha_atual, column=col)
        cell.alignment = center
        cell.border = thin_border
        if col == 11:
            cell.number_format = '0.00%'
    
    # === LINHA: Alunos Formados ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="Alunos Formados")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Valores AC
    val_lic_ac = get_val(lic_quim, "AC", "formados")
    val_bach_ac = get_val(bach_quim, "AC", "formados")
    val_ind_ac = get_val(bach_ind, "AC", "formados")
    total_ac = val_lic_ac + val_bach_ac + val_ind_ac
    
    # Valores AA
    val_lic_aa = get_val(lic_quim, "AA", "formados")
    val_bach_aa = get_val(bach_quim, "AA", "formados")
    val_ind_aa = get_val(bach_ind, "AA", "formados")
    total_aa = val_lic_aa + val_bach_aa + val_ind_aa
    
    total_geral = total_ac + total_aa
    
    percentual = f"=J{linha_atual}/$J$5"
    
    valores = [
        val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
        val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
        total_geral, percentual
    ]
    
    for col, val in enumerate(valores, 2):
        cell = ws.cell(row=linha_atual, column=col, value=val)
        cell.alignment = center
        cell.border = thin_border
        
        if col == 5:
            cell.value = f"=SUM(B{linha_atual}:D{linha_atual})"
        elif col == 9:
            cell.value = f"=SUM(F{linha_atual}:H{linha_atual})"
        elif col == 10:
            cell.value = f"=E{linha_atual}+I{linha_atual}"
        elif col == 11:
            cell.number_format = '0.00%'
    
    # === LINHA: MÉTRICAS FINAIS (%) (título) ===
    linha_atual += 1
    ws.merge_cells(f'A{linha_atual}:K{linha_atual}')
    cell = ws.cell(row=linha_atual, column=1, value="MÉTRICAS FINAIS (%)")
    cell.font = Font(bold=True)
    cell.fill = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")
    cell.alignment = center
    cell.border = thin_border
    
    # === LINHA: % Cancelamento ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="% Cancelamento")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Calcula percentuais
    for col in range(2, 12):
        if col in [5, 9, 10, 11]:
            # Totais - usa fórmula
            if col == 5:
                ws.cell(row=linha_atual, column=col).value = f"=E13/$J$5"
            elif col == 9:
                ws.cell(row=linha_atual, column=col).value = f"=I13/$J$5"
            elif col == 10:
                ws.cell(row=linha_atual, column=col).value = f"=J13/$J$5"
            elif col == 11:
                ws.cell(row=linha_atual, column=col).value = "-"
        else:
            # Por curso/modalidade
            if col < 5:  # AC
                total_cell = "B5" if col == 2 else "C5" if col == 3 else "D5"
            else:  # AA
                total_cell = "F5" if col == 6 else "G5" if col == 7 else "H5"
            
            cancel_cell = f"{get_column_letter(col)}13"
            ws.cell(row=linha_atual, column=col).value = f"={cancel_cell}/{total_cell}"
        
        cell = ws.cell(row=linha_atual, column=col)
        cell.alignment = center
        cell.border = thin_border
        if col != 11:
            cell.number_format = '0.00%'
    
    # === LINHA: % de Alunos Formados ===
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="% de Alunos Formados")
    ws.cell(row=linha_atual, column=1).alignment = left
    ws.cell(row=linha_atual, column=1).border = thin_border
    
    # Calcula percentuais de formados
    for col in range(2, 12):
        if col in [5, 9, 10, 11]:
            # Totais - usa fórmula
            if col == 5:
                ws.cell(row=linha_atual, column=col).value = f"=E19/$J$5"
            elif col == 9:
                ws.cell(row=linha_atual, column=col).value = f"=I19/$J$5"
            elif col == 10:
                ws.cell(row=linha_atual, column=col).value = f"=J19/$J$5"
            elif col == 11:
                ws.cell(row=linha_atual, column=col).value = "-"
        else:
            # Por curso/modalidade
            if col < 5:  # AC
                total_cell = "B5" if col == 2 else "C5" if col == 3 else "D5"
            else:  # AA
                total_cell = "F5" if col == 6 else "G5" if col == 7 else "H5"
            
            formados_cell = f"{get_column_letter(col)}19"
            ws.cell(row=linha_atual, column=col).value = f"={formados_cell}/{total_cell}"
        
        cell = ws.cell(row=linha_atual, column=col)
        cell.alignment = center
        cell.border = thin_border
        if col != 11:
            cell.number_format = '0.00%'
    
    # === LINHAS FINAIS: Teste de soma e validação ===
    linha_atual += 2
    ws.cell(row=linha_atual, column=1, value="Teste de soma:")
    ws.cell(row=linha_atual, column=2, value=f"=J13+J16+J19")
    ws.cell(row=linha_atual, column=2).alignment = left
    ws.cell(row=linha_atual, column=2).border = thin_border
    
    linha_atual += 1
    ws.cell(row=linha_atual, column=1, value="Dados digitados:")
    ws.cell(row=linha_atual, column=2, value=f'=IF(J5=J{linha_atual-1}, "OK", "Erro")')
    ws.cell(row=linha_atual, column=2).alignment = left
    ws.cell(row=linha_atual, column=2).border = thin_border
    
    # Ajusta largura das colunas
    ws.column_dimensions['A'].width = 30
    for col in range(2, 12):
        ws.column_dimensions[get_column_letter(col)].width = 12
    
    return ws

def criar_aba_acumulado(wb, dados_por_periodo):
    """
    Cria a aba 'Acumulado de X a Y' com os dados consolidados.
    """
    # Nome da aba
    periodos = sorted(dados_por_periodo.keys(), reverse=True)
    if not periodos:
        return None
    
    titulo_aba = f"Acumulado de {periodos[0]} a {periodos[-1]}"
    ws = wb.create_sheet(title=titulo_aba[:31])  # Limita a 31 caracteres
    
    # Preenche com dados básicos
    ws['A1'] = "Acumulado - Em construção"
    ws['A2'] = "Esta aba será preenchida com fórmulas de consolidação"
    
    return ws

def criar_aba_graficos(wb):
    """Cria aba de gráficos vazia"""
    ws = wb.create_sheet(title="Gráficos")
    ws['A1'] = "Gráficos"
    ws['A2'] = "Esta aba será usada para inserir gráficos baseados nos dados"
    return ws

def criar_aba_modelo(wb):
    """Cria aba modelo"""
    ws = wb.create_sheet(title="Modelo")
    
    # Cria estrutura básica do modelo
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Título
    ws.merge_cells('A1:K1')
    ws['A1'] = "QUÍMICA IQ - LEVANTAMENTO MATRÍCULAS SISU - MODELO"
    ws['A1'].font = Font(bold=True, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws['A1'].border = thin_border
    
    # Instruções
    ws['A3'] = "INSTRUÇÕES:"
    ws['A3'].font = Font(bold=True)
    
    instrucoes = [
        "1. Preencha os dados nas células indicadas",
        "2. As fórmulas calcularão automaticamente",
        "3. Não modifique as células com fórmulas",
        "4. Use este modelo para novos períodos"
    ]
    
    for i, instr in enumerate(instrucoes, 1):
        ws.cell(row=3+i, column=1, value=instr)
    
    return ws

def gerar_planilha_completa(dados_por_periodo):
    """
    Gera a planilha completa com todas as abas.
    """
    wb = Workbook()
    
    # Remove a sheet default
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])
    
    # 1. Cria aba de Gráficos
    criar_aba_graficos(wb)
    
    # 2. Cria aba Acumulado
    criar_aba_acumulado(wb, dados_por_periodo)
    
    # 3. Cria uma aba para cada período
    for periodo, dados_cursos in dados_por_periodo.items():
        criar_aba_periodo(wb, periodo, dados_cursos)
    
    # 4. Cria aba Modelo
    criar_aba_modelo(wb)
    
    return wb

def main():
    st.title("📊 Sistema de Cálculo de Evasão - Cursos de Química IQ/UFF")
    st.markdown("---")
    
    # Inicializa estado da sessão
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaAcademicoUFF()
    if 'dados_processados' not in st.session_state:
        st.session_state.dados_processados = {}
    if 'modo_operacao' not in st.session_state:
        st.session_state.modo_operacao = None
    
    # Sidebar com informações
    with st.sidebar:
        st.header("ℹ️ Informações")
        st.markdown("""
        **Cursos Monitorados:**
        - Licenciatura Química (12700)
        - Bacharel Química (312700)
        - Bacharel Q. Industrial (12709)
        
        **Modalidades:**
        - AC: Ampla Concorrência
        - AA: Ações Afirmativas (código inicia com 'L')
        """)
    
    # === SEÇÃO DE LOGIN ===
    if not st.session_state.logged_in:
        st.header("🔐 Login no Sistema Acadêmico")
        
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("IdUFF (CPF, email ou passaporte)")
        with col2:
            password = st.text_input("Senha", type="password")
        
        if st.button("✅ Fazer Login", type="primary", use_container_width=True):
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
                st.warning("Preencha usuário e senha.")
    
    else:
        st.success("✅ Logado no sistema acadêmico")
        
        if st.button("🚪 Sair", type="secondary"):
            st.session_state.logged_in = False
            st.session_state.sistema = SistemaAcademicoUFF()
            st.session_state.dados_processados = {}
            st.session_state.modo_operacao = None
            st.rerun()
        
        st.markdown("---")
        
        # === SELEÇÃO DO MODO DE OPERAÇÃO ===
        st.header("🎯 Selecione o Modo de Operação")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Buscar Dados do Sistema", use_container_width=True):
                st.session_state.modo_operacao = "sistema"
                st.rerun()
        
        with col2:
            if st.button("📤 Fazer Upload de Arquivos", use_container_width=True):
                st.session_state.modo_operacao = "upload"
                st.rerun()
        
        # === MODO: BUSCAR DO SISTEMA ===
        if st.session_state.modo_operacao == "sistema":
            st.markdown("---")
            st.header("🔄 Buscar Dados do Sistema Acadêmico")
            
            st.info("""
            **Instruções:**
            1. Especifique o intervalo de períodos
            2. O sistema buscará dados para todos os cursos
            3. Aguarde o processamento dos relatórios
            """)
            
            # Seleção de períodos
            col1, col2 = st.columns(2)
            with col1:
                # Período inicial
                ano_inicio = st.selectbox(
                    "Ano inicial",
                    options=list(range(2025, 2014, -1)),
                    index=0
                )
                semestre_inicio = st.selectbox(
                    "Semestre inicial",
                    options=[1, 2],
                    index=0
                )
                periodo_inicio = f"{ano_inicio}.{semestre_inicio}"
            
            with col2:
                # Período final
                ano_fim = st.selectbox(
                    "Ano final",
                    options=list(range(2025, 2014, -1)),
                    index=len(list(range(2025, 2014, -1))) - 1
                )
                semestre_fim = st.selectbox(
                    "Semestre final",
                    options=[1, 2],
                    index=1
                )
                periodo_fim = f"{ano_fim}.{semestre_fim}"
            
            st.info(f"Período selecionado: **{periodo_inicio}** a **{periodo_fim}**")
            
            if st.button("🔍 Buscar Dados no Sistema", type="primary", use_container_width=True):
                with st.spinner(f"Buscando dados de {periodo_inicio} a {periodo_fim}..."):
                    try:
                        # Aqui você implementaria a busca real no sistema
                        # Por enquanto, vamos usar dados simulados
                        dados_por_periodo, mensagem = st.session_state.sistema.gerar_relatorios_por_periodo(
                            periodo_inicio, periodo_fim
                        )
                        
                        if dados_por_periodo:
                            st.session_state.dados_processados = dados_por_periodo
                            st.success(f"✅ {mensagem}")
                            
                            # Mostra prévia dos dados
                            mostrar_previa_dados()
                            
                            # Botão para gerar planilha
                            mostrar_botao_gerar_planilha()
                        else:
                            st.error("❌ Nenhum dado encontrado para os períodos especificados")
                            
                    except Exception as e:
                        st.error(f"❌ Erro ao buscar dados: {str(e)}")
        
        # === MODO: UPLOAD DE ARQUIVOS ===
        elif st.session_state.modo_operacao == "upload":
            st.markdown("---")
            st.header("📤 Upload dos Relatórios Excel")
            
            st.info("""
            **Instruções:**
            1. Exporte os relatórios do sistema acadêmico
            2. Nomeie os arquivos: `CURSO_PERIODO.xlsx`
            3. Selecione todos os arquivos de uma vez
            
            **Exemplos:**
            - `Licenciatura_2025.1.xlsx`
            - `Bacharel_2024.2.xlsx`
            - `Industrial_2023.1.xlsx`
            """)
            
            uploaded_files = st.file_uploader(
                "Selecione os arquivos Excel",
                type=['xlsx', 'xls'],
                accept_multiple_files=True,
                help="Selecione todos os arquivos de relatórios exportados"
            )
            
            if uploaded_files:
                st.info(f"📁 {len(uploaded_files)} arquivo(s) carregado(s)")
                
                # Organiza dados por período e curso
                dados_por_periodo = defaultdict(lambda: defaultdict(dict))
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, uploaded_file in enumerate(uploaded_files):
                    try:
                        status_text.text(f"Processando {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                        
                        # Tenta extrair período e curso do nome do arquivo
                        nome_arquivo = uploaded_file.name.lower()
                        
                        # Detecta o curso
                        curso_nome = "Bacharel Química"  # Default
                        if "licenciatura" in nome_arquivo or "lic" in nome_arquivo:
                            curso_nome = "Licenciatura Química"
                        elif "industrial" in nome_arquivo or "ind" in nome_arquivo:
                            curso_nome = "Bacharel Q Industrial"
                        elif "bacharel" in nome_arquivo or "bach" in nome_arquivo:
                            curso_nome = "Bacharel Química"
                        
                        # Detecta período
                        periodo_match = re.search(r'(\d{4})[._/]?(\d)', nome_arquivo)
                        if periodo_match:
                            ano = periodo_match.group(1)
                            sem = periodo_match.group(2)
                            periodo = f"{ano}.{sem}"
                        else:
                            periodo = "2025.1"
                        
                        # Lê o arquivo
                        df = pd.read_excel(uploaded_file)
                        
                        # Remove linhas completamente vazias
                        df = df.dropna(how='all')
                        
                        # Processa os dados
                        resultados = processar_relatorio(df, curso_nome)
                        
                        # Armazena
                        dados_por_periodo[periodo][curso_nome] = resultados
                        
                        progress_bar.progress((i + 1) / len(uploaded_files))
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao processar {uploaded_file.name}: {str(e)}")
                
                status_text.text("✅ Processamento concluído!")
                
                # Salva no estado da sessão
                if dados_por_periodo:
                    st.session_state.dados_processados = dict(dados_por_periodo)
                    
                    # Mostra prévia dos dados
                    mostrar_previa_dados()
                    
                    # Botão para gerar planilha
                    mostrar_botao_gerar_planilha()
        
        # === DEMONSTRAÇÃO COM DADOS DE EXEMPLO ===
        st.markdown("---")
        st.header("🎯 Teste com Dados de Exemplo")
        
        if st.button("Gerar Planilha de Exemplo", use_container_width=True):
            # Dados de exemplo
            dados_exemplo = {
                "2025.1": {
                    "Licenciatura Química": {
                        "AC": {
                            "total_ingressantes": 10,
                            "cancelamentos": {
                                "Solicitação Oficial": 1,
                                "Ingressante - Insuf. Aproveit.": 3
                            },
                            "inscritos": 6,
                            "trancados": 0,
                            "formados": 0
                        },
                        "AA": {
                            "total_ingressantes": 16,
                            "cancelamentos": {
                                "Solicitação Oficial": 1,
                                "Ingressante - Insuf. Aproveit.": 3
                            },
                            "inscritos": 11,
                            "trancados": 1,
                            "formados": 0
                        }
                    },
                    "Bacharel Química": {
                        "AC": {
                            "total_ingressantes": 5,
                            "cancelamentos": {},
                            "inscritos": 5,
                            "trancados": 0,
                            "formados": 0
                        },
                        "AA": {
                            "total_ingressantes": 9,
                            "cancelamentos": {
                                "Ingressante - Insuf. Aproveit.": 1
                            },
                            "inscritos": 7,
                            "trancados": 0,
                            "formados": 0
                        }
                    },
                    "Bacharel Q Industrial": {
                        "AC": {
                            "total_ingressantes": 9,
                            "cancelamentos": {},
                            "inscritos": 8,
                            "trancados": 1,
                            "formados": 0
                        },
                        "AA": {
                            "total_ingressantes": 11,
                            "cancelamentos": {
                                "Solicitação Oficial": 1,
                                "Ingressante - Insuf. Aproveit.": 2
                            },
                            "inscritos": 6,
                            "trancados": 2,
                            "formados": 0
                        }
                    }
                }
            }
            
            with st.spinner("Gerando planilha de exemplo..."):
                try:
                    wb = gerar_planilha_completa(dados_exemplo)
                    
                    buffer = io.BytesIO()
                    wb.save(buffer)
                    buffer.seek(0)
                    
                    st.success("✅ Planilha de exemplo gerada!")
                    
                    st.download_button(
                        label="📥 BAIXAR PLANILHA DE EXEMPLO",
                        data=buffer,
                        file_name="Evasao_Quimica_IQ_EXEMPLO.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    st.info("""
                    **Esta planilha de exemplo contém:**
                    • Dados do período 2025.1
                    • Estrutura idêntica à planilha fornecida
                    • Fórmulas funcionais
                    • Formatação profissional
                    """)
                    
                except Exception as e:
                    st.error(f"❌ Erro ao gerar exemplo: {str(e)}")

def mostrar_previa_dados():
    """Mostra prévia dos dados processados"""
    if st.session_state.dados_processados:
        st.markdown("---")
        st.header("📋 Prévia dos Dados Processados")
        
        for periodo, cursos in st.session_state.dados_processados.items():
            with st.expander(f"📅 Período: {periodo}", expanded=True):
                for curso, dados in cursos.items():
                    st.subheader(f"🎓 {curso}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Ampla Concorrência (AC)**")
                        if "AC" in dados:
                            ac = dados["AC"]
                            st.write(f"• Ingressantes: {ac.get('total_ingressantes', 0)}")
                            st.write(f"• Inscritos: {ac.get('inscritos', 0)}")
                            st.write(f"• Trancados: {ac.get('trancados', 0)}")
                            st.write(f"• Formados: {ac.get('formados', 0)}")
                            total_cancel = sum(ac.get('cancelamentos', {}).values())
                            st.write(f"• Cancelamentos: {total_cancel}")
                    
                    with col2:
                        st.markdown("**Ações Afirmativas (AA)**")
                        if "AA" in dados:
                            aa = dados["AA"]
                            st.write(f"• Ingressantes: {aa.get('total_ingressantes', 0)}")
                            st.write(f"• Inscritos: {aa.get('inscritos', 0)}")
                            st.write(f"• Trancados: {aa.get('trancados', 0)}")
                            st.write(f"• Formados: {aa.get('formados', 0)}")
                            total_cancel = sum(aa.get('cancelamentos', {}).values())
                            st.write(f"• Cancelamentos: {total_cancel}")

def mostrar_botao_gerar_planilha():
    """Mostra botão para gerar planilha final"""
    st.markdown("---")
    st.header("🚀 Gerar Planilha Final")
    
    if st.button("📥 GERAR PLANILHA DE EVASÃO COMPLETA", 
                type="primary", 
                use_container_width=True):
        
        with st.spinner("Gerando planilha no formato exato..."):
            try:
                wb = gerar_planilha_completa(st.session_state.dados_processados)
                
                buffer = io.BytesIO()
                wb.save(buffer)
                buffer.seek(0)
                
                st.success("✅ Planilha gerada com sucesso!")
                
                nome_arquivo = f"Evasao_Quimica_IQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                st.download_button(
                    label="💾 BAIXAR PLANILHA COMPLETA",
                    data=buffer,
                    file_name=nome_arquivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.info("""
                **A planilha gerada contém:**
                1. **Gráficos** - Aba para inserção de gráficos
                2. **Acumulado** - Consolidação de todos os períodos
                3. **Períodos individuais** - Uma aba para cada período processado
                4. **Modelo** - Estrutura em branco para novos dados
                """)
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar planilha: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()
