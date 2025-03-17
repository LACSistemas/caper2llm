import streamlit as st
import os
import tempfile
import google.generativeai as genai
from PyPDF2 import PdfReader
import io
from datetime import datetime
from google.oauth2 import service_account
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Set page config
st.set_page_config(page_title="Legal Case Analyzer", layout="wide")

# Fixed service account configuration
SERVICE_ACCOUNT_FILE = "lawyerllmcase_credentials.json"  # Path to your service account JSON file

# Function to get credentials
@st.cache_resource
def get_credentials():
    try:
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        return credentials
    except Exception as e:
        st.sidebar.error(f"Error loading service account: {str(e)}")
        st.sidebar.info("Please ensure the service account JSON file is in the correct location.")
        return None

# Function to configure the Gemini API with service account
def configure_gemini_with_service_account():
    credentials = get_credentials()
    if credentials:
        try:
            genai.configure(credentials=credentials)
            return True
        except Exception as e:
            st.sidebar.error(f"Error configuring Gemini API: {str(e)}")
            return False
    return False

# Configure Gemini API with service account
api_configured = configure_gemini_with_service_account()

# Streamlit app title and description
st.title("Análise de Intimações - Modelo Teste")
st.markdown("""
Modelo utilizando ferramentas com parametrização limitada para determinar o ajuste fino da LLM.
Faça upload dos PDFs a qual o caso pertence e obterá 3 Análises:
1. O Teor da Intimação
2. Análise do Caso e Recomendação dos Próximos Passos
3. Preparação da Petição
""")

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to safely extract text from Gemini API response
def analyze_with_gemini(combined_text, prompt, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            f"{prompt}\n\nDocumentos do processo:\n{combined_text[:100000]}"
        )
        
        # From the test script output, we can see the proper structure:
        # response -> candidates[0] -> content -> parts[0] -> text
        try:
            if hasattr(response, "candidates") and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
                        # Here's the important part - parts is a RepeatedCompositeContainer
                        # and we need to access it as an indexable collection, not as a single object
                        parts = content.parts
                        if len(parts) > 0:
                            return parts[0].text
            
            # Fallback to string representation
            return str(response)
            
        except Exception as e:
            logging.error(f"Error extracting text: {str(e)}")
            # Extract text from string representation as a last resort
            try:
                response_str = str(response)
                # Find the text field in string representation
                if '"text":' in response_str:
                    start = response_str.find('"text":') + 8  # length of '"text": "'
                    end = response_str.find('"', start)
                    return response_str[start:end]
            except:
                pass
            
            return f"Error extracting response text: {str(e)}"
    
    except Exception as e:
        logging.error(f"Error with AI API: {str(e)}")
        return f"Error with AI API: {str(e)}"
    
# Main content
st.header("Upload de Documentos")
uploaded_files = st.file_uploader("Faça upload dos PDFs do processo", accept_multiple_files=True, type="pdf")

if uploaded_files and api_configured:
    # Set selected_model_full here to ensure it's defined
    selected_model_full = "gemini-2.0-flash"
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    # Display uploaded files
    st.subheader("Documentos Carregados:")
    for i, file in enumerate(uploaded_files):
        st.write(f"{i+1}. {file.name}")
    
    # Extract text from all PDFs
    all_text = []
    for i, file in enumerate(uploaded_files):
        text = extract_text_from_pdf(file)
        all_text.append(f"Documento {i+1} ({file.name}):\n{text}\n\n")
        progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)
    
    combined_text = "\n".join(all_text)
    
    # Display word count
    word_count = len(combined_text.split())
    st.write(f"Total de palavras extraídas: {word_count}")
    
    # Analysis button
    if st.button("Analisar Documentos"):
        st.header("Resultados da Análise")
        
        # Define the prompts
        prompts = [
            "Avalie o teor da intimação nos documentos fornecidos. Identifique a natureza da intimação, seus requisitos legais, prazos e possíveis implicações.",
            "Analise os documentos do processo, e verifique qual providencia deve ser tomada. Forneça uma análise detalhada da situação jurídica atual, recomendando ações específicas para responder à intimação de forma adequada.",
            "Prepare uma petição que atenda a intimação. A petição deve incluir todos os elementos necessários, como cabeçalho, qualificação das partes, introdução, exposição dos fatos, fundamentos jurídicos, pedidos e fechamento."
        ]
        
        # Create tabs for each analysis
        tabs = st.tabs(["Avaliação da Intimação", "Análise de Providências", "Preparação de Petição"])
        
        # Process each prompt
        for i, (tab, prompt) in enumerate(zip(tabs, prompts)):
            with tab:
                with st.spinner(f"Realizando análise {i+1}/3..."):
                    # Update progress bar
                    progress_bar.progress(0.5 + (i + 1) / len(prompts) * 0.5)
                    
                    # Get analysis from Gemini
                    response = analyze_with_gemini(combined_text, prompt, selected_model_full)
                    
                    # Display results
                    st.markdown(response)
                    
                    # Add download button for the analysis
                    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    analysis_filename = f"analise_{i+1}_{current_time}.txt"
                    
                    st.download_button(
                        label=f"Download da Análise {i+1}",
                        data=response,
                        file_name=analysis_filename,
                        mime="text/plain"
                    )
        
        # Complete progress bar
        progress_bar.progress(1.0)
        st.success("Análise completa!")
        
        # Add a section for analyzing the relation between analyses
        st.header("Análise Comparativa")
        if st.button("Comparar Resultados"):
            comparison_prompt = """
            Analise as três respostas anteriores e forneça uma análise comparativa:
            1. Identifique as principais convergências e divergências entre as análises
            2. Verifique se a petição proposta responde adequadamente à intimação e às providências identificadas
            3. Sugira melhorias ou pontos adicionais a serem considerados
            """
            
            with st.spinner("Realizando análise comparativa..."):
                # First get all three analyses
                analyses = []
                for prompt in prompts:
                    analysis = analyze_with_gemini(combined_text, prompt, selected_model_full)
                    analyses.append(analysis)
                
                # Then analyze the relationship between them
                full_prompt = f"{comparison_prompt}\n\n1. Avaliação da Intimação:\n{analyses[0]}\n\n2. Análise de Providências:\n{analyses[1]}\n\n3. Preparação de Petição:\n{analyses[2]}"
                comparison_analysis = analyze_with_gemini("", full_prompt, selected_model_full)
                
                st.markdown(comparison_analysis)
                
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="Download da Análise Comparativa",
                    data=comparison_analysis,
                    file_name=f"analise_comparativa_{current_time}.txt",
                    mime="text/plain"
                )
elif not api_configured:
    st.warning("A API da IA não está configurada. Verifique a configuração da conta de serviço.")
elif not uploaded_files:
    st.info("Aguardando upload dos documentos PDF.")
