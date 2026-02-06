# relatorio_automator.py
"""
Automação dos relatórios do SIGA / Administração Acadêmica - UFF
Fluxo real:
1) POST gera relatório
2) Relatório aparece em /relatorios
3) Download via link específico
"""

import os
import time
import logging
import requests
from bs4 import BeautifulSoup

from config import PASTA_RELATORIOS

logger = logging.getLogger(__name__)


class RelatorioUFFAutomator:

    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = "https://app.uff.br/graduacao/administracaoacademica"

    # ==========================================================
    # 1️⃣ Verificar status do relatório (SCRAPING REAL)
    # ==========================================================
    def verificar_status_relatorio(self, relatorio_id: str):
        """
        O SIGA NÃO possui endpoint JSON de status.
        A única forma é varrer a página /relatorios
        """

        url = f"{self.base_url}/relatorios"
        resp = self.session.get(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        tabela = soup.find("table")
        if not tabela:
            logger.warning("Tabela de relatórios não encontrada")
            return None

        for linha in tabela.find_all("tr"):
            colunas = linha.find_all("td")
            if not colunas:
                continue

            texto_linha = linha.get_text(strip=True)

            if relatorio_id in texto_linha:
                status = "PROCESSANDO"
                etapas = []

                for col in colunas:
                    texto = col.get_text(strip=True)
                    etapas.append(texto)

                    if texto.upper() in ("PRONTO", "CONCLUÍDO", "CONCLUIDO"):
                        status = "PRONTO"

                logger.info(f"Relatório {relatorio_id} encontrado - status: {status}")

                return {
                    "id": relatorio_id,
                    "status": status,
                    "etapas": etapas
                }

        logger.info(f"Relatório {relatorio_id} ainda não listado")
        return {
            "id": relatorio_id,
            "status": "PROCESSANDO",
            "etapas": []
        }

    # ==========================================================
    # 2️⃣ Aguardar conclusão (polling seguro)
    # ==========================================================
    def aguardar_relatorio_pronto(self, relatorio_id, timeout=1800, intervalo=20):
        """
        Aguarda até o relatório ficar PRONTO ou estourar timeout
        """

        inicio = time.time()

        while time.time() - inicio < timeout:
            status_info = self.verificar_status_relatorio(relatorio_id)

            if status_info and status_info.get("status") == "PRONTO":
                return status_info

            time.sleep(intervalo)

        logger.error(f"Timeout aguardando relatório {relatorio_id}")
        return None

    # ==========================================================
    # 3️⃣ Baixar relatório (URL REAL)
    # ==========================================================
    def baixar_relatorio(self, status_info):
        """
        Download real via link /download
        """

        relatorio_id = status_info["id"]

        url = f"{self.base_url}/relatorios/{relatorio_id}/download"

        resp = self.session.get(url, stream=True)
        resp.raise_for_status()

        os.makedirs(PASTA_RELATORIOS, exist_ok=True)

        nome_arquivo = f"relatorio_{relatorio_id}.xlsx"
        caminho = os.path.join(PASTA_RELATORIOS, nome_arquivo)

        with open(caminho, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Relatório {relatorio_id} salvo em {caminho}")
        return caminho
