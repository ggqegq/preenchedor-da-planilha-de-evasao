"""
auth.py - Módulo de autenticação no sistema UFF
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlencode, parse_qs, urlparse
import logging
from config import *

logger = logging.getLogger(__name__)

class UFFAuthenticator:
    """Classe para gerenciar autenticação no sistema UFF"""
    
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
        self.auth_data = {}
    
    def login(self, username=None, password=None):
        """Realiza login no sistema UFF"""
        if username:
            self.username = username
        if password:
            self.password = password
        
        if not self.username or not self.password:
            raise ValueError("Usuário e senha são obrigatórios")
        
        try:
            logger.info(f"Tentando login para usuário: {self.username}")
            
            # Primeiro, acessar a página de login para obter parâmetros OAuth
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar link de login
            login_link = soup.find('a', href=lambda x: x and 'openid-connect' in x)
            if login_link:
                login_url = login_link['href']
                logger.info(f"URL de login encontrada: {login_url}")
            else:
                # Tentar padrão comum
                login_url = LOGIN_URL
                params = {
                    'client_id': 'graduacao-administracaoacademica',
                    'redirect_uri': f'{APLICACAO_URL}/',
                    'response_type': 'code',
                    'scope': 'openid',
                    'state': self._generate_state()
                }
                login_url = f"{LOGIN_URL}?{urlencode(params)}"
            
            # Acessar página de login OAuth
            response = self.session.get(login_url, timeout=TIMEOUT_REQUESTS)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extrair parâmetros do formulário de login
            form = soup.find('form')
            if not form:
                raise Exception("Formulário de login não encontrado")
            
            # Preparar dados do formulário
            form_data = {}
            for input_tag in form.find_all('input'):
                if input_tag.get('name'):
                    form_data[input_tag['name']] = input_tag.get('value', '')
            
            # Adicionar credenciais
            form_data['username'] = self.username
            form_data['password'] = self.password
            
            # Encontrar URL de ação do formulário
            action_url = form.get('action', '')
            if not action_url.startswith('http'):
                # Construir URL completa
                parsed = urlparse(login_url)
                action_url = f"{parsed.scheme}://{parsed.netloc}{action_url}"
            
            # Submeter formulário de login
            response = self.session.post(
                action_url,
                data=form_data,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            # Verificar se login foi bem-sucedido
            if response.url and APLICACAO_URL in response.url:
                self.is_authenticated = True
                logger.info("Login realizado com sucesso!")
                
                # Extrair token CSRF
                self._extract_csrf_token(response.text)
                
                # Salvar cookies de sessão
                self.auth_data['cookies'] = dict(self.session.cookies)
                self.auth_data['headers'] = dict(self.session.headers)
                
                return True
            else:
                logger.error("Login falhou. Verifique as credenciais.")
                return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            return False
    
    def _generate_state(self):
        """Gera um state para OAuth"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    def _extract_csrf_token(self, html_content):
        """Extrai token CSRF do HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Procurar meta tag CSRF
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token and meta_token.get('content'):
            self.auth_data['csrf_token'] = meta_token['content']
            self.session.headers['X-CSRF-Token'] = meta_token['content']
            logger.info(f"CSRF Token extraído: {meta_token['content'][:20]}...")
        
        # Procurar input hidden
        input_token = soup.find('input', {'name': 'authenticity_token'})
        if input_token and input_token.get('value'):
            self.auth_data['authenticity_token'] = input_token['value']
            logger.info(f"Authenticity Token extraído: {input_token['value'][:20]}...")
    
    def logout(self):
        """Realiza logout do sistema"""
        if self.is_authenticated:
            try:
                logout_url = f"{BASE_URL}/auth/realms/master/protocol/openid-connect/logout"
                response = self.session.get(logout_url, timeout=TIMEOUT_REQUESTS)
                self.is_authenticated = False
                self.session.cookies.clear()
                logger.info("Logout realizado com sucesso")
            except Exception as e:
                logger.error(f"Erro durante logout: {str(e)}")
    
    def check_session(self):
        """Verifica se a sessão ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            return response.status_code == 200 and 'Sair' in response.text
        except:
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None
