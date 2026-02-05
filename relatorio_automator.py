"""
relatorio_automator.py - Monitoramento e download de relatórios
"""
import requests
from bs4 import BeautifulSoup
import time
import os
import re
from datetime import datetime
import pandas as pd
import logging
from config import *
from utils import *

logger = logging.getLogger(__name__)

class RelatorioUFFAutomator:
    """Classe para monitorar e baixar relatórios do sistema UFF"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
        
    def verificar_status_relatorio(self, relatorio_id):
        """Verifica o status de processamento de um relatório"""
        url = f"{self.base_url}/relatorios/{relatorio_id}"
        
        try:
            logger.info(f"Verificando status do relatório #{relatorio_id}")
            response = self.session.get(url, timeout=TIMEOUT_REQUESTS)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return self._parse_status_page(soup, relatorio_id)
            
        except Exception as e:
            logger.error(f"Erro ao verificar status do relatório {relatorio_id}: {str(e)}")
            return None
    
    def _parse_status_page(self, soup, relatorio_id):
        """Analisa a página de status do relatório"""
        status_info = {
            'id': relatorio_id,
            'status': 'DESCONHECIDO',
            'etapas': [],
            'detalhes': {},
            'filtros': {},
            'download_url': None,
            'titulo': None
        }
        
        # Extrair título
        h1 = soup.find('h1')
        if h1:
            status_info['titulo'] = h1.get_text(strip=True)
        
        # Analisar barra de progresso
        steps_bar = soup.find('div', {'id': 'relatorioStepsBar'})
        if steps_bar:
            status_info['etapas'] = self._parse_steps_bar(steps_bar)
        
        # Analisar detalhes do pedido
        detalhes_card = soup.find('div', class_='card-body')
        if detalhes_card:
            status_info['detalhes'] = self._parse_detalhes_card(detalhes_card)
        
        # Analisar filtros
        filtros_card = soup.find('div', class_='card-info')
        if filtros_card:
            status_info['filtros'] = self._parse_filtros_card(filtros_card)
        
        # Procurar link de download
        download_link = self._find_download_link(soup)
        if download_link:
            status_info['download_url'] = download_link
            status_info['status'] = 'PRONTO'
        elif status_info.get('detalhes', {}).get('processado_em') not in [None, '---', '']:
            status_info['status'] = 'PROCESSADO'
        elif status_info['etapas']:
            status_info['status'] = 'EM_PROCESSAMENTO'
        
        return status_info
    
    def _parse_steps_bar(self, steps_bar):
        """Analisa a barra de etapas do processamento"""
        etapas = []
        steps = steps_bar.find_all('div', class_='step')
        
        for i, step in enumerate(steps, 1):
            # Verificar se está marcado como done
            is_done = 'done' in step.get('class', [])
            
            # Encontrar texto da etapa atual
            label_active = step.find('span', class_='label-active')
            label_done = step.find('span', class_='label-done')
            
            if label_done and (is_done or label_done.get_text(strip=True)):
                etapa_texto = label_done.get_text(strip=True)
                etapas.append(f"Etapa {i}: {etapa_texto} {'(Concluída)' if is_done else ''}")
            elif label_active:
                etapa_texto = label_active.get_text(strip=True)
                etapas.append(f"Etapa {i}: {etapa_texto} (Em andamento)")
        
        return etapas
    
    def _parse_detalhes_card(self, card_body):
        """Analisa o card de detalhes do pedido"""
        detalhes = {}
        rows = card_body.find_all(['dt', 'dd'])
        
        current_key = None
        for element in rows:
            if element.name == 'dt':
                current_key = element.get_text(strip=True).replace(':', '').lower()
            elif element.name == 'dd' and current_key:
                detalhes[current_key] = element.get_text(strip=True)
                current_key = None
        
        return detalhes
    
    def _parse_filtros_card(self, filtros_card):
        """Analisa o card de filtros aplicados"""
        filtros = {}
        rows = filtros_card.find_all('div', class_='row')
        
        for row in rows:
            cols = row.find_all('div', recursive=False)
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True).replace(':', '').replace('*', '').strip()
                value = cols[1].get_text(strip=True)
                if key and value and value != '-':
                    filtros[key] = value
        
        return filtros
    
    def _find_download_link(self, soup):
        """Procura por link de download na página"""
        # Tentar diferentes padrões de link de download
        patterns = [
            'a[href*="download"]',
            'a:contains("Download")',
            'a:contains("Baixar")',
            'a:contains("download")',
            'a.btn-primary[href]'
        ]
        
        for pattern in patterns:
            try:
                if 'contains' in pattern:
                    # Busca por texto
                    text = pattern.split('"')[1]
                    links = soup.find_all('a', string=lambda s: s and text.lower() in s.lower())
                else:
                    # Busca por seletor CSS
                    links = soup.select(pattern)
                
                for link in links:
                    href = link.get('href', '')
                    if href and ('.xlsx' in href.lower() or 'download' in href.lower()):
                        if not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        return href
            except:
                continue
        
        return None
    
    def aguardar_conclusao(self, relatorio_id, callback_progresso=None, 
                          intervalo=INTERVALO_VERIFICACAO, timeout=TIMEOUT_PROCESSAMENTO):
        """Aguarda a conclusão do processamento do relatório"""
        logger.info(f"Iniciando monitoramento do relatório #{relatorio_id}")
        logger.info(f"Timeout: {timeout}s, Intervalo: {intervalo}s")
        
        tempo_inicio = time.time()
        ultimo_status = None
        
        while time.time() - tempo_inicio < timeout:
            status_info = self.verificar_status_relatorio(relatorio_id)
            
            if not status_info:
                if callback_progresso:
                    callback_progresso(0, "Erro ao verificar status", False)
                time.sleep(intervalo)
                continue
            
            # Calcular progresso baseado no tempo
            tempo_decorrido = time.time() - tempo_inicio
            progresso = min(tempo_decorrido / timeout, 0.95)
            
            # Mensagem de status
            mensagem = f"Status: {status_info.get('status', 'Desconhecido')}"
            if status_info.get('etapas'):
                mensagem += f" | {status_info['etapas'][-1] if status_info['etapas'] else ''}"
            
            # Chamar callback de progresso
            if callback_progresso:
                callback_progresso(progresso, mensagem, False)
            
            # Verificar se está pronto
            if status_info['status'] == 'PRONTO':
                if callback_progresso:
                    callback_progresso(1.0, "✅ Relatório pronto para download!", True)
                logger.info(f"Relatório #{relatorio_id} está pronto!")
                return status_info
            
            # Verificar se houve mudança significativa
            if status_info != ultimo_status:
                logger.info(f"Status atualizado: {status_info['status']}")
                if status_info.get('detalhes'):
                    logger.info(f"Detalhes: {status_info['detalhes']}")
                ultimo_status = status_info
            
            time.sleep(intervalo)
        
        # Timeout atingido
        timeout_msg = f"Timeout após {timeout//60} minutos"
        logger.warning(timeout_msg)
        if callback_progresso:
            callback_progresso(1.0, f"⏰ {timeout_msg}", False)
        
        return None
    
    def baixar_relatorio(self, status_info, pasta_destino=PASTA_RELATORIOS):
        """Baixa o relatório quando estiver pronto"""
        if not status_info or not status_info.get('download_url'):
            logger.error("URL de download não disponível")
            return None
        
        try:
            # Criar pasta de destino
            os.makedirs(pasta_destino, exist_ok=True)
            
            # Gerar nome de arquivo descritivo
            nome_arquivo = self._gerar_nome_arquivo(status_info)
            caminho_completo = os.path.join(pasta_destino, nome_arquivo)
            
            logger.info(f"Iniciando download: {nome_arquivo}")
            logger.info(f"URL: {status_info['download_url']}")
            
            # Fazer download
            response = self.session.get(
                status_info['download_url'],
                stream=True,
                timeout=TIMEOUT_REQUESTS
            )
            response.raise_for_status()
            
            # Salvar arquivo
            tamanho_total = int(response.headers.get('content-length', 0))
            tamanho_baixado = 0
            
            with open(caminho_completo, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        tamanho_baixado += len(chunk)
                        
                        # Log progresso a cada 1MB
                        if tamanho_baixado % (1024 * 1024) < 8192:
                            progresso = (tamanho_baixado / tamanho_total * 100) if tamanho_total > 0 else 0
                            logger.info(f"Download: {tamanho_baixado/(1024*1024):.1f}MB ({progresso:.1f}%)")
            
            logger.info(f"Download concluído: {caminho_completo} ({tamanho_baixado/(1024*1024):.1f}MB)")
            
            # Validar arquivo
            if self._validar_arquivo_excel(caminho_completo):
                logger.info("Arquivo Excel validado com sucesso")
                return caminho_completo
            else:
                logger.warning("Arquivo baixado pode não ser um Excel válido")
                return caminho_completo
            
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {str(e)}")
            return None
    
    def _gerar_nome_arquivo(self, status_info):
        """Gera um nome descritivo para o arquivo"""
        filtros = status_info.get('filtros', {})
        
        # Extrair informações principais
        curso = filtros.get('Curso', 'desconhecido').replace(' ', '_').replace('/', '_')
        desdobramento = filtros.get('Desdobramento', 'desconhecido')
        
        # Extrair código do desdobramento
        codigo_match = re.search(r'\((\d+)\)', desdobramento)
        codigo = codigo_match.group(1) if codigo_match else 'sem_codigo'
        
        # Limpar nome do desdobramento
        desdobramento_limpo = desdobramento.split('(')[0].strip().replace(' ', '_')
        
        # Ano/Semestre
        ingresso = filtros.get('Ano/Semestre de Ingresso', 'sem_ingresso')
        ingresso_limpo = ingresso.replace('/', '-').replace(' ', '').replace('º', '')
        
        # Timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Montar nome do arquivo
        nome = f"relatorio_{curso}_{desdobramento_limpo}_{codigo}_{ingresso_limpo}_{timestamp}.xlsx"
        
        # Remover caracteres inválidos
        nome = re.sub(r'[<>:"|?*]', '', nome)
        nome = nome.replace('__', '_').replace('__', '_')  # Remover duplos underscores
        
        return nome
    
    def _validar_arquivo_excel(self, caminho_arquivo):
        """Valida se o arquivo é um Excel válido"""
        try:
            # Tentar ler as primeiras linhas
            df = pd.read_excel(caminho_arquivo, nrows=5)
            logger.info(f"Arquivo válido: {len(df)} linhas, {len(df.columns)} colunas")
            return True
        except Exception as e:
            logger.warning(f"Arquivo não é um Excel válido: {str(e)}")
            return False
