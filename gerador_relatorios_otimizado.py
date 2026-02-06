# gerador_relatorios_otimizado.py
"""
Módulo corrigido para geração de relatórios com mapeamento correto de campos do SIGA
"""
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeradorRelatoriosOtimizado:
    """Classe otimizada para gerar relatórios em lote"""
    
    def __init__(self, session):
        self.session = session
        # Assume-se que FormularioHandler e RelatorioUFFAutomator estão configurados corretamente
        # self.form_handler = FormularioHandler(session)
        # self.rel_automator = RelatorioUFFAutomator(session)

    def criar_filtros_para_curso(self, curso_config, periodo, forma_ingresso, csrf_token=None):
        """
        Cria dicionário de filtros corrigido com a nomenclatura 'filtros[campo]'
        conforme exigido pelo formulário HTML do SIGA/UFF.
        """

        # O período vem como '20251' ou '20252'
        ano = periodo[:4]
        semestre = periodo[4]
        
        # Mapeamento exato dos campos encontrados no HTML fornecido
        filtros = {
            'utf8': '✓',
            'authenticity_token': csrf_token or '', # Token extraído do HTML 
            'filtros[idlocalidade]': '1',           # Niterói
            'filtros[idcurso]': str(curso_config['codigo_curso']), # ID do Curso 
            'filtros[iddesdobramento]': str(curso_config['codigo_desdobramento']),
            'filtros[idnivelcurso]': str(curso_config['nivel']),
            'filtros[idturno]': '',
            'filtros[idstatusaluno]': '',
            'filtros[idsituacaoaluno]': '',
            'filtros[idformaingresso]': str(forma_ingresso),
            'filtros[idacaoafirmativa]': '',
            'filtros[anosem_ingresso]': f'{ano}/{semestre}',
            'filtros[anosem_desvinculacao]': '',
            'format': 'xls' # Valor do botão clicado [cite: 15]
        }

        return filtros

    def gerar_relatorio_individual_com_progresso(self, curso_config, periodo, forma_ingresso, callback_progresso=None):
        """Gera um relatório individual com feedback de progresso"""
        logger.info(f"Gerando relatório: {curso_config['nome']} - Período {periodo}")
        
        try:
            # 1. Obter o token CSRF da página de pesquisa antes de enviar
            # Isso é vital para que o servidor aceite a requisição
            response_busca = self.session.get("URL_DA_PAGINA_DE_PESQUISA") 
            # (Substitua pela URL real onde está o formulário do arquivo .txt)
            
            # Aqui você usaria o BeautifulSoup para pegar o token do HTML fornecido:
            # <meta name="csrf-token" content="..." /> [cite: 1, 17]
            csrf_token = "ONa/DhwamHeUKqiGfoYq9/w9FPb1ZxwSv7BqXum2/StwcPKjFPOfCZ6PF5eknGJ4aSVtg2e1vowqiKSvFF80oQ==" # Exemplo do seu arquivo
            
            if callback_progresso:
                callback_progresso(f"Preparando {curso_config['nome']} - {periodo[:4]}/{periodo[4:]}", 0)
            
            # Criar filtros com a nomenclatura correta 'filtros[idcurso]'
            filtros = self.criar_filtros_para_curso(curso_config, periodo, forma_ingresso, csrf_token)
            
            if callback_progresso:
                callback_progresso(f"Enviando solicitação com filtros de curso...", 10)
            
            # Enviar para o form_handler (certifique-se que ele faz um POST para a URL correta)
            resultado = self.form_handler.gerar_relatorio(filtros)
            
            # ... resto da sua lógica de acompanhamento ...
            return resultado

        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            return {'success': False, 'error': str(e)}
