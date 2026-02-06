# gerador_relatorios.py
"""
gerador_relatorios.py - Módulo para geração automatizada de relatórios
"""
import logging
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

from config import *
from formulario_handler import FormularioHandler
from relatorio_automator import RelatorioUFFAutomator
from utils import *

logger = logging.getLogger(__name__)

class GeradorRelatorios:
    """Classe para gerar relatórios em lote para múltiplos cursos e períodos"""
    
    def __init__(self, session):
        self.session = session
        self.form_handler = FormularioHandler(session)
        self.rel_automator = RelatorioUFFAutomator(session)
        self.resultados = {}
    
    def obter_desdobramentos_curso(self, curso_id, localidade_id='1'):
        """Obtém os desdobramentos disponíveis para um curso"""
        try:
            url = f"{APLICACAO_URL}/relatorios/listagens_alunos"
            response = self.session.get(url, timeout=TIMEOUT_REQUESTS)
            
            # Primeiro, obter cursos disponíveis para a localidade
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Construir dados para buscar desdobramentos via AJAX
            dados_curso = {
                'authenticity_token': self._extrair_csrf_token(soup),
                'idlocalidade': localidade_id,
                'idcurso': curso_id
            }
            
            # URL para buscar desdobramentos (via análise do JavaScript)
            url_desdobramentos = f"{APLICACAO_URL}/relatorios/buscar_desdobramentos"
            
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
            
            response = self.session.post(
                url_desdobramentos,
                data=dados_curso,
                headers=headers,
                timeout=TIMEOUT_REQUESTS
            )
            
            if response.status_code == 200:
                try:
                    dados = response.json()
                    if dados.get('success'):
                        return dados.get('desdobramentos', [])
                except:
                    # Se não for JSON, tentar parsear HTML
                    soup_desdob = BeautifulSoup(response.text, 'html.parser')
                    options = soup_desdob.find_all('option')
                    desdobramentos = []
                    for option in options:
                        if option.get('value') and option.get('value') != '':
                            desdobramentos.append({
                                'value': option.get('value'),
                                'text': option.get_text(strip=True)
                            })
                    return desdobramentos
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao obter desdobramentos: {str(e)}")
            return []
    
    def _extrair_csrf_token(self, soup):
        """Extrai token CSRF da página"""
        token_input = soup.find('input', {'name': 'authenticity_token'})
        if token_input:
            return token_input.get('value', '')
        
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token:
            return meta_token.get('content', '')
        
        return ''
    
    def criar_filtros_para_curso(self, curso_config, periodo, forma_ingresso):
        """Cria dicionário de filtros para um curso específico"""
        filtros = {
            'idlocalidade': '1',  # Niterói
            'idcurso': curso_config['codigo_curso'],
            'iddesdobramento': curso_config['codigo_desdobramento'],
            'idturno': '',  # Todos os turnos
            'idstatusaluno': '',  # Todos os status
            'idsituacaoaluno': '',  # Todas as situações
            'idformaingresso': forma_ingresso,
            'idacaoafirmativa': '',  # Todas as modalidades
            'anosem_ingresso': periodo,
            'anosem_desvinculacao': '',  # Não filtrar por desvinculação
            'format': 'xls'  # Formato XLSX
        }
        return filtros
    
    def gerar_relatorio_individual(self, curso_config, periodo, forma_ingresso):
        """Gera um relatório individual para curso/período específico"""
        logger.info(f"Gerando relatório: {curso_config['nome']} - Período {periodo}")
        
        try:
            # Criar filtros
            filtros = self.criar_filtros_para_curso(curso_config, periodo, forma_ingresso)
            
            # Gerar relatório usando FormularioHandler
            resultado = self.form_handler.gerar_relatorio(filtros)
            
            if resultado.get('success') and resultado.get('relatorio_id'):
                relatorio_id = resultado['relatorio_id']
                
                # Monitorar processamento
                status_info = self.rel_automator.aguardar_conclusao(
                    relatorio_id=relatorio_id,
                    callback_progresso=self._callback_progresso,
                    timeout=1800  # 30 minutos
                )
                
                if status_info and status_info.get('status') == 'PRONTO':
                    # Baixar relatório
                    caminho_arquivo = self.rel_automator.baixar_relatorio(status_info)
                    
                    if caminho_arquivo:
                        return {
                            'success': True,
                            'relatorio_id': relatorio_id,
                            'caminho_arquivo': caminho_arquivo,
                            'status_info': status_info,
                            'curso': curso_config['nome'],
                            'periodo': periodo
                        }
            
            return {
                'success': False,
                'error': resultado.get('error', 'Erro desconhecido'),
                'curso': curso_config['nome'],
                'periodo': periodo
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'curso': curso_config['nome'],
                'periodo': periodo
            }
    
    def _callback_progresso(self, progresso, mensagem, concluido):
        """Callback para atualização de progresso"""
        logger.info(f"Progresso: {progresso:.1%} - {mensagem}")
    
    def gerar_relatorios_em_lote(self, cursos, periodos):
        """Gera relatórios para todos os cursos e períodos especificados"""
        logger.info(f"Iniciando geração em lote: {len(cursos)} cursos × {len(periodos)} períodos")
        
        resultados = {}
        
        for curso in cursos:
            resultados_curso = []
            
            for periodo in periodos:
                # Determinar forma de ingresso baseada no semestre
                forma_ingresso = self._determinar_forma_ingresso(periodo)
                
                # Gerar relatório
                resultado = self.gerar_relatorio_individual(curso, periodo, forma_ingresso)
                resultados_curso.append(resultado)
                
                # Aguardar entre requisições para não sobrecarregar o servidor
                time.sleep(5)
            
            resultados[curso['nome']] = resultados_curso
        
        self.resultados = resultados
        return resultados
    
    def _determinar_forma_ingresso(self, periodo):
        """Determina a forma de ingresso baseada no semestre do período"""
        # Extrair semestre do período (ex: "20251" → semestre 1)
        if periodo.endswith('1'):  # 1º semestre
            return '125'  # SISU 1ª Edição
        else:  # 2º semestre
            return '124'  # SISU 2ª Edição
    
    def processar_periodos_intervalo(self, periodo_inicial, periodo_final):
        """Gera lista de períodos entre o inicial e final"""
        # Extrair ano e semestre dos períodos
        def parse_periodo(periodo):
            ano = int(periodo[:4])
            semestre = int(periodo[4])
            return ano, semestre
        
        ano_inicial, sem_inicial = parse_periodo(periodo_inicial)
        ano_final, sem_final = parse_periodo(periodo_final)
        
        periodos = []
        
        ano_atual = ano_inicial
        sem_atual = sem_inicial
        
        while (ano_atual < ano_final) or (ano_atual == ano_final and sem_atual <= sem_final):
            periodos.append(f"{ano_atual}{sem_atual}")
            
            # Avançar para próximo período
            if sem_atual == 1:
                sem_atual = 2
            else:
                sem_atual = 1
                ano_atual += 1
        
        return periodos
    
    def obter_cursos_predefinidos(self):
        """Retorna configuração dos cursos predefinidos"""
        return [
            {
                'nome': 'Química (Licenciatura)',
                'codigo_curso': '12700',  # Código do curso Química
                'codigo_desdobramento': '12700',  # Desdobramento específico
                'tipo': 'Licenciatura'
            },
            {
                'nome': 'Química (Bacharelado)',
                'codigo_curso': '12700',  # Código do curso Química
                'codigo_desdobramento': '312700',  # Desdobramento específico
                'tipo': 'Bacharelado'
            },
            {
                'nome': 'Química Industrial',
                'codigo_curso': '12709',  # Código do curso Química Industrial
                'codigo_desdobramento': '12709',  # Desdobramento específico
                'tipo': 'Bacharelado'
            }
        ]


