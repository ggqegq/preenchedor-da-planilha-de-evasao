import streamlit as st
from uff_client import UFFClient

st.set_page_config(page_title="Relatórios UFF", layout="centered")
st.title("Gerador de Relatórios UFF")

usuario = st.text_input("Usuário UFF")
senha = st.text_input("Senha", type="password")

curso = st.selectbox(
    "Curso",
    ["Química", "Química Industrial"]
)

semestre = st.selectbox(
    "Semestre de ingresso",
    ["2025/1°", "2025/2°"]
)

if st.button("Gerar relatório"):
    try:
        client = UFFClient(usuario, senha)
        client.login()

        filtros = {
            "localidade": "Niterói",
            "curso": curso,
            "ano_semestre_ingresso": semestre,
            "forma_ingresso": "SISU"
        }

        relatorio_id = client.gerar_relatorio(filtros)
        arquivo = client.baixar_xlsx(relatorio_id)

        st.success("Relatório gerado com sucesso!")

        st.download_button(
            label="Baixar XLSX",
            data=arquivo,
            file_name=f"relatorio_{curso}_{semestre}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Erro ao gerar relatório: {e}")
