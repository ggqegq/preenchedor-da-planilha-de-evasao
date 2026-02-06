# gerador_relatorios_otimizado.py

import logging
import time
import os
from datetime import datetime
from typing import Optional

import requests

from formulario_handler import FormularioHandler
from relatorio_automator import RelatorioUFFAutomator

logger = logging.getLogger(__name__)


class GeradorRelatoriosOtimizado:
    """Classe para geração otimizada de relatórios do SIGA"""

    def __init__(self, session: requests.Session):
        self.session = session
        self.form_handler = FormularioHandler(session)
        self.rel_automator = RelatorioUFFAutomator(session)

    # ==========================================================
    # CURSOS
    # ==========================================================
    def obter_cursos_predefinidos(self, cursos_selecionados=None):
        cursos = [
            {
                "nome": "Química (Licenciatura)",
                "codigo_curso": "12700",
                "codigo_desdobramento": "12700",
                "nivel": "1",
            },
            {
                "nome": "Química (Bacharelado)",
                "codigo_curso": "12700",
                "codigo_desdobramento": "312700",
                "nivel": "2",
            },
            {
                "nome": "Química Industrial",
                "codigo_curso": "12709",
                "codigo_desdobramento": "12709",
                "nivel": "2",
            },
        ]

        if cursos_selecionados:
            return [c for c in cursos if c["nome"] in cursos_selecionados]

        return cursos

    # ==========================================================
    # FILTROS
    # ==========================================================
    def criar_filtros_para_curso(self, curso_config, periodo, forma_ingresso):
        ano = periodo[:4]
        semestre = periodo[4]

        filtros = {
            "idlocalidade": "1",  # Niterói
            "idcurso": curso_config["codigo_curso"],
            "iddesdobramento": curso_config["codigo_desdobramento"],
            "idnivelcurso": curso_config["nivel"],
            "idturno": "",
            "idstatusaluno": "",
            "idsituacaoaluno": "",
            "idformaingresso": forma_ingresso,
            "idacaoafirmativa": "",
            "anosem_ingresso": f"{ano}/{semestre}",
            "anosem_desvinculacao": "",
            "format": "xls",
        }

        return filtros

    # ==========================================================
    # RELATÓRIO INDIVIDUAL
    # ==========================================================
    def gerar_relatorio_individual(self, curso_config, periodo, forma_ingresso):
        logger.info(
            f"Iniciando: {curso_config['nome']} - {periodo[:4]}/{periodo[4]}"
        )

        filtros = self.criar_filtros_para_curso(
            curso_config, periodo, forma_ingresso
        )

        resultado = self.form_handler.gerar_relatorio(filtros)

        if not resultado.get("success"):
            raise RuntimeError(resultado.get("error", "Erro ao gerar relatório"))

        relatorio_id = resultado.get("relatorio_id")
        if not relatorio_id:
            raise RuntimeError("ID do relatório não retornado")

        status_info = self.rel_automator.aguardar_relatorio_pronto(relatorio_id)
        if not status_info:
            raise RuntimeError("Relatório não ficou pronto")

        caminho = self.rel_automator.baixar_relatorio(status_info)
        return caminho