class ProcessadorDadosRelatorios:
    """Classe para processar e analisar dados dos relatórios baixados"""
    
    def __init__(self, pasta_relatorios=PASTA_RELATORIOS):
        self.pasta_relatorios = pasta_relatorios
    
    def ler_relatorio_excel(self, caminho_arquivo):
        """Lê um arquivo Excel e retorna DataFrame"""
        try:
            df = pd.read_excel(caminho_arquivo)
            logger.info(f"Arquivo lido: {len(df)} linhas, {len(df.columns)} colunas")
            return df
        except Exception as e:
            logger.error(f"Erro ao ler arquivo Excel: {str(e)}")
            return None
    
    def extrair_dados_relatorio(self, df, curso, periodo):
        """Extrai e processa dados do relatório"""
        if df is None or df.empty:
            return None
        
        dados = {
            'curso': curso,
            'periodo': periodo,
            'total_registros': len(df),
            'categorias': {}
        }
        
        # Mapeamento de situações
        situacoes_normalizadas = {
            'Inscrito': 'Inscritos/Pendentes/Concluintes',
            'Concluinte': 'Inscritos/Pendentes/Concluintes',
            'Pendente': 'Inscritos/Pendentes/Concluintes',
            'Trancado': 'Trancados',
            'Formando': 'Formados',
            'Formado': 'Formados',
            'Permanência de Vínculo': 'Formados'
        }
        
        # Classificar por situação
        if 'SITUAÇÃO' in df.columns:
            situacoes = df['SITUAÇÃO'].fillna('Desconhecido')
            
            for situacao_original, situacao_normalizada in situacoes_normalizadas.items():
                contagem = situacoes[situacoes.str.contains(situacao_original, case=False, na=False)].shape[0]
                if contagem > 0:
                    if situacao_normalizada not in dados['categorias']:
                        dados['categorias'][situacao_normalizada] = 0
                    dados['categorias'][situacao_normalizada] += contagem
        
        # Contar cancelamentos
        if 'MOTIVO DO CANCELAMENTO' in df.columns:
            motivos = df['MOTIVO DO CANCELAMENTO'].fillna('')
            cancelamentos = motivos[motivos != '']
            dados['total_cancelamentos'] = len(cancelamentos)
            
            # Classificar motivos de cancelamento
            motivos_classificados = self._classificar_motivos_cancelamento(cancelamentos)
            dados['motivos_cancelamento'] = motivos_classificados
        
        # Separar por modalidade de ingresso
        if 'MODALIDADE' in df.columns:
            modalidades = df['MODALIDADE'].fillna('')
            
            # Ampla concorrência (códigos começando com A)
            ampla_concorrencia = modalidades[modalidades.str.startswith('A', na=False)]
            dados['ampla_concorrencia'] = len(ampla_concorrencia)
            
            # Ações afirmativas (códigos começando com L)
            acoes_afirmativas = modalidades[modalidades.str.startswith('L', na=False)]
            dados['acoes_afirmativas'] = len(acoes_afirmativas)
        
        # Calcular matrículas ativas
        mat_ativas = 0
        for cat in ['Inscritos/Pendentes/Concluintes', 'Trancados']:
            if cat in dados['categorias']:
                mat_ativas += dados['categorias'][cat]
        
        dados['matriculas_ativas'] = mat_ativas
        
        # Calcular percentuais
        if dados['total_registros'] > 0:
            for categoria, valor in dados['categorias'].items():
                percentual = (valor / dados['total_registros']) * 100
                dados['categorias'][categoria] = {
                    'quantidade': valor,
                    'percentual': round(percentual, 2)
                }
        
        return dados
    
    def _classificar_motivos_cancelamento(self, motivos_series):
        """Classifica motivos de cancelamento em categorias"""
        categorias = {
            'Solicitação Oficial': 0,
            'Abandono': 0,
            'Insuficiência de Aproveitamento': 0,
            'Ingressante - Insuf. Aproveit.': 0,
            'Mudança de Curso': 0,
            'Outros': 0
        }
        
        # Mapeamento de padrões para categorias
        padroes = {
            'Solicitação Oficial': ['solicitação oficial', 'pedido'],
            'Abandono': ['abandono', 'desistência'],
            'Insuficiência de Aproveitamento': ['insuficiência de aproveitamento', 'reprovação'],
            'Ingressante - Insuf. Aproveit.': ['ingressante', 'calouro'],
            'Mudança de Curso': ['mudança de curso', 'transferência']
        }
        
        for motivo in motivos_series:
            motivo_str = str(motivo).lower()
            classificado = False
            
            for categoria, padroes_cat in padroes.items():
                for padrao in padroes_cat:
                    if padrao in motivo_str:
                        categorias[categoria] += 1
                        classificado = True
                        break
                if classificado:
                    break
            
            if not classificado:
                categorias['Outros'] += 1
        
        # Calcular percentuais
        total = sum(categorias.values())
        if total > 0:
            categorias_com_percentuais = {}
            for cat, valor in categorias.items():
                percentual = (valor / total) * 100
                categorias_com_percentuais[cat] = {
                    'quantidade': valor,
                    'percentual': round(percentual, 2)
                }
            return categorias_com_percentuais
        
        return categorias
    
    def consolidar_dados_todos_relatorios(self, resultados_geracao):
        """Consolida dados de todos os relatórios gerados"""
        dados_consolidados = {
            'cursos': {},
            'periodos': {},
            'resumo_geral': {
                'total_cursos': 0,
                'total_periodos': 0,
                'total_matriculas': 0,
                'total_cancelamentos': 0,
                'total_formados': 0,
                'total_ativos': 0
            }
        }
        
        for curso_nome, resultados_curso in resultados_geracao.items():
            dados_curso = {
                'periodos': {},
                'totais': {
                    'matriculas': 0,
                    'cancelamentos': 0,
                    'formados': 0,
                    'ativos': 0
                }
            }
            
            for resultado in resultados_curso:
                if resultado.get('success') and 'caminho_arquivo' in resultado:
                    periodo = resultado.get('periodo')
                    
                    # Ler e processar relatório
                    df = self.ler_relatorio_excel(resultado['caminho_arquivo'])
                    if df is not None:
                        dados_periodo = self.extrair_dados_relatorio(df, curso_nome, periodo)
                        
                        if dados_periodo:
                            dados_curso['periodos'][periodo] = dados_periodo
                            
                            # Acumular totais
                            dados_curso['totais']['matriculas'] += dados_periodo.get('total_registros', 0)
                            dados_curso['totais']['cancelamentos'] += dados_periodo.get('total_cancelamentos', 0)
                            
                            if 'Formados' in dados_periodo.get('categorias', {}):
                                dados_curso['totais']['formados'] += dados_periodo['categorias']['Formados'].get('quantidade', 0)
                            
                            dados_curso['totais']['ativos'] += dados_periodo.get('matriculas_ativas', 0)
            
            dados_consolidados['cursos'][curso_nome] = dados_curso
        
        # Calcular totais gerais
        for curso_nome, dados_curso in dados_consolidados['cursos'].items():
            dados_consolidados['resumo_geral']['total_cursos'] += 1
            dados_consolidados['resumo_geral']['total_matriculas'] += dados_curso['totais']['matriculas']
            dados_consolidados['resumo_geral']['total_cancelamentos'] += dados_curso['totais']['cancelamentos']
            dados_consolidados['resumo_geral']['total_formados'] += dados_curso['totais']['formados']
            dados_consolidados['resumo_geral']['total_ativos'] += dados_curso['totais']['ativos']
        
        # Contar períodos únicos
        periodos_unicos = set()
        for curso_nome, dados_curso in dados_consolidados['cursos'].items():
            for periodo in dados_curso['periodos'].keys():
                periodos_unicos.add(periodo)
        
        dados_consolidados['resumo_geral']['total_periodos'] = len(periodos_unicos)
        
        return dados_consolidados
    
    def gerar_planilha_consolidada(self, dados_consolidados, caminho_saida):
        """Gera planilha Excel com dados consolidados"""
        try:
            # Criar writer para múltiplas abas
            with pd.ExcelWriter(caminho_saida, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # 1. ABA: RESUMO GERAL
                dados_resumo = []
                for curso_nome, dados_curso in dados_consolidados['cursos'].items():
                    dados_resumo.append({
                        'Curso': curso_nome,
                        'Total Matrículas': dados_curso['totais']['matriculas'],
                        'Total Cancelamentos': dados_curso['totais']['cancelamentos'],
                        'Total Formados': dados_curso['totais']['formados'],
                        'Total Ativos': dados_curso['totais']['ativos'],
                        '% Cancelamentos': round((dados_curso['totais']['cancelamentos'] / dados_curso['totais']['matriculas'] * 100), 2) if dados_curso['totais']['matriculas'] > 0 else 0,
                        '% Formados': round((dados_curso['totais']['formados'] / dados_curso['totais']['matriculas'] * 100), 2) if dados_curso['totais']['matriculas'] > 0 else 0,
                        '% Ativos': round((dados_curso['totais']['ativos'] / dados_curso['totais']['matriculas'] * 100), 2) if dados_curso['totais']['matriculas'] > 0 else 0
                    })
                
                df_resumo = pd.DataFrame(dados_resumo)
                df_resumo.to_excel(writer, sheet_name='RESUMO GERAL', index=False)
                
                # Formatar a aba RESUMO GERAL
                worksheet = writer.sheets['RESUMO GERAL']
                format_percent = workbook.add_format({'num_format': '0.00%'})
                format_header = workbook.add_format({'bold': True, 'bg_color': '#366092', 'font_color': 'white'})
                
                for col_num, value in enumerate(df_resumo.columns.values):
                    worksheet.write(0, col_num, value, format_header)
                
                # Aplicar formatação percentual
                percent_cols = ['% Cancelamentos', '% Formados', '% Ativos']
                for col_name in percent_cols:
                    if col_name in df_resumo.columns:
                        col_idx = df_resumo.columns.get_loc(col_name)
                        for row in range(1, len(df_resumo) + 1):
                            worksheet.write(row, col_idx, df_resumo.iloc[row-1][col_name]/100, format_percent)
                
                worksheet.autofit()
                
                # 2. ABA: DETALHES POR CURSO E PERÍODO
                dados_detalhes = []
                for curso_nome, dados_curso in dados_consolidados['cursos'].items():
                    for periodo, dados_periodo in dados_curso['periodos'].items():
                        # Formatando período para exibição
                        periodo_display = f"{periodo[:4]}/{periodo[4:]}"
                        
                        linha = {
                            'Curso': curso_nome,
                            'Período': periodo_display,
                            'Total Registros': dados_periodo.get('total_registros', 0),
                            'Matrículas Ativas': dados_periodo.get('matriculas_ativas', 0),
                            'Ampla Concorrência': dados_periodo.get('ampla_concorrencia', 0),
                            'Ações Afirmativas': dados_periodo.get('acoes_afirmativas', 0)
                        }
                        
                        # Adicionar categorias
                        categorias = dados_periodo.get('categorias', {})
                        for categoria, dados_cat in categorias.items():
                            linha[f'{categoria} (qtd)'] = dados_cat.get('quantidade', 0)
                            linha[f'{categoria} (%)'] = dados_cat.get('percentual', 0)
                        
                        # Adicionar cancelamentos
                        motivos = dados_periodo.get('motivos_cancelamento', {})
                        for motivo, dados_motivo in motivos.items():
                            linha[f'Cancel: {motivo}'] = dados_motivo.get('quantidade', 0)
                        
                        dados_detalhes.append(linha)
                
                if dados_detalhes:
                    df_detalhes = pd.DataFrame(dados_detalhes)
                    df_detalhes.to_excel(writer, sheet_name='DETALHES', index=False)
                    
                    # Formatar a aba DETALHES
                    worksheet_detalhes = writer.sheets['DETALHES']
                    for col_num, value in enumerate(df_detalhes.columns.values):
                        worksheet_detalhes.write(0, col_num, value, format_header)
                    
                    # Aplicar formatação percentual para colunas com %
                    for col_num, col_name in enumerate(df_detalhes.columns):
                        if '(%)' in col_name:
                            for row in range(1, len(df_detalhes) + 1):
                                worksheet_detalhes.write(row, col_num, df_detalhes.iloc[row-1][col_name]/100, format_percent)
                    
                    worksheet_detalhes.autofit()
                
                # 3. ABA: CANCELAMENTOS
                dados_cancel = []
                for curso_nome, dados_curso in dados_consolidados['cursos'].items():
                    for periodo, dados_periodo in dados_curso['periodos'].items():
                        periodo_display = f"{periodo[:4]}/{periodo[4:]}"
                        motivos = dados_periodo.get('motivos_cancelamento', {})
                        
                        for motivo, dados_motivo in motivos.items():
                            dados_cancel.append({
                                'Curso': curso_nome,
                                'Período': periodo_display,
                                'Motivo Cancelamento': motivo,
                                'Quantidade': dados_motivo.get('quantidade', 0),
                                'Percentual': dados_motivo.get('percentual', 0)
                            })
                
                if dados_cancel:
                    df_cancel = pd.DataFrame(dados_cancel)
                    df_cancel.to_excel(writer, sheet_name='CANCELAMENTOS', index=False)
                    
                    # Formatar a aba CANCELAMENTOS
                    worksheet_cancel = writer.sheets['CANCELAMENTOS']
                    for col_num, value in enumerate(df_cancel.columns.values):
                        worksheet_cancel.write(0, col_num, value, format_header)
                    
                    col_percent = df_cancel.columns.get_loc('Percentual')
                    for row in range(1, len(df_cancel) + 1):
                        worksheet_cancel.write(row, col_percent, df_cancel.iloc[row-1]['Percentual']/100, format_percent)
                    
                    worksheet_cancel.autofit()
                
                # 4. ABA: MODALIDADES
                dados_modalidades = []
                for curso_nome, dados_curso in dados_consolidados['cursos'].items():
                    for periodo, dados_periodo in dados_curso['periodos'].items():
                        periodo_display = f"{periodo[:4]}/{periodo[4:]}"
                        total = dados_periodo.get('total_registros', 0)
                        ampla = dados_periodo.get('ampla_concorrencia', 0)
                        acoes = dados_periodo.get('acoes_afirmativas', 0)
                        
                        if total > 0:
                            dados_modalidades.append({
                                'Curso': curso_nome,
                                'Período': periodo_display,
                                'Total': total,
                                'Ampla Concorrência': ampla,
                                '% Ampla': round((ampla / total * 100), 2),
                                'Ações Afirmativas': acoes,
                                '% Ações': round((acoes / total * 100), 2)
                            })
                
                if dados_modalidades:
                    df_modal = pd.DataFrame(dados_modalidades)
                    df_modal.to_excel(writer, sheet_name='MODALIDADES', index=False)
                    
                    # Formatar a aba MODALIDADES
                    worksheet_modal = writer.sheets['MODALIDADES']
                    for col_num, value in enumerate(df_modal.columns.values):
                        worksheet_modal.write(0, col_num, value, format_header)
                    
                    # Formatar percentuais
                    for col_name in ['% Ampla', '% Ações']:
                        if col_name in df_modal.columns:
                            col_idx = df_modal.columns.get_loc(col_name)
                            for row in range(1, len(df_modal) + 1):
                                worksheet_modal.write(row, col_idx, df_modal.iloc[row-1][col_name]/100, format_percent)
                    
                    worksheet_modal.autofit()
                
                logger.info(f"Planilha consolidada gerada: {caminho_saida}")
                return True
                
        except Exception as e:
            logger.error(f"Erro ao gerar planilha: {str(e)}")
            return False
