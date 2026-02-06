# gerador_relatorios_otimizado.py
"""
gerador_relatorios_otimizado.py - Módulo otimizado para geração de relatórios
"""
import logging
import time
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import threading

from config import *
from formulario_handler import FormularioHandler
from relatorio_automator import RelatorioUFFAutomator
from utils import *

logger = logging.getLogger(__name__)

class GeradorRelatoriosOtimizado:
    """Classe otimizada para gerar relatórios em lote"""
    
    def __init__(self, session):
        self.session = session
        self.form_handler = FormularioHandler(session)
        self.rel_automator = RelatorioUFFAutomator(session)
        self.progresso_atual = {
            'total': 0,
            'concluido': 0,
            'atual': '',
            'status': ''
        }
    
    def descobrir_valores_cursos(self):
        """Descobre os valores corretos dos cursos analisando o formulário"""
        try:
            # Carregar a página do formulário
            response = self.session.get(LISTAGEM_ALUNOS_URL)
            
            if response.status_code != 200:
                logger.error(f"Falha ao carregar formulário: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Encontrar o select de cursos
            select_curso = soup.find('select', {'id': 'idcurso'})
            
            if not select_curso:
                logger.error("Select de cursos não encontrado")
                return None
            
            logger.info("=== VALORES DISPONÍVEIS PARA CURSOS ===")
            cursos_disponiveis = []
            
            for option in select_curso.find_all('option'):
                if option.get('value') and option.get('value') != '':
                    cursos_disponiveis.append({
                        'value': option.get('value'),
                        'text': option.text.strip()
                    })
                    logger.info(f"Value: '{option.get('value')}', Text: '{option.text.strip()}'")
            
            logger.info("=== VALORES DISPONÍVEIS PARA DESDOBRAMENTOS ===")
            # Também verificar desdobramentos
            select_desdobramento = soup.find('select', {'id': 'iddesdobramento'})
            
            if select_desdobramento:
                for option in select_desdobramento.find_all('option'):
                    if option.get('value') and option.get('value') != '':
                        logger.info(f"Value: '{option.get('value')}', Text: '{option.text.strip()}'")
            
            return cursos_disponiveis
            
        except Exception as e:
            logger.error(f"Erro ao descobrir valores: {str(e)}")
            return None
    
    def criar_filtros_para_curso(self, curso_config, periodo, forma_ingresso):
        """Cria dicionário de filtros para um curso específico"""
        logger.info(f"Criando filtros para: {curso_config['nome']} - {curso_config['codigo_curso']}:{curso_config['codigo_desdobramento']}")
        
        filtros = {
            'idlocalidade': '1',  # Niterói
            'idcurso': curso_config['codigo_curso'],
            'iddesdobramento': curso_config['codigo_desdobramento'],
            'idturno': '',  # Todos os turnos
            'idstatusaluno': '',  # Todos os status
            'idsituacaoaluno': '',  # Todas as situações
            'idformaingresso': forma_ingresso,  # SISU 1ª ou 2ª Edição
            'idacaoafirmativa': '',  # TODAS as modalidades (Ampla + Ações Afirmativas)
            'anosem_ingresso': periodo,
            'anosem_desvinculacao': '',  # Não filtrar por desvinculação
            'format': 'xls'  # Formato XLSX - conforme botão no HTML
        }
        
        logger.debug(f"Filtros criados: {filtros}")
        return filtros
    
    def gerar_relatorio_individual_com_progresso(self, curso_config, periodo, forma_ingresso, callback_progresso=None):
        """Gera um relatório individual com feedback de progresso"""
        logger.info(f"Gerando relatório: {curso_config['nome']} - Período {periodo}")
        
        try:
            # Primeiro, tentar descobrir os valores corretos se houver problema
            if callback_progresso:
                callback_progresso(f"Preparando {curso_config['nome']} - {periodo[:4]}/{periodo[4:]}", 0)
            
            # Criar filtros
            filtros = self.criar_filtros_para_curso(curso_config, periodo, forma_ingresso)
            
            if callback_progresso:
                callback_progresso(f"Enviando solicitação...", 10)
            
            # Gerar relatório usando FormularioHandler
            resultado = self.form_handler.gerar_relatorio(filtros)
            
            if not resultado.get('success'):
                logger.error(f"Erro ao gerar relatório: {resultado.get('error')}")
                return {
                    'success': False,
                    'error': resultado.get('error', 'Erro ao enviar solicitação'),
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            if not resultado.get('relatorio_id'):
                logger.error("ID do relatório não retornado")
                return {
                    'success': False,
                    'error': 'ID do relatório não retornado',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            relatorio_id = resultado['relatorio_id']
            
            if callback_progresso:
                callback_progresso(f"Aguardando processamento... (ID: {relatorio_id})", 30)
            
            # Monitorar processamento com progresso detalhado
            status_info = self._aguardar_conclusao_com_progresso(
                relatorio_id=relatorio_id,
                callback_progresso=callback_progresso,
                progresso_inicial=30,
                progresso_final=80
            )
            
            if not status_info or status_info.get('status') != 'PRONTO':
                logger.error(f"Relatório não ficou pronto. Status: {status_info}")
                return {
                    'success': False,
                    'error': 'Relatório não ficou pronto',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            if callback_progresso:
                callback_progresso(f"Baixando arquivo...", 80)
            
            # Baixar relatório
            caminho_arquivo = self.rel_automator.baixar_relatorio(status_info)
            
            if not caminho_arquivo:
                logger.error("Erro ao baixar arquivo")
                return {
                    'success': False,
                    'error': 'Erro ao baixar arquivo',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            logger.info(f"Relatório gerado com sucesso: {caminho_arquivo}")
            
            if callback_progresso:
                callback_progresso(f"Concluído!", 100)
            
            return {
                'success': True,
                'relatorio_id': relatorio_id,
                'caminho_arquivo': caminho_arquivo,
                'status_info': status_info,
                'curso': curso_config['nome'],
                'periodo': periodo,
                'forma_ingresso': forma_ingresso
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'curso': curso_config['nome'],
                'periodo': periodo
            }
    
    def _aguardar_conclusao_com_progresso(self, relatorio_id, callback_progresso=None, 
                                         progresso_inicial=0, progresso_final=100,
                                         intervalo=30, timeout=1800):
        """Aguarda conclusão com feedback de progresso incremental"""
        
        tempo_inicio = time.time()
        ultimo_status = None
        progresso_atual = progresso_inicial
        
        while time.time() - tempo_inicio < timeout:
            status_info = self.rel_automator.verificar_status_relatorio(relatorio_id)
            
            if not status_info:
                if callback_progresso:
                    callback_progresso(f"Erro ao verificar status", progresso_atual)
                time.sleep(intervalo)
                continue
            
            # Calcular progresso baseado no tempo
            tempo_decorrido = time.time() - tempo_inicio
            progresso_tempo = min(tempo_decorrido / timeout, 0.95)
            
            # Combinar progresso do tempo com progresso baseado em etapas
            if status_info.get('etapas'):
                etapas = status_info['etapas']
                num_etapas = len(etapas)
                etapas_concluidas = sum(1 for etapa in etapas if 'Concluída' in etapa)
                
                if num_etapas > 0:
                    progresso_etapas = etapas_concluidas / num_etapas
                    progresso_combinado = (progresso_tempo * 0.5) + (progresso_etapas * 0.5)
                else:
                    progresso_combinado = progresso_tempo
            else:
                progresso_combinado = progresso_tempo
            
            # Calcular progresso final
            range_progresso = progresso_final - progresso_inicial
            progresso_atual = progresso_inicial + (progresso_combinado * range_progresso)
            
            # Mensagem de status
            status = status_info.get('status', 'Desconhecido')
            mensagem = f"Status: {status}"
            
            if status_info.get('etapas'):
                ultima_etapa = status_info['etapas'][-1] if status_info['etapas'] else ''
                mensagem += f" | {ultima_etapa[:50]}"
            
            # Chamar callback de progresso
            if callback_progresso:
                callback_progresso(mensagem, progresso_atual)
            
            # Verificar se está pronto
            if status_info['status'] == 'PRONTO':
                return status_info
            
            # Verificar se houve mudança significativa
            if status_info != ultimo_status:
                logger.info(f"Status atualizado: {status_info['status']}")
                ultimo_status = status_info
            
            time.sleep(intervalo)
        
        # Timeout atingido
        logger.warning(f"Timeout ao aguardar relatório {relatorio_id}")
        return None
    
    def _determinar_forma_ingresso(self, periodo):
        """Determina a forma de ingresso baseada no semestre do período"""
        # Baseado no HTML: SISU 1ª Edição = "125", SISU 2ª Edição = "124"
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
        
        logger.info(f"Gerados {len(periodos)} períodos: {periodos}")
        return periodos
    
    def obter_cursos_predefinidos(self, cursos_selecionados=None):
        """Retorna configuração dos cursos predefinidos"""
        # CORREÇÃO: Tentar descobrir os valores corretos primeiro
        logger.info("Tentando descobrir valores corretos dos cursos...")
        cursos_disponiveis = self.descobrir_valores_cursos()
        
        # Mapeamento dos cursos baseado no que descobrimos
        mapeamento_cursos = {
            'Química (Licenciatura)': {
                'nome': 'Química (Licenciatura)',
                'codigo_curso': '12700',  # Valor para o curso Química
                'codigo_desdobramento': '12700',  # Valor para licenciatura
                'tipo': 'Licenciatura'
            },
            'Química (Bacharelado)': {
                'nome': 'Química (Bacharelado)',
                'codigo_curso': '12700',  # Mesmo curso
                'codigo_desdobramento': '312700',  # Valor específico para bacharelado
                'tipo': 'Bacharelado'
            },
            'Química Industrial': {
                'nome': 'Química Industrial',
                'codigo_curso': '12709',  # Valor para Química Industrial
                'codigo_desdobramento': '12709',  # Mesmo valor
                'tipo': 'Bacharelado'
            }
        }
        
        # Se descobrimos os valores, usar os valores reais
        if cursos_disponiveis:
            logger.info("Valores descobertos, atualizando mapeamento...")
            # Procurar os valores corretos nos cursos descobertos
            for curso_info in cursos_disponiveis:
                texto = curso_info['text']
                valor = curso_info['value']
                
                if 'Química (Licenciatura)' in texto:
                    mapeamento_cursos['Química (Licenciatura)']['codigo_curso'] = valor
                    mapeamento_cursos['Química (Licenciatura)']['codigo_desdobramento'] = valor
                elif 'Química (Bacharelado)' in texto:
                    mapeamento_cursos['Química (Bacharelado)']['codigo_curso'] = valor
                    # O desdobramento pode ser diferente
                elif 'Química Industrial' in texto:
                    mapeamento_cursos['Química Industrial']['codigo_curso'] = valor
                    mapeamento_cursos['Química Industrial']['codigo_desdobramento'] = valor
        
        todos_cursos = list(mapeamento_cursos.values())
        
        if cursos_selecionados:
            cursos_filtrados = [c for c in todos_cursos if c['nome'] in cursos_selecionados]
            logger.info(f"Cursos selecionados: {[c['nome'] for c in cursos_filtrados]}")
            
            # Log dos códigos que serão usados
            for curso in cursos_filtrados:
                logger.info(f"  {curso['nome']}: curso={curso['codigo_curso']}, desdobramento={curso['codigo_desdobramento']}")
            
            return cursos_filtrados
        
        logger.info(f"Todos os cursos selecionados: {[c['nome'] for c in todos_cursos]}")
        return todos_cursos


class ProcessadorDadosOtimizado:
    """Classe otimizada para processar dados dos relatórios"""
    
    def __init__(self, pasta_relatorios=PASTA_RELATORIOS):
        self.pasta_relatorios = pasta_relatorios
    
    def ler_e_processar_relatorio(self, caminho_arquivo, curso, periodo):
        """Lê e processa um relatório em um único passo"""
        try:
            # Ler Excel
            df = pd.read_excel(caminho_arquivo)
            
            if df.empty:
                logger.warning(f"Arquivo vazio: {caminho_arquivo}")
                return None
            
            # Normalizar nomes de colunas (remover espaços, maiúsculas)
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            dados = {
                'curso': curso,
                'periodo': periodo,
                'total_registros': len(df),
                'detalhes': {}
            }
            
            # 1. Contar por SITUAÇÃO
            if 'SITUAÇÃO' in df.columns or 'SITUACAO' in df.columns:
                col_situacao = 'SITUAÇÃO' if 'SITUAÇÃO' in df.columns else 'SITUACAO'
                
                situacoes = df[col_situacao].fillna('Desconhecido').astype(str)
                
                # Mapear para categorias normalizadas
                categorias = {
                    'Inscritos/Pendentes/Concluintes': 0,
                    'Trancados': 0,
                    'Formados': 0,
                    'Outros': 0
                }
                
                for situacao in situacoes:
                    situacao_lower = situacao.lower()
                    
                    if any(term in situacao_lower for term in ['inscrito', 'concluinte', 'pendente']):
                        categorias['Inscritos/Pendentes/Concluintes'] += 1
                    elif 'trancado' in situacao_lower:
                        categorias['Trancados'] += 1
                    elif any(term in situacao_lower for term in ['formado', 'formando', 'permanência']):
                        categorias['Formados'] += 1
                    else:
                        categorias['Outros'] += 1
                
                dados['categorias_situacao'] = categorias
            
            # 2. Contar cancelamentos
            col_cancelamento = None
            for col in ['MOTIVO DO CANCELAMENTO', 'MOTIVO CANCELAMENTO', 'CANCELAMENTO']:
                if col in df.columns:
                    col_cancelamento = col
                    break
            
            if col_cancelamento:
                motivos = df[col_cancelamento].fillna('')
                cancelamentos = motivos[motivos != '']
                dados['total_cancelamentos'] = len(cancelamentos)
                dados['motivos_cancelamento'] = self._classificar_motivos_cancelamento(cancelamentos)
            else:
                dados['total_cancelamentos'] = 0
                dados['motivos_cancelamento'] = {}
            
            # 3. Separar por modalidade
            col_modalidade = None
            for col in ['MODALIDADE', 'MODALIDADE DE INGRESSO', 'ACAO AFIRMATIVA']:
                if col in df.columns:
                    col_modalidade = col
                    break
            
            if col_modalidade:
                modalidades = df[col_modalidade].fillna('')
                
                # Ampla concorrência (códigos começando com A)
                ampla = modalidades[modalidades.str.startswith('A', na=False)]
                dados['ampla_concorrencia'] = len(ampla)
                
                # Ações afirmativas (códigos começando com L)
                acoes = modalidades[modalidades.str.startswith('L', na=False)]
                dados['acoes_afirmativas'] = len(acoes)
                
                # Outras modalidades
                outras = modalidades[~(modalidades.str.startswith('A', na=False) | 
                                       modalidades.str.startswith('L', na=False)) & (modalidades != '')]
                dados['outras_modalidades'] = len(outras)
            else:
                dados['ampla_concorrencia'] = 0
                dados['acoes_afirmativas'] = 0
                dados['outras_modalidades'] = 0
            
            # 4. Calcular totais e percentuais
            dados['matriculas_ativas'] = (
                dados['categorias_situacao'].get('Inscritos/Pendentes/Concluintes', 0) +
                dados['categorias_situacao'].get('Trancados', 0)
            )
            
            # Calcular percentuais
            if dados['total_registros'] > 0:
                for categoria in dados['categorias_situacao']:
                    valor = dados['categorias_situacao'][categoria]
                    percentual = (valor / dados['total_registros']) * 100
                    dados['categorias_situacao'][categoria] = {
                        'quantidade': valor,
                        'percentual': round(percentual, 2)
                    }
                
                # Percentual cancelamentos
                dados['percentual_cancelamentos'] = round(
                    (dados['total_cancelamentos'] / dados['total_registros']) * 100, 2
                )
                
                # Percentual modalidades
                dados['percentual_ampla'] = round(
                    (dados['ampla_concorrencia'] / dados['total_registros']) * 100, 2
                ) if dados['total_registros'] > 0 else 0
                
                dados['percentual_acoes'] = round(
                    (dados['acoes_afirmativas'] / dados['total_registros']) * 100, 2
                ) if dados['total_registros'] > 0 else 0
            
            logger.info(f"Processado {caminho_arquivo}: {dados['total_registros']} registros")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao processar relatório {caminho_arquivo}: {str(e)}", exc_info=True)
            return None
    
    def _classificar_motivos_cancelamento(self, motivos_series):
        """Classifica motivos de cancelamento"""
        categorias = {
            'Solicitação Oficial': 0,
            'Abandono': 0,
            'Insuficiência de Aproveitamento': 0,
            'Ingressante - Insuf. Aproveit.': 0,
            'Mudança de Curso': 0,
            'Outros': 0
        }
        
        for motivo in motivos_series:
            motivo_str = str(motivo).lower()
            
            if any(term in motivo_str for term in ['solicitação', 'solicitacao', 'pedido', 'oficial']):
                categorias['Solicitação Oficial'] += 1
            elif any(term in motivo_str for term in ['abandono', 'desistência', 'desistencia']):
                categorias['Abandono'] += 1
            elif any(term in motivo_str for term in ['insuficiência', 'insuficiencia', 'reprovação', 'reprovacao']):
                if 'ingressante' in motivo_str or 'calouro' in motivo_str:
                    categorias['Ingressante - Insuf. Aproveit.'] += 1
                else:
                    categorias['Insuficiência de Aproveitamento'] += 1
            elif any(term in motivo_str for term in ['mudança', 'mudanca', 'transferência', 'transferencia']):
                categorias['Mudança de Curso'] += 1
            else:
                categorias['Outros'] += 1
        
        # Converter para dicionário com percentuais
        total = sum(categorias.values())
        if total > 0:
            resultado = {}
            for cat, valor in categorias.items():
                percentual = (valor / total) * 100
                resultado[cat] = {
                    'quantidade': valor,
                    'percentual': round(percentual, 2)
                }
            return resultado
        
        return categorias
    
    def processar_todos_relatorios(self, resultados_geracao):
        """Processa todos os relatórios e consolida dados"""
        logger.info(f"Processando {len(resultados_geracao)} cursos")
        dados_consolidados = {
            'por_curso': {},
            'por_periodo': {},
            'resumo_geral': {
                'total_cursos': 0,
                'total_periodos': 0,
                'total_matriculas': 0,
                'total_cancelamentos': 0,
                'total_formados': 0,
                'total_ativos': 0
            }
        }
        
        periodos_unicos = set()
        relatorios_processados = 0
        
        for curso_nome, resultados_curso in resultados_geracao.items():
            if curso_nome not in dados_consolidados['por_curso']:
                dados_consolidados['por_curso'][curso_nome] = {
                    'periodos': {},
                    'totais': {
                        'matriculas': 0,
                        'cancelamentos': 0,
                        'formados': 0,
                        'ativos': 0,
                        'ampla_concorrencia': 0,
                        'acoes_afirmativas': 0
                    }
                }
            
            for resultado in resultados_curso:
                if resultado.get('success') and 'caminho_arquivo' in resultado:
                    periodo = resultado.get('periodo')
                    periodos_unicos.add(periodo)
                    
                    # Processar relatório
                    dados = self.ler_e_processar_relatorio(
                        resultado['caminho_arquivo'],
                        curso_nome,
                        periodo
                    )
                    
                    if dados:
                        dados_consolidados['por_curso'][curso_nome]['periodos'][periodo] = dados
                        relatorios_processados += 1
                        
                        # Acumular totais do curso
                        dados_consolidados['por_curso'][curso_nome]['totais']['matriculas'] += dados['total_registros']
                        dados_consolidados['por_curso'][curso_nome]['totais']['cancelamentos'] += dados['total_cancelamentos']
                        dados_consolidados['por_curso'][curso_nome]['totais']['formados'] += dados['categorias_situacao']['Formados']['quantidade']
                        dados_consolidados['por_curso'][curso_nome]['totais']['ativos'] += dados['matriculas_ativas']
                        dados_consolidados['por_curso'][curso_nome]['totais']['ampla_concorrencia'] += dados['ampla_concorrencia']
                        dados_consolidados['por_curso'][curso_nome]['totais']['acoes_afirmativas'] += dados['acoes_afirmativas']
        
        # Calcular totais gerais
        dados_consolidados['resumo_geral']['total_cursos'] = len(dados_consolidados['por_curso'])
        dados_consolidados['resumo_geral']['total_periodos'] = len(periodos_unicos)
        
        for curso_nome, dados_curso in dados_consolidados['por_curso'].items():
            dados_consolidados['resumo_geral']['total_matriculas'] += dados_curso['totais']['matriculas']
            dados_consolidados['resumo_geral']['total_cancelamentos'] += dados_curso['totais']['cancelamentos']
            dados_consolidados['resumo_geral']['total_formados'] += dados_curso['totais']['formados']
            dados_consolidados['resumo_geral']['total_ativos'] += dados_curso['totais']['ativos']
        
        logger.info(f"Processamento concluído: {relatorios_processados} relatórios processados")
        return dados_consolidados
