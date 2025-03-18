import streamlit as st
import os
import tempfile
import google.generativeai as genai
from google.cloud import vision
import io
from datetime import datetime
import logging
import fitz  # PyMuPDF for PDF handling
import json
import requests

# Set up logging
logging.basicConfig(level=logging.INFO)

# Set page config
st.set_page_config(page_title="Legal Case Analyzer", layout="wide")

# Get API key from secrets
def get_api_key():
    try:
        # Try to get from Streamlit secrets
        return st.secrets["GOOGLE_API_KEY"]
    except Exception as e:
        st.error("API key not found in secrets.")
        st.info("Please set up your secrets.toml file with GOOGLE_API_KEY.")
        return None

# Function to configure the Gemini API with API key
def configure_gemini_with_api_key():
    api_key = get_api_key()
    if not api_key:
        return False
   
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.error(f"Error configuring Gemini API: {str(e)}")
        st.info("Please check if the API key is valid and has access to the Generative AI API.")
        return False

# Streamlit app title and description
st.title("Análise de Intimações - Modelo Teste")
st.markdown("""
Modelo utilizando ferramentas com parametrização limitada para determinar o ajuste fino da LLM.
Faça upload dos PDFs a qual o caso pertence e obterá 3 Análises:
1. O Teor da Intimação
2. Análise do Caso e Recomendação dos Próximos Passos
3. Preparação da Petição
""")

# Configure API and display status
api_configured = configure_gemini_with_api_key()
if api_configured:
    st.sidebar.success("API configurada com sucesso!")
else:
    st.sidebar.error("Falha na configuração da API. Verifique as configurações de secrets.")

# Function to extract text from PDF using Google Vision API with API key
def extract_text_with_vision(pdf_file):
    api_key = get_api_key()
    if not api_key:
        return "API key not configured correctly."
   
    # Define the Vision API endpoint
    vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
   
    # Convert PDF to images and extract text
    text = ""
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
   
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        # Render page as image
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        img_bytes = pix.tobytes("png")
       
        # Encode image to base64
        import base64
        encoded_image = base64.b64encode(img_bytes).decode('UTF-8')
       
        # Prepare request payload
        request_data = {
            "requests": [
                {
                    "image": {
                        "content": encoded_image
                    },
                    "features": [
                        {
                            "type": "TEXT_DETECTION"
                        }
                    ]
                }
            ]
        }
       
        # Make API request
        response = requests.post(vision_url, json=request_data)
       
        if response.status_code == 200:
            response_data = response.json()
           
            # Extract text from annotations
            if (response_data.get('responses') and
                response_data['responses'][0].get('textAnnotations') and
                len(response_data['responses'][0]['textAnnotations']) > 0):
               
                page_text = response_data['responses'][0]['textAnnotations'][0]['description']
                text += f"\nPágina {page_num + 1}:\n{page_text}\n"
            else:
                text += f"\nPágina {page_num + 1}: Nenhum texto detectado\n"
        else:
            raise Exception(f"Error in OCR: {response.status_code} - {response.text}")
   
    return text

# Function to safely extract text from Gemini API response
def analyze_with_gemini(combined_text, prompt, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            f"{prompt}\n\nDocumentos do processo:\n{combined_text[:100000]}"
        )
       
        try:
            if hasattr(response, "candidates") and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
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
   
    # Extract text from all PDFs using Google Vision
    all_text = []
    try:
        for i, file in enumerate(uploaded_files):
            with st.spinner(f"Extraindo texto do documento {i+1}/{len(uploaded_files)} usando Extração e OCR para partes necessárias..."):
                # Create a temporary copy of the file for processing
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file.read())
                    file.seek(0)  # Reset file pointer
                    temp_file_path = temp_file.name
               
                # Process with Google Vision
                with open(temp_file_path, "rb") as pdf_file:
                    text = extract_text_with_vision(pdf_file)
               
                # Remove temporary file
                os.unlink(temp_file_path)
               
                all_text.append(f"Documento {i+1} ({file.name}):\n{text}\n\n")
                progress_bar.progress((i + 1) / len(uploaded_files) * 0.5)
       
        combined_text = "\n".join(all_text)
       
        # Display word count
        word_count = len(combined_text.split())
        st.write(f"Total de palavras extraídas: {word_count}")
   
    except Exception as e:
        st.error(f"Erro ao extrair texto dos PDFs: {str(e)}")
        st.stop()
   
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
    st.error("A API da IA não está configurada corretamente. Verifique as configurações de secrets.")
elif not uploaded_files:
    st.info("Aguardando upload dos documentos PDF.")

