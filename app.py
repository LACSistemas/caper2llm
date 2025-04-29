# app.py
import streamlit as st
import os
import tempfile
import fitz                     
import google.generativeai as genai
from datetime import datetime
import logging

# ───────────────────────────── Configurações básicas ────────────────────────────
logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Legal Case Analyzer", layout="wide")

# ------------------------------------------------------------------------------
# Funções utilitárias
# ------------------------------------------------------------------------------

def get_api_key():
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        st.sidebar.error("Chave da API não encontrada em secrets.toml.")
        st.sidebar.info("Adicione GOOGLE_API_KEY no arquivo secrets.toml.")
        return None


def configure_gemini():
    api_key = get_api_key()
    if not api_key:
        return False
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.sidebar.error(f"Erro ao configurar Gemini: {e}")
        return False


def extract_text_from_pdf(pdf_file) -> str:
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    texto = []
    for i, page in enumerate(doc):
        page_text = page.get_text("text", sort=True).strip()
        if page_text:
            texto.append(f"\nPágina {i+1}\n{page_text}\n")
        else:
            texto.append(f"\nPágina {i+1}: (sem texto pesquisável)\n")
    return "".join(texto)


def call_gemini(prompt: str, context_text: str, model_name: str = "gemini-2.0-flash") -> str:
    """
    Envia o prompt + TODO o texto do processo ao modelo (sem limite hard-coded).
    Verifique quotas de token do modelo em uso.
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(f"{prompt}\n\nDocumentos do processo:\n{context_text}")
        return response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        logging.exception("Erro na chamada à LLM")
        return f"Erro na chamada à LLM: {e}"

# ------------------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------------------

st.title("Análise de Intimações – Modelo Teste")
st.markdown("""
Faça upload dos PDFs que compõem o processo e obtenha **três análises**:

1. **Teor da intimação**  
2. **Análise do caso + próximos passos**  
3. **Petição sugerida**  
""")

api_ready = configure_gemini()
if not api_ready:
    st.stop()

st.header("Upload de documentos")
files = st.file_uploader(
    "Arraste seus PDFs aqui",
    type="pdf",
    accept_multiple_files=True
)

# ------------------------------------------------------------------------------
# Processamento dos PDFs
# ------------------------------------------------------------------------------

if files:
    progress = st.progress(0)
    textos = []

    for idx, pdf in enumerate(files, start=1):
        with st.spinner(f"Lendo texto do PDF {idx}/{len(files)} ..."):
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp.write(pdf.read())
            temp.flush()
            temp.seek(0)

            textos.append(f"Documento {idx} – {pdf.name}\n" +
                          extract_text_from_pdf(temp))
            temp.close()
            os.unlink(temp.name)

        progress.progress(idx / len(files) * 0.50)

    corpus = "\n".join(textos)
    st.info(f"Total de palavras extraídas: **{len(corpus.split())}**")

    # ------------------------------------------------------------------------------
    # Análise com Gemini
    # ------------------------------------------------------------------------------

    prompts = {
        "Avaliação da Intimação":
            "Avalie o teor da intimação. Identifique natureza, requisitos legais, prazos e implicações.",
        "Providências Recomendadas":
            "Analise o processo e recomende ações específicas para responder adequadamente à intimação.",
        "Petição":
            "Redija a petição completa (cabeçalho, qualificação, fatos, fundamentos jurídicos, pedidos, fechamento)."
    }

    if st.button("🔎 Executar análises"):
        tabs = st.tabs(list(prompts.keys()))

        for i, (tab_name, prompt) in enumerate(prompts.items(), start=1):
            with tabs[i-1]:
                with st.spinner(f"Analisando ({tab_name}) ..."):
                    progress.progress(0.50 + i / len(prompts) * 0.45)
                    resultado = call_gemini(prompt, corpus)

                    st.markdown(resultado)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        f"💾 Download {tab_name}",
                        data=resultado,
                        file_name=f"{tab_name.lower().replace(' ', '_')}_{ts}.txt",
                        mime="text/plain"
                    )

        progress.progress(1.0)
        st.success("Todas as análises concluídas!")

        # Análise comparativa opcional
        if st.button("📊 Análise comparativa entre resultados"):
            st.subheader("Comparativo")
            comp_prompt = (
                "Compare as três análises acima, indicando convergências e divergências, "
                "avaliando se a petição responde adequadamente e sugerindo melhorias."
            )
            with st.spinner("Gerando comparação ..."):
                comparacao = call_gemini(comp_prompt, corpus)
                st.markdown(comparacao)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "💾 Download análise comparativa",
                    data=comparacao,
                    file_name=f"analise_comparativa_{ts}.txt",
                    mime="text/plain"
                )
else:
    st.info("Envie um ou mais PDFs para começar.")

