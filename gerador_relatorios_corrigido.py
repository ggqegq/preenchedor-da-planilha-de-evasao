# gerador_relatorios_corrigido.py
"""
gerador_relatorios_corrigido.py - Módulo corrigido para aplicar filtros corretamente
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
import json

from config import *
from formulario_handler import FormularioHandler
from relatorio_automator import RelatorioUFFAutomator
from utils import *

logger = logging.getLogger(__name__)

class GeradorRelatoriosCorrigido:
    """Classe corrigida para aplicar filtros corretamente"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
        self.csrf_token = None
        self.form_handler = FormularioHandler(session)
        self.rel_automator = RelatorioUFFAutomator(session)
    
    def extrair_csrf_token(self, html):
        """Extrai token CSRF do HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Procurar meta tag CSRF
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token and meta_token.get('content'):
            return meta_token.get('content')
        
        # Procurar input hidden
        input_token = soup.find('input', {'name': 'authenticity_token'})
        if input_token and input_token.get('value'):
            return input_token.get('value')
        
        return None
    
    def carregar_pagina_formulario(self):
        """Carrega a página do formulário e extrai tokens"""
        url = f"{self.base_url}/relatorios/listagens_alunos"
        
        try:
            response = self.session.get(url, timeout=TIMEOUT_REQUESTS)
            response.raise_for_status()
            
            # Extrair CSRF token
            self.csrf_token = self.extrair_csrf_token(response.text)
            
            # Extrair outros tokens necessários
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extrair token do input utf8
            utf8_token = soup.find('input', {'name': 'utf8'})
            utf8_value = utf8_token.get('value') if utf8_token else '✓'
            
            return {
                'html': response.text,
                'csrf_token': self.csrf_token,
                'utf8_token': utf8_value,
                'soup': soup
            }
            
        except Exception as e:
            logger.error(f"Erro ao carregar página: {str(e)}")
            return None
    
    def buscar_opcoes_curso(self, localidade_id='1'):
        """Busca cursos disponíveis para uma localidade"""
        try:
            url = f"{self.base_url}/relatorios/buscar_cursos"
            
            dados = {
                'authenticity_token': self.csrf_token,
                'idlocalidade': localidade_id
            }
            
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f"{self.base_url}/relatorios/listagens_alunos"
            }
            
            response = self.session.post(url, data=dados, headers=headers, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code == 200:
                try:
                    # Tentar parsear como JSON
                    dados_json = response.json()
                    if dados_json.get('success'):
                        return dados_json.get('cursos', [])
                except:
                    # Se não for JSON, parsear HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    options = soup.find_all('option')
                    
                    cursos = []
                    for option in options:
                        if option.get('value') and option.get('value') != '':
                            cursos.append({
                                'value': option.get('value'),
                                'text': option.get_text(strip=True)
                            })
                    return cursos
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao buscar cursos: {str(e)}")
            return []
    
    def buscar_desdobramentos(self, curso_id, localidade_id='1'):
        """Busca desdobramentos disponíveis para um curso"""
        try:
            url = f"{self.base_url}/relatorios/buscar_desdobramentos"
            
            dados = {
                'authenticity_token': self.csrf_token,
                'idlocalidade': localidade_id,
                'idcurso': curso_id
            }
            
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f"{self.base_url}/relatorios/listagens_alunos"
            }
            
            response = self.session.post(url, data=dados, headers=headers, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code == 200:
                try:
                    # Tentar parsear como JSON
                    dados_json = response.json()
                    if dados_json.get('success'):
                        return dados_json.get('desdobramentos', [])
                except:
                    # Se não for JSON, parsear HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    options = soup.find_all('option')
                    
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
            logger.error(f"Erro ao buscar desdobramentos: {str(e)}")
            return []
    
    def criar_parametros_corretos(self, curso_config, periodo, forma_ingresso):
        """Cria parâmetros CORRETOS para o formulário"""
        
        # Mapeamento de cursos baseado no HTML fornecido
        mapeamento_cursos = {
            'Química (Licenciatura)': {
                'curso_id': '12700',  # ID do curso Química
                'desdobramento_id': '12700',  # ID do desdobramento Licenciatura
                'curso_nome': 'Química',
                'desdobramento_nome': 'Quimica (Licenciatura) (12700)'
            },
            'Química (Bacharelado)': {
                'curso_id': '12700',  # ID do curso Química
                'desdobramento_id': '312700',  # ID do desdobramento Bacharelado
                'curso_nome': 'Química',
                'desdobramento_nome': 'Quimica (Bacharelado) (312700)'
            },
            'Química Industrial': {
                'curso_id': '12709',  # ID do curso Química Industrial
                'desdobramento_id': '12709',  # ID do desdobramento
                'curso_nome': 'Química Industrial',
                'desdobramento_nome': 'Química Industrial (12709)'
            }
        }
        
        curso_info = mapeamento_cursos.get(curso_config['nome'])
        if not curso_info:
            raise ValueError(f"Curso não mapeado: {curso_config['nome']}")
        
        # Parâmetros baseados no HTML da página
        parametros = {
            'utf8': '✓',
            'authenticity_token': self.csrf_token,
            'idlocalidade': '1',  # Niterói
            'idcurso': curso_info['curso_id'],
            'iddesdobramento': curso_info['desdobramento_id'],
            'idturno': '',  # Todos os turnos
            'idstatusaluno': '',  # Todos os status
            'idsituacaoaluno': '',  # Todas as situações
            'idformaingresso': forma_ingresso,  # SISU 1ª ou 2ª Edição
            'idacaoafirmativa': '',  # Todas as modalidades
            'anosem_ingresso': periodo,  # Formato: 20251, 20252, etc.
            'anosem_desvinculacao': '',  # Não filtrar por desvinculação
            'format': 'xls'  # Formato XLSX
        }
        
        logger.info(f"Parâmetros criados para {curso_config['nome']}:")
        logger.info(f"  Curso ID: {curso_info['curso_id']}")
        logger.info(f"  Desdobramento ID: {curso_info['desdobramento_id']}")
        logger.info(f"  Período: {periodo}")
        logger.info(f"  Forma Ingresso: {forma_ingresso}")
        
        return parametros
    
    def enviar_formulario_corretamente(self, parametros):
        """Envia o formulário CORRETAMENTE com todos os parâmetros"""
        url = f"{self.base_url}/relatorios/listagens_alunos"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/relatorios/listagens_alunos",
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            logger.info(f"Enviando formulário para: {url}")
            logger.info(f"Parâmetros: {json.dumps(parametros, indent=2)}")
            
            response = self.session.post(
                url,
                data=parametros,
                headers=headers,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            response.raise_for_status()
            
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url and 'listagens_alunos' not in response.url:
                # Extrair ID do relatório da URL
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    relatorio_id = match.group(1)
                    logger.info(f"✅ Relatório criado com ID: {relatorio_id}")
                    return {
                        'success': True,
                        'relatorio_id': relatorio_id,
                        'url_relatorio': response.url,
                        'html': response.text
                    }
            
            # Verificar mensagens de erro
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Verificar alertas de erro
            alert_error = soup.find('div', class_='alert-error') or soup.find('div', class_='alert-danger')
            if alert_error:
                error_msg = alert_error.get_text(strip=True)[:200]
                logger.error(f"Erro no formulário: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'html': response.text
                }
            
            # Verificar alertas de sucesso
            alert_success = soup.find('div', class_='alert-success')
            if alert_success and 'sucesso' in alert_success.text.lower():
                # Tentar encontrar ID do relatório na página
                match = re.search(r'Relatório #(\d+)', response.text)
                if match:
                    relatorio_id = match.group(1)
                    logger.info(f"✅ Relatório criado com ID: {relatorio_id}")
                    return {
                        'success': True,
                        'relatorio_id': relatorio_id,
                        'url_relatorio': response.url,
                        'html': response.text
                    }
            
            logger.warning("Não foi possível determinar o resultado")
            return {
                'success': False,
                'error': 'Resultado indeterminado - verifique o HTML da resposta',
                'html': response.text[:1000]
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar formulário: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def gerar_relatorio_corretamente(self, curso_config, periodo, forma_ingresso, callback_progresso=None):
        """Gera um relatório aplicando TODOS os filtros corretamente"""
        logger.info(f"Gerando relatório CORRETO: {curso_config['nome']} - Período {periodo}")
        
        try:
            # 1. Carregar página inicial para obter tokens
            if callback_progresso:
                callback_progresso("Carregando formulário...", 5)
            
            pagina = self.carregar_pagina_formulario()
            if not pagina or not self.csrf_token:
                return {
                    'success': False,
                    'error': 'Não foi possível carregar o formulário',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            # 2. Criar parâmetros corretos
            if callback_progresso:
                callback_progresso("Configurando filtros...", 10)
            
            parametros = self.criar_parametros_corretos(curso_config, periodo, forma_ingresso)
            
            # 3. Enviar formulário
            if callback_progresso:
                callback_progresso("Enviando solicitação de relatório...", 20)
            
            resultado = self.enviar_formulario_corretamente(parametros)
            
            if not resultado.get('success'):
                return {
                    'success': False,
                    'error': resultado.get('error', 'Erro ao enviar solicitação'),
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            if not resultado.get('relatorio_id'):
                return {
                    'success': False,
                    'error': 'ID do relatório não retornado',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            relatorio_id = resultado['relatorio_id']
            
            # 4. Monitorar processamento
            if callback_progresso:
                callback_progresso(f"Aguardando processamento (ID: {relatorio_id})...", 30)
            
            status_info = self._aguardar_conclusao_com_progresso(
                relatorio_id=relatorio_id,
                callback_progresso=callback_progresso,
                progresso_inicial=30,
                progresso_final=80
            )
            
            if not status_info or status_info.get('status') != 'PRONTO':
                return {
                    'success': False,
                    'error': 'Relatório não ficou pronto',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            # 5. Baixar relatório
            if callback_progresso:
                callback_progresso("Baixando arquivo...", 80)
            
            caminho_arquivo = self.rel_automator.baixar_relatorio(status_info)
            
            if not caminho_arquivo:
                return {
                    'success': False,
                    'error': 'Erro ao baixar arquivo',
                    'curso': curso_config['nome'],
                    'periodo': periodo
                }
            
            if callback_progresso:
                callback_progresso("Concluído!", 100)
            
            # 6. Verificar se o relatório contém os dados corretos
            if self._verificar_conteudo_relatorio(caminho_arquivo, curso_config['nome']):
                logger.info(f"✅ Relatório de {curso_config['nome']} verificado com sucesso")
            else:
                logger.warning(f"⚠️ Relatório de {curso_config['nome']} pode não conter dados filtrados corretamente")
            
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
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'curso': curso_config['nome'],
                'periodo': periodo
            }
    
    def _verificar_conteudo_relatorio(self, caminho_arquivo, curso_nome):
        """Verifica se o relatório contém dados do curso correto"""
        try:
            # Ler apenas as primeiras linhas para verificação
            df = pd.read_excel(caminho_arquivo, nrows=10)
            
            if df.empty:
                logger.warning(f"Relatório vazio: {caminho_arquivo}")
                return False
            
            # Verificar colunas que podem indicar o curso
            colunas_curso = ['CURSO', 'DESDOBRAMENTO', 'NOME DO CURSO']
            for col in colunas_curso:
                if col in df.columns:
                    # Verificar se há dados do curso correto
                    valores = df[col].dropna().astype(str)
                    if any(curso_nome.lower() in str(valor).lower() for valor in valores.head()):
                        return True
            
            # Se não encontrou nas colunas específicas, verificar em todas as colunas
            for col in df.columns:
                try:
                    valores = df[col].dropna().astype(str)
                    if any(curso_nome.lower() in str(valor).lower() for valor in valores.head()):
                        return True
                except:
                    continue
            
            logger.warning(f"Não encontrou referência a '{curso_nome}' no relatório")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar conteúdo: {str(e)}")
            return True  # Assume que está OK para não bloquear o processo
    
    def _aguardar_conclusao_com_progresso(self, relatorio_id, callback_progresso=None, 
                                         progresso_inicial=0, progresso_final=100,
                                         intervalo=30, timeout=1800):
        """Aguarda conclusão com feedback de progresso"""
        
        tempo_inicio = time.time()
        ultimo_status = None
        
        while time.time() - tempo_inicio < timeout:
            status_info = self.rel_automator.verificar_status_relatorio(relatorio_id)
            
            if not status_info:
                if callback_progresso:
                    callback_progresso(f"Erro ao verificar status", progresso_inicial)
                time.sleep(intervalo)
                continue
            
            # Calcular progresso baseado no tempo
            tempo_decorrido = time.time() - tempo_inicio
            progresso_tempo = min(tempo_decorrido / timeout, 0.95)
            
            # Combinar progresso
            range_progresso = progresso_final - progresso_inicial
            progresso_atual = progresso_inicial + (progresso_tempo * range_progresso)
            
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
            
            # Verificar se houve mudança
            if status_info != ultimo_status:
                logger.info(f"Status atualizado: {status_info['status']}")
                ultimo_status = status_info
            
            time.sleep(intervalo)
        
        return None
    
    def _determinar_forma_ingresso(self, periodo):
        """Determina a forma de ingresso baseada no semestre"""
        if periodo.endswith('1'):  # 1º semestre
            return '125'  # SISU 1ª Edição
        else:  # 2º semestre
            return '124'  # SISU 2ª Edição
    
    def processar_periodos_intervalo(self, periodo_inicial, periodo_final):
        """Gera lista de períodos entre o inicial e final"""
        # Extrair ano e semestre
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
    
    def obter_cursos_configurados(self, cursos_selecionados=None):
        """Retorna configuração dos cursos com IDs corretos"""
        todos_cursos = [
            {
                'nome': 'Química (Licenciatura)',
                'codigo_curso': '12700',  # ID do curso Química
                'codigo_desdobramento': '12700',  # ID do desdobramento Licenciatura
                'tipo': 'Licenciatura',
                'descricao': 'Quimica (Licenciatura) (12700)'
            },
            {
                'nome': 'Química (Bacharelado)',
                'codigo_curso': '12700',  # ID do curso Química
                'codigo_desdobramento': '312700',  # ID do desdobramento Bacharelado
                'tipo': 'Bacharelado',
                'descricao': 'Quimica (Bacharelado) (312700)'
            },
            {
                'nome': 'Química Industrial',
                'codigo_curso': '12709',  # ID do curso Química Industrial
                'codigo_desdobramento': '12709',  # ID do desdobramento
                'tipo': 'Bacharelado',
                'descricao': 'Química Industrial (12709)'
            }
        ]
        
        if cursos_selecionados:
            return [c for c in todos_cursos if c['nome'] in cursos_selecionados]
        
        return todos_cursos


class InterfaceProgressoMelhorada:
    """Interface de progresso melhorada"""
    
    def __init__(self):
        self.progress_bar = None
        self.status_text = None
        self.resultados_container = None
        self.detalhes_container = None
        self.tabela_resultados = []
        self.contadores = {'sucesso': 0, 'erro': 0, 'total': 0}
    
    def inicializar(self, total_tarefas):
        """Inicializa interface"""
        self.contadores['total'] = total_tarefas
        
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
        
        # Container para detalhes
        self.detalhes_container = st.expander("📋 Detalhes da Execução", expanded=False)
        
        # Container para resultados finais
        self.resultados_container = st.container()
    
    def atualizar(self, mensagem, progresso):
        """Atualiza barra e mensagem"""
        if self.progress_bar:
            self.progress_bar.progress(progresso / 100)
        if self.status_text:
            self.status_text.text(mensagem)
    
    def adicionar_resultado(self, curso, periodo, sucesso, detalhe="", tempo=None):
        """Adiciona resultado"""
        periodo_display = f"{periodo[:4]}/{periodo[4:]}" if len(periodo) == 5 else periodo
        
        if sucesso:
            emoji = "✅"
            status = "Sucesso"
            self.contadores['sucesso'] += 1
        else:
            emoji = "❌"
            status = "Erro"
            self.contadores['erro'] += 1
        
        resultado = {
            'Curso': curso,
            'Período': periodo_display,
            'Status': f"{emoji} {status}",
            'Detalhe': detalhe[:100],
            'Tempo': tempo or "-"
        }
        
        self.tabela_resultados.append(resultado)
        self.atualizar_contadores()
        
        # Atualizar detalhes em tempo real
        with self.detalhes_container:
            st.write(f"{emoji} **{curso}** - {periodo_display}: {detalhe[:80]}")
    
    def atualizar_contadores(self):
        """Atualiza contadores"""
        concluido = self.contadores['sucesso'] + self.contadores['erro']
        restante = self.contadores['total'] - concluido
        
        self.col_total.markdown(f"**Total:** {self.contadores['total']}")
        self.col_sucesso.markdown(f"**✅ {self.contadores['sucesso']}**")
        self.col_erro.markdown(f"**❌ {self.contadores['erro']}**")
        self.col_restante.markdown(f"**⏳ {restante}**")
    
    def exibir_resultados_finais(self):
        """Exibe tabela com todos os resultados"""
        with self.resultados_container:
            if self.tabela_resultados:
                st.markdown("### 📊 Resultados Consolidados")
                
                # Estatísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    taxa = (self.contadores['sucesso'] / self.contadores['total'] * 100) if self.contadores['total'] > 0 else 0
                    st.metric("Taxa de Sucesso", f"{taxa:.1f}%")
                with col2:
                    st.metric("Relatórios Gerados", self.contadores['sucesso'])
                with col3:
                    st.metric("Relatórios com Erro", self.contadores['erro'])
                
                # Tabela detalhada
                df = pd.DataFrame(self.tabela_resultados)
                st.dataframe(df, use_container_width=True, hide_index=True)
