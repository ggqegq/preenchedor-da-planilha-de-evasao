# gerador_relatorios_otimizado.py
import logging
import time
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class GeradorRelatoriosOtimizado:
    def __init__(self, session):
        self.session = session

    def criar_filtros_para_curso(self, curso_config, periodo, forma_ingresso):
        """
        CORREÇÃO: O SIGA exige que os campos estejam dentro de 'filtros[]'
        """
        ano = periodo[:4]
        semestre = periodo[4]
        
        # O segredo está nestas chaves com colchetes, conforme o HTML original
        return {
            'utf8': '✓',
            'filtros[idlocalidade]': '1', 
            'filtros[idcurso]': str(curso_config['codigo_curso']),
            'filtros[iddesdobramento]': str(curso_config['codigo_desdobramento']),
            'filtros[idnivelcurso]': str(curso_config['nivel']),
            'filtros[idturno]': '',
            'filtros[idstatusaluno]': '',
            'filtros[idsituacaoaluno]': '',
            'filtros[idformaingresso]': str(forma_ingresso),
            'filtros[idacaoafirmativa]': '',
            'filtros[anosem_ingresso]': f"{ano}/{semestre}",
            'filtros[anosem_desvinculacao]': '',
            'format': 'xls'
        }

# Adicionando as classes que o main.py tenta importar para evitar o ImportError
class ProcessadorDadosOtimizado:
    def __init__(self):
        pass
    def processar(self, dados):
        return pd.DataFrame(dados)

class InterfaceProgresso:
    def __init__(self):
        pass
