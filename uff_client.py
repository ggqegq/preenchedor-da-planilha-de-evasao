import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from config import *

class UFFClient:
    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.username = username
        self.password = password

    # ---------------- LOGIN ----------------
    def login(self):
        r = self.session.get(APLICACAO_URL)
        soup = BeautifulSoup(r.text, "html.parser")

        form = soup.find("form")
        action = form["action"]

        payload = {
            "username": self.username,
            "password": self.password
        }

        for inp in form.find_all("input", type="hidden"):
            payload[inp["name"]] = inp.get("value", "")

        login_url = action if action.startswith("http") else urljoin(BASE_URL, action)
        resp = self.session.post(login_url, data=payload)

        if APLICACAO_URL not in resp.url:
            raise Exception("Falha no login")

    # ---------------- FORMULÁRIO ----------------
    def gerar_relatorio(self, filtros):
        page = self.session.get(LISTAGEM_ALUNOS_URL)
        soup = BeautifulSoup(page.text, "html.parser")

        form = soup.find("form")
        action = urljoin(APLICACAO_URL, form["action"])

        data = {}
        for inp in form.find_all("input"):
            if inp.get("name"):
                data[inp["name"]] = inp.get("value", "")

        for select in form.find_all("select"):
            name = select["name"]
            if name in filtros:
                for opt in select.find_all("option"):
                    if filtros[name] in opt.text:
                        data[name] = opt["value"]

        resp = self.session.post(action, data=data, allow_redirects=True)

        match = re.search(r"/relatorios/(\d+)", resp.url)
        if not match:
            raise Exception("ID do relatório não encontrado")

        return match.group(1)

    # ---------------- DOWNLOAD ----------------
    def baixar_xlsx(self, relatorio_id):
        url = f"{RELATORIOS_URL}/{relatorio_id}/xlsx"
        r = self.session.get(url)
        r.raise_for_status()
        return r.content
