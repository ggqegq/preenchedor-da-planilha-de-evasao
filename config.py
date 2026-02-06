"""
config.py - Configurações do projeto de automação de relatórios UFF
"""

# URLs do sistema
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
TOKEN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/token"

# Caminhos relativos
RELATORIOS_URL = f"{APLICACAO_URL}/relatorios"
LISTAGEM_ALUNOS_URL = f"{APLICACAO_URL}/relatorios/listagens_alunos"

# Parâmetros padrão
PARAMETROS_PADRAO = {
    'localidade': 'Niterói',
    'tipo_saida': 'xlsx',
    'gerar_button': 'Gerar relatório em xlsx'
}

# Mapeamento de cursos
CURSOS = {
    'quimica': {
        'nome': 'Química',
        'desdobramentos': {
            'licenciatura': {
                'nome': 'Química (Licenciatura) (12700)',
                'codigo': '12700'
            },
            'bacharelado': {
                'nome': 'Química (Bacharelado) (312700)',
                'codigo': '312700'
            }
        }
    },
    'quimica_industrial': {
        'nome': 'Química Industrial',
        'desdobramentos': {
            'default': {
                'nome': 'Química Industrial (12709)',
                'codigo': '12709'
            }
        }
    }
}

# Formas de ingresso
FORMAS_INGRESSO = {
    '1': 'SISU 1ª Edição',
    '2': 'SISU 2ª Edição',
    '-': '-'
}

# Headers para requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Configurações de timeout
TIMEOUT_REQUESTS = 30
TIMEOUT_PROCESSAMENTO = 3600  # 1 hora
INTERVALO_VERIFICACAO = 30  # segundos

# Caminhos de arquivos
PASTA_RELATORIOS = 'relatorios'
LOG_FILE = 'relatorios_uff.log'
