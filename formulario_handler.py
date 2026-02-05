"""
formulario_handler.py - Manipulação de formulários do sistema
"""
import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urljoin
from config import *
from utils import *

logger = logging.getLogger(__name__)

class FormularioHandler:
    """Classe para manipular formulários do sistema UFF"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
    
    def acessar_pagina_listagem(self):
        """Acessa a página de listagem de alunos"""
        try:
            response = self.session.get(LISTAGEM_ALUNOS_URL, timeout=TIMEOUT_REQUESTS)
            response.raise_for_status()
            
            # Verificar se estamos na página correta
            soup = BeautifulSoup(response.text, 'html.parser')
            if 'Listagem de Alunos' not in soup.text:
                raise Exception("Não está na página de listagem de alunos")
            
            return soup
        except Exception as e:
            logger.error(f"Erro ao acessar página de listagem: {str(e)}")
            raise
    
    def extrair_parametros_formulario(self, soup):
        """Extrai parâmetros do formulário da página"""
        formulario = soup.find('form', action=lambda x: x and 'listagens_alunos' in x)
        
        if not formulario:
            raise Exception("Formulário de listagem não encontrado")
        
        parametros = {
            'action': formulario.get('action', ''),
            'method': formulario.get('method', 'post').lower(),
            'inputs': {},
            'selects': {}
        }
        
        # Extrair inputs
        for input_tag in formulario.find_all('input'):
            name = input_tag.get('name')
            if name:
                parametros['inputs'][name] = {
                    'type': input_tag.get('type', 'text'),
                    'value': input_tag.get('value', '')
                }
        
        # Extrair selects
        for select_tag in formulario.find_all('select'):
            name = select_tag.get('name')
            if name:
                options = []
                for option in select_tag.find_all('option'):
                    options.append({
                        'value': option.get('value', ''),
                        'text': option.get_text(strip=True),
                        'selected': 'selected' in option.attrs
                    })
                parametros['selects'][name] = options
        
        # Extrair tokens CSRF
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token:
            parametros['csrf_token'] = meta_token.get('content', '')
        
        input_token = soup.find('input', {'name': 'authenticity_token'})
        if input_token:
            parametros['authenticity_token'] = input_token.get('value', '')
        
        logger.info(f"Formulário extraído com {len(parametros['inputs'])} inputs e {len(parametros['selects'])} selects")
        return parametros
    
    def preencher_formulario(self, parametros_formulario, filtros):
        """Preenche o formulário com os filtros especificados"""
        dados_formulario = {}
        
        # Adicionar tokens CSRF
        if 'authenticity_token' in parametros_formulario:
            dados_formulario['authenticity_token'] = parametros_formulario['authenticity_token']
        
        # Adicionar parâmetros padrão do formulário
        for name, input_info in parametros_formulario['inputs'].items():
            if input_info['value']:
                dados_formulario[name] = input_info['value']
        
        # Aplicar filtros
        for campo, valor in filtros.items():
            if campo in parametros_formulario['selects']:
                # Verificar se o valor existe nas opções
                opcoes = parametros_formulario['selects'][campo]
                valor_encontrado = False
                
                for opcao in opcoes:
                    if str(opcao['value']) == str(valor) or opcao['text'] == valor:
                        dados_formulario[campo] = opcao['value']
                        valor_encontrado = True
                        logger.info(f"Filtro aplicado: {campo} = {valor} (valor: {opcao['value']})")
                        break
                
                if not valor_encontrado:
                    logger.warning(f"Valor '{valor}' não encontrado para campo '{campo}'")
            elif campo in parametros_formulario['inputs']:
                dados_formulario[campo] = valor
                logger.info(f"Input aplicado: {campo} = {valor}")
        
        return dados_formulario
    
    def submeter_formulario(self, dados_formulario, action_url):
        """Submete o formulário e retorna a resposta"""
        try:
            # Construir URL completa
            if not action_url.startswith('http'):
                action_url = urljoin(self.base_url, action_url)
            
            logger.info(f"Submetendo formulário para: {action_url}")
            logger.debug(f"Dados do formulário: {dados_formulario}")
            
            # Submeter formulário
            response = self.session.post(
                action_url,
                data=dados_formulario,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            response.raise_for_status()
            
            # Verificar se a submissão foi bem-sucedida
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Verificar mensagens de sucesso
            alert_success = soup.find('div', class_='alert-success')
            if alert_success and 'sucesso' in alert_success.text.lower():
                logger.info("Formulário submetido com sucesso!")
                
                # Tentar extrair ID do relatório da URL
                relatorio_id = self._extrair_id_relatorio(response.url)
                if relatorio_id:
                    logger.info(f"ID do relatório detectado: {relatorio_id}")
                    return {
                        'success': True,
                        'relatorio_id': relatorio_id,
                        'url_relatorio': response.url,
                        'html': response.text
                    }
            
            # Verificar erros
            alert_error = soup.find('div', class_='alert-error') or soup.find('div', class_='alert-danger')
            if alert_error:
                error_msg = alert_error.get_text(strip=True)[:200]
                logger.error(f"Erro no formulário: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'html': response.text
                }
            
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url and response.url != action_url:
                relatorio_id = self._extrair_id_relatorio(response.url)
                return {
                    'success': True,
                    'relatorio_id': relatorio_id,
                    'url_relatorio': response.url,
                    'html': response.text
                }
            
            logger.warning("Não foi possível determinar o resultado da submissão")
            return {
                'success': False,
                'error': 'Resultado indeterminado',
                'html': response.text
            }
            
        except Exception as e:
            logger.error(f"Erro ao submeter formulário: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extrair_id_relatorio(self, url):
        """Extrai o ID do relatório da URL"""
        match = re.search(r'/relatorios/(\d+)', url)
        return match.group(1) if match else None
    
    def gerar_relatorio(self, filtros):
        """Fluxo completo para gerar um relatório"""
        try:
            # 1. Acessar página de listagem
            logger.info("Acessando página de listagem de alunos...")
            soup = self.acessar_pagina_listagem()
            
            # 2. Extrair parâmetros do formulário
            logger.info("Extraindo parâmetros do formulário...")
            parametros = self.extrair_parametros_formulario(soup)
            
            # 3. Preencher formulário
            logger.info("Preenchendo formulário com filtros...")
            dados_formulario = self.preencher_formulario(parametros, filtros)
            
            # 4. Submeter formulário
            logger.info("Submetendo formulário...")
            resultado = self.submeter_formulario(dados_formulario, parametros['action'])
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro no fluxo de geração: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
