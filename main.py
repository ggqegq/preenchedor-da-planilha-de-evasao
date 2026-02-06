import streamlit as st
from uff_client import UFFClient
from config import *

st.title("Gerador de Relatórios UFF")

user = st.text_input("Usuário")
pwd = st.text_input("Senha", type="password")

curso = st.selectbox("Curso", ["Química", "Química Industrial"])
semestre = st.selectbox("Semestre", ["2025/1°", "2025/2°"])

if st.button("Gerar relatório"):
    client = UFFClient(user, pwd)
    client.login()

    filtros = {
        "localidade": "Niterói",
        "curso": curso,
        "ano_semestre_ingresso": semestre,
        "forma_ingresso": "SISU"
    }

    relatorio_id = client.gerar_relatorio(filtros)
    arquivo = client.baixar_xlsx(relatorio_id)

    st.download_button(
        "Baixar XLSX",
        arquivo,
        file_name=f"relatorio_{curso}_{semestre}.xlsx"
    )
