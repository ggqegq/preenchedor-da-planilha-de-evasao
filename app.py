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
from openpyxl.utils import get_column_letter
import re
from datetime import datetime
from collections import defaultdict

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
CURSOS_CONFIG = {
    "Licenciatura Química": {"codigo": "12700", "col_ac": 2, "col_aa": 6},
    "Bacharel Química": {"codigo": "312700", "col_ac": 3, "col_aa": 7},
    "Bacharel Q Industrial": {"codigo": "12709", "col_ac": 4, "col_aa": 8}
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
    Código iniciando com 'A' → Ampla Concorrência (AC)
    Código iniciando com 'L' → Ações Afirmativas (AA)
    """
    if not codigo_modalidade or pd.isna(codigo_modalidade):
        return "AC"  # Default para Ampla Concorrência
    
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
    if situacao in SITUACOES_INSCRITOS:
        return "Inscrito", None
    
    # Verifica se é trancado
    if situacao in SITUACOES_TRANCADOS:
        return "Trancado", None
    
    # Verifica se é formado
    if situacao in SITUACOES_FORMADOS:
        return "Formado", None
    
    # Verifica cancelamentos
    for motivo_nome, situacoes_match in MOTIVOS_CANCELAMENTO:
        for s in situacoes_match:
            if s.lower() in situacao.lower() or situacao.lower() in s.lower():
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
            if "Administração Acadêmica" in response.text or "Sair" in response.text:
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
            
            if response.status_code == 200:
                if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in response.headers.get('Content-Type', ''):
                    return response.content, "Relatório gerado com sucesso"
                else:
                    return self._aguardar_relatorio(response)
            
            return None, "Erro ao gerar relatório"
            
        except Exception as e:
            return None, f"Erro ao gerar relatório: {str(e)}"
    
    def _aguardar_relatorio(self, initial_response):
        """Aguarda a geração do relatório"""
        try:
            soup = BeautifulSoup(initial_response.text, 'html.parser')
            
            status_container = soup.find('div', {'id': 'statusUpdateContainer'})
            if status_container:
                relatorio_id = status_container.get('data-id')
                
                for _ in range(60):
                    time.sleep(5)
                    
                    status_response = self.session.get(
                        f"{ADMIN_ACAD_URL}/relatorios/{relatorio_id}"
                    )
                    
                    if 'download' in status_response.text.lower():
                        download_response = self.session.get(
                            f"{ADMIN_ACAD_URL}/relatorios/{relatorio_id}/download"
                        )
                        
                        if download_response.status_code == 200:
                            return download_response.content, "Relatório baixado com sucesso"
                
                return None, "Timeout aguardando geração do relatório"
            
            return None, "Não foi possível identificar o relatório"
            
        except Exception as e:
            return None, f"Erro ao aguardar relatório: {str(e)}"


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
    
    # Encontra as colunas relevantes
    col_situacao = None
    col_modalidade = None
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'situação' in col_lower or 'situacao' in col_lower:
            col_situacao = col
        if 'modalidade' in col_lower:
            col_modalidade = col
    
    if col_situacao is None:
        return resultados
    
    # Processa cada linha
    for idx, row in df.iterrows():
        # Classifica modalidade
        modalidade = "AC"
        if col_modalidade and col_modalidade in row:
            modalidade = classificar_modalidade(row[col_modalidade])
        
        # Conta ingressante
        resultados[modalidade]["total_ingressantes"] += 1
        
        # Categoriza situação
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


def gerar_planilha_evasao(dados_por_periodo_curso):
    """
    Gera a planilha de evasão no formato exato do modelo fornecido.
    
    dados_por_periodo_curso: dict com estrutura:
    {
        "2025.1": {
            "Licenciatura Química": {"AC": {...}, "AA": {...}},
            "Bacharel Química": {"AC": {...}, "AA": {...}},
            "Bacharel Q Industrial": {"AC": {...}, "AA": {...}}
        },
        ...
    }
    """
    
    wb = Workbook()
    
    # Estilos
    header_fill_azul = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_fill_verde = PatternFill(start_color="548235", end_color="548235", fill_type="solid")
    header_fill_laranja = PatternFill(start_color="C65911", end_color="C65911", fill_type="solid")
    header_fill_cinza = PatternFill(start_color="808080", end_color="808080", fill_type="solid")
    
    fill_vermelho = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
    fill_verde_claro = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
    fill_amarelo = PatternFill(start_color="FFFF99", end_color="FFFF99", fill_type="solid")
    
    header_font_branco = Font(bold=True, color="FFFFFF")
    header_font_preto = Font(bold=True, color="000000")
    normal_font = Font(color="000000")
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    
    # Remove planilha padrão
    wb.remove(wb.active)
    
    # Ordena períodos do mais recente para o mais antigo
    periodos_ordenados = sorted(dados_por_periodo_curso.keys(), reverse=True)
    
    # Cria aba de Gráficos primeiro (será preenchida depois)
    ws_graficos = wb.create_sheet(title="Gráficos")
    ws_graficos['A1'] = "Gráficos serão adicionados manualmente"
    
    # Cria aba Acumulada
    ws_acumulado = wb.create_sheet(title=f"Acumulado de {periodos_ordenados[0]} a {periodos_ordenados[-1]}")
    
    # Para cada período, cria uma aba
    for periodo in periodos_ordenados:
        dados_cursos = dados_por_periodo_curso[periodo]
        
        # Nome da aba (formato: 2025.1)
        nome_aba = periodo.replace("/", ".").replace("°", "")
        ws = wb.create_sheet(title=nome_aba)
        
        # === LINHA 1: Título principal ===
        ws.merge_cells('A1:K1')
        cell = ws['A1']
        cell.value = "QUÍMICA IQ - LEVANTAMENTO MATRÍCULAS SISU"
        cell.font = header_font_branco
        cell.fill = header_fill_azul
        cell.alignment = center_alignment
        cell.border = border
        
        # === LINHA 2: Cabeçalho de grupos ===
        # Coluna A vazia
        ws.cell(row=2, column=1, value="Modalidade").font = header_font_branco
        ws.cell(row=2, column=1).fill = header_fill_azul
        ws.cell(row=2, column=1).alignment = center_alignment
        ws.cell(row=2, column=1).border = border
        
        # AMPLA CONCORRÊNCIA (B-E)
        ws.merge_cells('B2:E2')
        cell = ws['B2']
        cell.value = "AMPLA CONCORRÊNCIA"
        cell.font = header_font_branco
        cell.fill = header_fill_azul
        cell.alignment = center_alignment
        for col in range(2, 6):
            ws.cell(row=2, column=col).border = border
        
        # AÇÕES AFIRMATIVAS (F-I)
        ws.merge_cells('F2:I2')
        cell = ws['F2']
        cell.value = "AÇÕES AFIRMATIVAS"
        cell.font = header_font_branco
        cell.fill = header_fill_verde
        cell.alignment = center_alignment
        for col in range(6, 10):
            ws.cell(row=2, column=col).border = border
        
        # TOTAIS (J-K)
        ws.merge_cells('J2:K2')
        cell = ws['J2']
        cell.value = "TOTAIS"
        cell.font = header_font_branco
        cell.fill = header_fill_laranja
        cell.alignment = center_alignment
        for col in range(10, 12):
            ws.cell(row=2, column=col).border = border
        
        # === LINHA 3: Cabeçalho de cursos ===
        headers_row3 = [
            ("Curso", header_fill_azul),
            ("Licenciatura Química", header_fill_azul),
            ("Bacharel Química", header_fill_azul),
            ("Bacharel Q Industrial", header_fill_azul),
            ("TOTAL (AC)", header_fill_azul),
            ("Licenciatura Química", header_fill_verde),
            ("Bacharel Química", header_fill_verde),
            ("Bacharel Q Industrial", header_fill_verde),
            ("TOTAL (AA)", header_fill_verde),
            ("TOTAL GERAL", header_fill_laranja),
            ("% GERAL", header_fill_laranja)
        ]
        
        for col, (header, fill) in enumerate(headers_row3, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.font = header_font_branco
            cell.fill = fill
            cell.alignment = center_alignment
            cell.border = border
        
        # Extrai dados de cada curso
        lic_quim = dados_cursos.get("Licenciatura Química", {"AC": {}, "AA": {}})
        bach_quim = dados_cursos.get("Bacharel Química", {"AC": {}, "AA": {}})
        bach_ind = dados_cursos.get("Bacharel Q Industrial", {"AC": {}, "AA": {}})
        
        # Função auxiliar para obter valor com default
        def get_val(dados, modalidade, chave, sub_chave=None):
            if modalidade not in dados:
                dados[modalidade] = {"total_ingressantes": 0, "cancelamentos": {}, "inscritos": 0, "trancados": 0, "formados": 0}
            if sub_chave:
                return dados[modalidade].get(chave, {}).get(sub_chave, 0)
            return dados[modalidade].get(chave, 0)
        
        # === LINHA 4: Total de Ingressantes ===
        row = 4
        ws.cell(row=row, column=1, value="Total de Ingressantes").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
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
        
        valores_row4 = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac, 
                        val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                        total_geral, "-"]
        
        for col, val in enumerate(valores_row4, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === LINHA 5: Seção CANCELAMENTOS ===
        row = 5
        ws.merge_cells(f'A{row}:K{row}')
        cell = ws.cell(row=row, column=1, value="CANCELAMENTOS")
        cell.font = header_font_preto
        cell.fill = header_fill_cinza
        cell.alignment = center_alignment
        cell.border = border
        
        # === LINHAS 6-10: Motivos de cancelamento ===
        motivos_ordem = [
            "Solicitação Oficial",
            "Abandono", 
            "Insuficiência de Aproveitamento",
            "Ingressante - Insuf. Aproveit.",
            "Mudança de Curso"
        ]
        
        for motivo in motivos_ordem:
            row += 1
            ws.cell(row=row, column=1, value=motivo).border = border
            ws.cell(row=row, column=1).alignment = left_alignment
            
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
            total_ingressantes = dados_cursos.get("_total_geral", total_geral) or 1
            pct = f"{(total_geral / total_ingressantes * 100):.2f}%" if total_ingressantes > 0 else "0,00%"
            
            valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                      val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                      total_geral, pct]
            
            for col, val in enumerate(valores, 2):
                cell = ws.cell(row=row, column=col, value=val)
                cell.alignment = center_alignment
                cell.border = border
        
        # === LINHA: TOTAL CANCELAMENTOS ===
        row += 1
        ws.cell(row=row, column=1, value="TOTAL CANCELAMENTOS").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        ws.cell(row=row, column=1).font = Font(bold=True)
        
        # Soma de todos os cancelamentos
        def soma_cancelamentos(dados, modalidade):
            if modalidade not in dados:
                return 0
            return sum(dados[modalidade].get("cancelamentos", {}).values())
        
        val_lic_ac = soma_cancelamentos(lic_quim, "AC")
        val_bach_ac = soma_cancelamentos(bach_quim, "AC")
        val_ind_ac = soma_cancelamentos(bach_ind, "AC")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = soma_cancelamentos(lic_quim, "AA")
        val_bach_aa = soma_cancelamentos(bach_quim, "AA")
        val_ind_aa = soma_cancelamentos(bach_ind, "AA")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        total_ingressantes_geral = (get_val(lic_quim, "AC", "total_ingressantes") + 
                                    get_val(bach_quim, "AC", "total_ingressantes") + 
                                    get_val(bach_ind, "AC", "total_ingressantes") +
                                    get_val(lic_quim, "AA", "total_ingressantes") + 
                                    get_val(bach_quim, "AA", "total_ingressantes") + 
                                    get_val(bach_ind, "AA", "total_ingressantes"))
        
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
            cell.font = Font(bold=True)
        
        # === LINHA: Seção MATRÍCULAS ATIVAS ===
        row += 1
        ws.merge_cells(f'A{row}:K{row}')
        cell = ws.cell(row=row, column=1, value="MATRÍCULAS ATIVAS")
        cell.font = header_font_preto
        cell.fill = header_fill_cinza
        cell.alignment = center_alignment
        cell.border = border
        
        # === LINHA: Inscritos ===
        row += 1
        ws.cell(row=row, column=1, value="Inscritos").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        val_lic_ac = get_val(lic_quim, "AC", "inscritos")
        val_bach_ac = get_val(bach_quim, "AC", "inscritos")
        val_ind_ac = get_val(bach_ind, "AC", "inscritos")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = get_val(lic_quim, "AA", "inscritos")
        val_bach_aa = get_val(bach_quim, "AA", "inscritos")
        val_ind_aa = get_val(bach_ind, "AA", "inscritos")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === LINHA: Trancados ===
        row += 1
        ws.cell(row=row, column=1, value="Trancados").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        val_lic_ac = get_val(lic_quim, "AC", "trancados")
        val_bach_ac = get_val(bach_quim, "AC", "trancados")
        val_ind_ac = get_val(bach_ind, "AC", "trancados")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = get_val(lic_quim, "AA", "trancados")
        val_bach_aa = get_val(bach_quim, "AA", "trancados")
        val_ind_aa = get_val(bach_ind, "AA", "trancados")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === LINHA: TOTAL MATRIC. ATIVAS ===
        row += 1
        ws.cell(row=row, column=1, value="TOTAL MATRIC. ATIVAS").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        ws.cell(row=row, column=1).font = Font(bold=True)
        
        val_lic_ac = get_val(lic_quim, "AC", "inscritos") + get_val(lic_quim, "AC", "trancados")
        val_bach_ac = get_val(bach_quim, "AC", "inscritos") + get_val(bach_quim, "AC", "trancados")
        val_ind_ac = get_val(bach_ind, "AC", "inscritos") + get_val(bach_ind, "AC", "trancados")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = get_val(lic_quim, "AA", "inscritos") + get_val(lic_quim, "AA", "trancados")
        val_bach_aa = get_val(bach_quim, "AA", "inscritos") + get_val(bach_quim, "AA", "trancados")
        val_ind_aa = get_val(bach_ind, "AA", "inscritos") + get_val(bach_ind, "AA", "trancados")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
            cell.font = Font(bold=True)
        
        # === LINHA: Seção SITUAÇÃO ATUAL ===
        row += 1
        ws.merge_cells(f'A{row}:K{row}')
        cell = ws.cell(row=row, column=1, value="SITUAÇÃO ATUAL")
        cell.font = header_font_preto
        cell.fill = header_fill_cinza
        cell.alignment = center_alignment
        cell.border = border
        
        # === LINHA: Matrículas Ativas (repetição) ===
        row += 1
        ws.cell(row=row, column=1, value="Matrículas Ativas").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        val_lic_ac = get_val(lic_quim, "AC", "inscritos") + get_val(lic_quim, "AC", "trancados")
        val_bach_ac = get_val(bach_quim, "AC", "inscritos") + get_val(bach_quim, "AC", "trancados")
        val_ind_ac = get_val(bach_ind, "AC", "inscritos") + get_val(bach_ind, "AC", "trancados")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = get_val(lic_quim, "AA", "inscritos") + get_val(lic_quim, "AA", "trancados")
        val_bach_aa = get_val(bach_quim, "AA", "inscritos") + get_val(bach_quim, "AA", "trancados")
        val_ind_aa = get_val(bach_ind, "AA", "inscritos") + get_val(bach_ind, "AA", "trancados")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === LINHA: Alunos Formados ===
        row += 1
        ws.cell(row=row, column=1, value="Alunos Formados").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        val_lic_ac = get_val(lic_quim, "AC", "formados")
        val_bach_ac = get_val(bach_quim, "AC", "formados")
        val_ind_ac = get_val(bach_ind, "AC", "formados")
        total_ac = val_lic_ac + val_bach_ac + val_ind_ac
        
        val_lic_aa = get_val(lic_quim, "AA", "formados")
        val_bach_aa = get_val(bach_quim, "AA", "formados")
        val_ind_aa = get_val(bach_ind, "AA", "formados")
        total_aa = val_lic_aa + val_bach_aa + val_ind_aa
        
        total_geral = total_ac + total_aa
        pct = f"{(total_geral / total_ingressantes_geral * 100):.2f}%" if total_ingressantes_geral > 0 else "0,00%"
        
        valores = [val_lic_ac, val_bach_ac, val_ind_ac, total_ac,
                  val_lic_aa, val_bach_aa, val_ind_aa, total_aa,
                  total_geral, pct]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === LINHA: Seção MÉTRICAS FINAIS (%) ===
        row += 1
        ws.merge_cells(f'A{row}:K{row}')
        cell = ws.cell(row=row, column=1, value="MÉTRICAS FINAIS (%)")
        cell.font = header_font_preto
        cell.fill = header_fill_cinza
        cell.alignment = center_alignment
        cell.border = border
        
        # === LINHA: % Cancelamento ===
        row += 1
        ws.cell(row=row, column=1, value="% Cancelamento").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        def calc_pct_cancelamento(dados, modalidade):
            total_ing = get_val(dados, modalidade, "total_ingressantes")
            total_canc = soma_cancelamentos(dados, modalidade)
            if total_ing > 0:
                return total_canc / total_ing * 100
            return 0
        
        pct_lic_ac = calc_pct_cancelamento(lic_quim, "AC")
        pct_bach_ac = calc_pct_cancelamento(bach_quim, "AC")
        pct_ind_ac = calc_pct_cancelamento(bach_ind, "AC")
        
        pct_lic_aa = calc_pct_cancelamento(lic_quim, "AA")
        pct_bach_aa = calc_pct_cancelamento(bach_quim, "AA")
        pct_ind_aa = calc_pct_cancelamento(bach_ind, "AA")
        
        # Total AC e AA
        total_ing_ac = (get_val(lic_quim, "AC", "total_ingressantes") + 
                       get_val(bach_quim, "AC", "total_ingressantes") + 
                       get_val(bach_ind, "AC", "total_ingressantes"))
        total_canc_ac = (soma_cancelamentos(lic_quim, "AC") + 
                        soma_cancelamentos(bach_quim, "AC") + 
                        soma_cancelamentos(bach_ind, "AC"))
        pct_total_ac = (total_canc_ac / total_ing_ac * 100) if total_ing_ac > 0 else 0
        
        total_ing_aa = (get_val(lic_quim, "AA", "total_ingressantes") + 
                       get_val(bach_quim, "AA", "total_ingressantes") + 
                       get_val(bach_ind, "AA", "total_ingressantes"))
        total_canc_aa = (soma_cancelamentos(lic_quim, "AA") + 
                        soma_cancelamentos(bach_quim, "AA") + 
                        soma_cancelamentos(bach_ind, "AA"))
        pct_total_aa = (total_canc_aa / total_ing_aa * 100) if total_ing_aa > 0 else 0
        
        pct_geral = ((total_canc_ac + total_canc_aa) / total_ingressantes_geral * 100) if total_ingressantes_geral > 0 else 0
        
        valores = [f"{pct_lic_ac:.2f}%", f"{pct_bach_ac:.2f}%", f"{pct_ind_ac:.2f}%", f"{pct_total_ac:.2f}%",
                  f"{pct_lic_aa:.2f}%", f"{pct_bach_aa:.2f}%", f"{pct_ind_aa:.2f}%", f"{pct_total_aa:.2f}%",
                  f"{pct_geral:.2f}%", "-"]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
            # Aplica cores condicionais
            try:
                pct_val = float(val.replace("%", "").replace(",", "."))
                if pct_val == 0:
                    cell.fill = fill_verde_claro
                elif pct_val < 10:
                    cell.fill = fill_amarelo
                else:
                    cell.fill = fill_vermelho
            except:
                pass
        
        # === LINHA: % de Alunos Formados ===
        row += 1
        ws.cell(row=row, column=1, value="% de Alunos Formados").border = border
        ws.cell(row=row, column=1).alignment = left_alignment
        
        def calc_pct_formados(dados, modalidade):
            total_ing = get_val(dados, modalidade, "total_ingressantes")
            total_form = get_val(dados, modalidade, "formados")
            if total_ing > 0:
                return total_form / total_ing * 100
            return 0
        
        pct_lic_ac = calc_pct_formados(lic_quim, "AC")
        pct_bach_ac = calc_pct_formados(bach_quim, "AC")
        pct_ind_ac = calc_pct_formados(bach_ind, "AC")
        
        pct_lic_aa = calc_pct_formados(lic_quim, "AA")
        pct_bach_aa = calc_pct_formados(bach_quim, "AA")
        pct_ind_aa = calc_pct_formados(bach_ind, "AA")
        
        total_form_ac = (get_val(lic_quim, "AC", "formados") + 
                        get_val(bach_quim, "AC", "formados") + 
                        get_val(bach_ind, "AC", "formados"))
        pct_total_ac = (total_form_ac / total_ing_ac * 100) if total_ing_ac > 0 else 0
        
        total_form_aa = (get_val(lic_quim, "AA", "formados") + 
                        get_val(bach_quim, "AA", "formados") + 
                        get_val(bach_ind, "AA", "formados"))
        pct_total_aa = (total_form_aa / total_ing_aa * 100) if total_ing_aa > 0 else 0
        
        pct_geral = ((total_form_ac + total_form_aa) / total_ingressantes_geral * 100) if total_ingressantes_geral > 0 else 0
        
        valores = [f"{pct_lic_ac:.2f}%", f"{pct_bach_ac:.2f}%", f"{pct_ind_ac:.2f}%", f"{pct_total_ac:.2f}%",
                  f"{pct_lic_aa:.2f}%", f"{pct_bach_aa:.2f}%", f"{pct_ind_aa:.2f}%", f"{pct_total_aa:.2f}%",
                  f"{pct_geral:.2f}%", "-"]
        
        for col, val in enumerate(valores, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center_alignment
            cell.border = border
        
        # === Ajusta largura das colunas ===
        ws.column_dimensions['A'].width = 28
        for col in range(2, 12):
            ws.column_dimensions[get_column_letter(col)].width = 14
    
    return wb


# ==================== INTERFACE STREAMLIT ====================

def main():
    st.title("Cálculo de Evasão - Cursos de Química UFF")
    st.markdown("---")
    
    # Inicializa estado da sessão
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'sistema' not in st.session_state:
        st.session_state.sistema = SistemaAcademicoUFF()
    if 'dados_processados' not in st.session_state:
        st.session_state.dados_processados = {}
    
    # Sidebar
    with st.sidebar:
        st.header("Informações")
        st.markdown("""
        **Regras de Classificação:**
        - Código com 'A' = Ampla Concorrência
        - Código com 'L' = Ações Afirmativas
        
        **Cursos:**
        - Licenciatura Química (12700)
        - Bacharel Química (312700)
        - Bacharel Q. Industrial (12709)
        """)
    
    # === SEÇÃO DE LOGIN ===
    if not st.session_state.logged_in:
        st.header("Login no Sistema Acadêmico")
        
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("IdUFF (CPF, email ou passaporte)")
        with col2:
            password = st.text_input("Senha", type="password")
        
        if st.button("Fazer Login", type="primary"):
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
        st.success("Logado no sistema acadêmico")
        
        if st.button("Sair"):
            st.session_state.logged_in = False
            st.session_state.sistema = SistemaAcademicoUFF()
            st.session_state.dados_processados = {}
            st.rerun()
        
        st.markdown("---")
        
        # === UPLOAD DE RELATÓRIOS ===
        st.header("Upload dos Relatórios Excel")
        st.markdown("""
        Faça upload dos relatórios exportados do sistema. 
        **Nomeie os arquivos no formato:** `CURSO_PERIODO.xlsx`
        
        Exemplos:
        - `Licenciatura_2025.1.xlsx`
        - `Bacharel_2024.2.xlsx`
        - `Industrial_2023.1.xlsx`
        """)
        
        uploaded_files = st.file_uploader(
            "Selecione os arquivos Excel",
            type=['xlsx', 'xls'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.info(f"{len(uploaded_files)} arquivo(s) carregado(s)")
            
            # Organiza dados por período e curso
            dados_por_periodo = defaultdict(lambda: defaultdict(dict))
            
            for uploaded_file in uploaded_files:
                try:
                    # Tenta extrair período e curso do nome do arquivo
                    nome_arquivo = uploaded_file.name.replace(".xlsx", "").replace(".xls", "")
                    
                    # Detecta o curso pelo nome
                    curso_nome = "Bacharel Química"  # Default
                    if "licenciatura" in nome_arquivo.lower() or "lic" in nome_arquivo.lower():
                        curso_nome = "Licenciatura Química"
                    elif "industrial" in nome_arquivo.lower() or "ind" in nome_arquivo.lower():
                        curso_nome = "Bacharel Q Industrial"
                    elif "bacharel" in nome_arquivo.lower() or "bach" in nome_arquivo.lower():
                        curso_nome = "Bacharel Química"
                    
                    # Detecta período (formato: 2025.1 ou 2025/1)
                    periodo_match = re.search(r'(\d{4})[._/](\d)', nome_arquivo)
                    if periodo_match:
                        periodo = f"{periodo_match.group(1)}.{periodo_match.group(2)}"
                    else:
                        periodo = "2025.1"  # Default
                    
                    # Lê o arquivo Excel
                    df = pd.read_excel(uploaded_file, skiprows=3)
                    
                    # Remove linhas vazias e linhas de resumo
                    df = df.dropna(how='all')
                    df = df[~df.iloc[:, 0].astype(str).str.contains('Alunos de', na=False)]
                    
                    # Processa os dados
                    resultados = processar_relatorio(df, curso_nome)
                    
                    # Armazena nos dados organizados
                    dados_por_periodo[periodo][curso_nome] = resultados
                    
                    st.success(f"{uploaded_file.name}: {len(df)} registros - Período: {periodo} - Curso: {curso_nome}")
                    
                except Exception as e:
                    st.error(f"Erro ao processar {uploaded_file.name}: {str(e)}")
            
            # Salva no estado da sessão
            st.session_state.dados_processados = dict(dados_por_periodo)
            
            # === PRÉVIA DOS DADOS ===
            if st.session_state.dados_processados:
                st.markdown("---")
                st.header("Prévia dos Dados Processados")
                
                for periodo, cursos in st.session_state.dados_processados.items():
                    with st.expander(f"Período: {periodo}"):
                        for curso, dados in cursos.items():
                            st.subheader(curso)
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Ampla Concorrência (AC):**")
                                if "AC" in dados:
                                    st.write(f"- Total ingressantes: {dados['AC'].get('total_ingressantes', 0)}")
                                    st.write(f"- Inscritos: {dados['AC'].get('inscritos', 0)}")
                                    st.write(f"- Trancados: {dados['AC'].get('trancados', 0)}")
                                    st.write(f"- Formados: {dados['AC'].get('formados', 0)}")
                                    st.write(f"- Cancelamentos: {sum(dados['AC'].get('cancelamentos', {}).values())}")
                            
                            with col2:
                                st.write("**Ações Afirmativas (AA):**")
                                if "AA" in dados:
                                    st.write(f"- Total ingressantes: {dados['AA'].get('total_ingressantes', 0)}")
                                    st.write(f"- Inscritos: {dados['AA'].get('inscritos', 0)}")
                                    st.write(f"- Trancados: {dados['AA'].get('trancados', 0)}")
                                    st.write(f"- Formados: {dados['AA'].get('formados', 0)}")
                                    st.write(f"- Cancelamentos: {sum(dados['AA'].get('cancelamentos', {}).values())}")
                
                # === BOTÃO PARA GERAR PLANILHA ===
                st.markdown("---")
                if st.button("GERAR PLANILHA DE EVASÃO", type="primary", use_container_width=True):
                    with st.spinner("Gerando planilha..."):
                        try:
                            wb = gerar_planilha_evasao(st.session_state.dados_processados)
                            
                            buffer = io.BytesIO()
                            wb.save(buffer)
                            buffer.seek(0)
                            
                            st.success("Planilha gerada com sucesso!")
                            
                            st.download_button(
                                label="BAIXAR PLANILHA DE EVASÃO",
                                data=buffer,
                                file_name=f"Evasao_Quimica_IQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Erro ao gerar planilha: {str(e)}")
        
        # === DEMONSTRAÇÃO ===
        st.markdown("---")
        st.header("Demonstração com Dados de Exemplo")
        
        if st.button("Gerar Planilha de Exemplo (baseada na imagem fornecida)"):
            # Dados de exemplo baseados na imagem
            dados_exemplo = {
                "2025.1": {
                    "Licenciatura Química": {
                        "AC": {"total_ingressantes": 10, "cancelamentos": {"Solicitação Oficial": 1}, "inscritos": 6, "trancados": 0, "formados": 0},
                        "AA": {"total_ingressantes": 16, "cancelamentos": {"Solicitação Oficial": 1, "Ingressante - Insuf. Aproveit.": 3}, "inscritos": 11, "trancados": 1, "formados": 0}
                    },
                    "Bacharel Química": {
                        "AC": {"total_ingressantes": 5, "cancelamentos": {}, "inscritos": 5, "trancados": 0, "formados": 0},
                        "AA": {"total_ingressantes": 9, "cancelamentos": {}, "inscritos": 7, "trancados": 0, "formados": 0}
                    },
                    "Bacharel Q Industrial": {
                        "AC": {"total_ingressantes": 9, "cancelamentos": {}, "inscritos": 8, "trancados": 1, "formados": 0},
                        "AA": {"total_ingressantes": 11, "cancelamentos": {"Ingressante - Insuf. Aproveit.": 2}, "inscritos": 6, "trancados": 2, "formados": 0}
                    }
                }
            }
            
            with st.spinner("Gerando planilha de exemplo..."):
                wb = gerar_planilha_evasao(dados_exemplo)
                
                buffer = io.BytesIO()
                wb.save(buffer)
                buffer.seek(0)
                
                st.success("Planilha de exemplo gerada!")
                
                st.download_button(
                    label="BAIXAR PLANILHA DE EXEMPLO",
                    data=buffer,
                    file_name="Evasao_Quimica_EXEMPLO.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )


if __name__ == "__main__":
    main()
