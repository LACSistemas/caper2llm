import streamlit as st
import requests
import time
import json
import pandas as pd
from datetime import datetime, date
import hashlib
from typing import List, Dict, Any, Optional
import math
from dataclasses import dataclass, field
from enum import Enum
 
# === CONFIGURAÇÃO ===
st.set_page_config(
    page_title="Automação de buscas pelo DJEN - CNJ",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

@dataclass
class ExclusionRule:
    """Sub-regra de exclusão para filtrar resultados"""
    name: str
    field: str  # campo a verificar (numeroOab, nomeParte, etc)
    value: str
    enabled: bool = True

@dataclass
class SearchRule:
    """Regra principal de busca"""
    name: str
    enabled: bool
    parameters: Dict[str, Any]
    exclusions: List[ExclusionRule] = field(default_factory=list)
    
    def __post_init__(self):
        # Remove empty parameters
        self.parameters = {k: v for k, v in self.parameters.items() 
                         if v is not None and v != "" and v != 0}

# === ESTILO CSS ===
st.markdown("""
<style>
    .publication-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
        background-color: #f9f9f9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .publication-title {
        font-size: 18px;
        font-weight: bold;
        color: #1f4e79;
        margin-bottom: 10px;
    }
    .publication-info {
        font-size: 14px;
        color: #666;
        margin-bottom: 8px;
    }
    .publication-text {
        background-color: #fff;
        padding: 15px;
        border-radius: 4px;
        border-left: 4px solid #1f4e79;
        margin: 10px 0;
        font-size: 14px;
        line-height: 1.5;
    }
    .lawyer-info {
        background-color: #e8f4f8;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
        font-size: 13px;
    }
    .search-progress {
        text-align: center;
        padding: 20px;
        background-color: #e8f4f8;
        border-radius: 8px;
        margin: 10px 0;
    }
    .rule-card {
        border: 1px solid #28a745;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #f8f9fa;
        border-left: 4px solid #28a745;
    }
    .rule-disabled {
        opacity: 0.6;
        background-color: #f8f9fa;
        border-color: #ccc;
    }
    .exclusion-rule {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 4px;
        padding: 8px;
        margin: 5px 0;
        font-size: 13px;
    }
    .exclusion-disabled {
        opacity: 0.5;
    }
    .stats-card {
        background-color: #e3f2fd;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

class OptimizedDJESearcher:
    def __init__(self):
        self.base_url = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
        
    def search_with_params(self, params: Dict[str, Any], progress_callback=None) -> List[Dict]:
        """Executa busca com parâmetros específicos"""
        publications = []
        search_params = params.copy()
        search_params.update({
            "itensPorPagina": 50,
            "pagina": 1
        })
        
        rule_name = params.get('_rule_name', 'Busca')
        
        while True:
            if progress_callback:
                progress_callback(f"Buscando {rule_name} - Página {search_params['pagina']}")
            
            try:
                response = requests.get(self.base_url, params=search_params, timeout=30)
                
                if response.status_code == 200:
                    dados = response.json()
                    items = dados.get("items", [])
                    
                    if not items:
                        break
                    
                    publications.extend(items)
                    search_params["pagina"] += 1
                    time.sleep(0.5)  # Rate limiting
                    
                elif response.status_code == 429:
                    if progress_callback:
                        progress_callback("Rate limit atingido. Aguardando...")
                    time.sleep(10)
                else:
                    st.error(f"Erro na busca {rule_name}: {response.status_code}")
                    break
                    
            except Exception as e:
                st.error(f"Erro na requisição {rule_name}: {str(e)}")
                break
                
        return publications
    
    def apply_exclusions(self, publications: List[Dict], exclusions: List[ExclusionRule]) -> tuple[List[Dict], Dict[str, int]]:
        """Aplica as exclusões aos resultados e retorna estatísticas"""
        if not exclusions:
            return publications, {}
        
        excluded_count = {}
        filtered_publications = []
        
        for pub in publications:
            should_exclude = False
            
            for exclusion in exclusions:
                if not exclusion.enabled:
                    continue
                
                # Verifica o campo específico para exclusão
                if exclusion.field == 'numeroOab':
                    # Procura nos advogados
                    advogados = pub.get('destinatarioadvogados', [])
                    for adv_info in advogados:
                        adv = adv_info.get('advogado', {})
                        if str(adv.get('numero_oab', '')).strip() == str(exclusion.value).strip():
                            should_exclude = True
                            excluded_count[exclusion.name] = excluded_count.get(exclusion.name, 0) + 1
                            break
                
                elif exclusion.field == 'nomeParte':
                    # Procura nos destinatários
                    destinatarios = pub.get('destinatarios', [])
                    for dest in destinatarios:
                        if exclusion.value.lower() in dest.get('nome', '').lower():
                            should_exclude = True
                            excluded_count[exclusion.name] = excluded_count.get(exclusion.name, 0) + 1
                            break
                
                elif exclusion.field == 'numeroProcesso':
                    if exclusion.value in pub.get('numeroprocessocommascara', ''):
                        should_exclude = True
                        excluded_count[exclusion.name] = excluded_count.get(exclusion.name, 0) + 1
                
                elif exclusion.field == 'nomeAdvogado':
                    advogados = pub.get('destinatarioadvogados', [])
                    for adv_info in advogados:
                        adv = adv_info.get('advogado', {})
                        if exclusion.value.lower() in adv.get('nome', '').lower():
                            should_exclude = True
                            excluded_count[exclusion.name] = excluded_count.get(exclusion.name, 0) + 1
                            break
                
                if should_exclude:
                    break
            
            if not should_exclude:
                filtered_publications.append(pub)
        
        return filtered_publications, excluded_count
    
    def execute_rules(self, rules: List[SearchRule], progress_callback=None) -> tuple[List[Dict], Dict[str, Any]]:
        """Executa todas as regras e retorna resultados com estatísticas"""
        all_publications = []
        stats = {
            'rules_executed': 0,
            'total_found': 0,
            'total_excluded': 0,
            'exclusion_details': {},
            'rule_counts': {}
        }
        
        # Executa cada regra de busca
        for rule in rules:
            if not rule.enabled:
                continue
            
            stats['rules_executed'] += 1
            
            if progress_callback:
                progress_callback(f"Executando regra: {rule.name}")
            
            # Adiciona identificador da regra nos parâmetros
            rule_params = rule.parameters.copy()
            rule_params['_rule_name'] = rule.name
            
            # Busca publicações
            publications = self.search_with_params(rule_params, progress_callback)
            stats['rule_counts'][rule.name] = len(publications)
            
            # Aplica exclusões específicas da regra
            if rule.exclusions:
                if progress_callback:
                    progress_callback(f"Aplicando exclusões para: {rule.name}")
                
                publications, exclusion_counts = self.apply_exclusions(publications, rule.exclusions)
                
                for exc_name, count in exclusion_counts.items():
                    stats['exclusion_details'][f"{rule.name} - {exc_name}"] = count
                    stats['total_excluded'] += count
            
            # Adiciona metadados às publicações
            for pub in publications:
                pub['_source_rule'] = rule.name
            
            all_publications.extend(publications)
        
        # Remove duplicatas
        if progress_callback:
            progress_callback("Removendo duplicatas...")
        
        unique_publications = self.remove_duplicates(all_publications)
        stats['total_found'] = len(unique_publications)
        stats['duplicates_removed'] = len(all_publications) - len(unique_publications)
        
        return unique_publications, stats
    
    def remove_duplicates(self, publications: List[Dict]) -> List[Dict]:
        """Remove duplicatas baseado no hash da publicação"""
        seen_hashes = set()
        unique_publications = []
        
        for pub in publications:
            pub_hash = pub.get('hash')
            if pub_hash and pub_hash not in seen_hashes:
                seen_hashes.add(pub_hash)
                unique_publications.append(pub)
            elif not pub_hash:
                # Para publicações sem hash, usar outros campos
                unique_id = f"{pub.get('id', '')}_{pub.get('numeroprocessocommascara', '')}"
                if unique_id not in seen_hashes:
                    seen_hashes.add(unique_id)
                    unique_publications.append(pub)
        
        return unique_publications

def create_rule_form(rule_index: int, existing_rule: Optional[SearchRule] = None) -> Optional[SearchRule]:
    """Cria formulário para configurar uma regra com sub-regras de exclusão"""
    prefix = f"rule_{rule_index}"
    
    with st.expander(f"📋 Regra {rule_index + 1}" + (f" - {existing_rule.name}" if existing_rule else ""), 
                     expanded=not existing_rule):
        
        # Informações básicas da regra
        col1, col2 = st.columns([3, 1])
        
        with col1:
            rule_name = st.text_input(
                "Nome da Regra", 
                value=existing_rule.name if existing_rule else f"Regra {rule_index + 1}",
                key=f"{prefix}_name"
            )
        
        with col2:
            rule_enabled = st.checkbox(
                "Regra Ativa",
                value=existing_rule.enabled if existing_rule else True,
                key=f"{prefix}_enabled"
            )
        
        st.markdown("### 🔍 Parâmetros de Busca")
        
        # Parâmetros organizados em abas
        tab1, tab2, tab3, tab4 = st.tabs(["👨‍💼 Advogado", "👥 Parte/Processo", "🏛️ Tribunal", "📅 Período"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                numero_oab = st.text_input(
                    "Número da OAB",
                    value=existing_rule.parameters.get('numeroOab', '') if existing_rule else '',
                    key=f"{prefix}_numero_oab"
                )
            
            with col2:
                uf_options = [""] + ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", 
                                   "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", 
                                   "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
                uf_default = 0
                if existing_rule and existing_rule.parameters.get('ufOab'):
                    try:
                        uf_default = uf_options.index(existing_rule.parameters.get('ufOab'))
                    except ValueError:
                        uf_default = 0
                
                uf_oab = st.selectbox(
                    "UF da OAB",
                    options=uf_options,
                    index=uf_default,
                    key=f"{prefix}_uf_oab"
                )
            
            nome_advogado = st.text_input(
                "Nome do Advogado",
                value=existing_rule.parameters.get('nomeAdvogado', '') if existing_rule else '',
                key=f"{prefix}_nome_advogado"
            )
        
        with tab2:
            nome_parte = st.text_input(
                "Nome da Parte",
                value=existing_rule.parameters.get('nomeParte', '') if existing_rule else '',
                key=f"{prefix}_nome_parte"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                numero_processo = st.text_input(
                    "Número do Processo",
                    value=existing_rule.parameters.get('numeroProcesso', '') if existing_rule else '',
                    key=f"{prefix}_numero_processo"
                )
            
            with col2:
                numero_comunicacao = st.number_input(
                    "Número da Comunicação",
                    min_value=0,
                    value=existing_rule.parameters.get('numeroComunicacao', 0) if existing_rule else 0,
                    key=f"{prefix}_numero_comunicacao"
                )
        
        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                sigla_tribunal = st.text_input(
                    "Sigla do Tribunal",
                    value=existing_rule.parameters.get('siglaTribunal', '') if existing_rule else '',
                    key=f"{prefix}_sigla_tribunal"
                )
            
            with col2:
                orgao_id = st.number_input(
                    "ID do Órgão",
                    min_value=0,
                    value=existing_rule.parameters.get('orgaoId', 0) if existing_rule else 0,
                    key=f"{prefix}_orgao_id"
                )
        
        with tab4:
            col1, col2 = st.columns(2)
            
            with col1:
                default_start_date = date.today()
                if existing_rule and existing_rule.parameters.get('dataDisponibilizacaoInicio'):
                    try:
                        default_start_date = datetime.strptime(
                            existing_rule.parameters.get('dataDisponibilizacaoInicio'), 
                            '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        pass
                
                data_inicio = st.date_input(
                    "Data de Início",
                    value=default_start_date,
                    key=f"{prefix}_data_inicio"
                )
            
            with col2:
                default_end_date = None
                if existing_rule and existing_rule.parameters.get('dataDisponibilizacaoFim'):
                    try:
                        default_end_date = datetime.strptime(
                            existing_rule.parameters.get('dataDisponibilizacaoFim'), 
                            '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        pass
                
                data_fim = st.date_input(
                    "Data de Fim",
                    value=default_end_date,
                    key=f"{prefix}_data_fim"
                )
        
        # Sub-regras de exclusão
        st.markdown("### 🚫 Exclusões (filtros pós-busca)")
        st.info("As exclusões são aplicadas após a busca para filtrar resultados indesejados")
        
        # Gerenciar exclusões existentes
        exclusions = []
        if existing_rule and existing_rule.exclusions:
            for exc_idx, exc in enumerate(existing_rule.exclusions):
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    exc_name = st.text_input(
                        "Nome",
                        value=exc.name,
                        key=f"{prefix}_exc_{exc_idx}_name"
                    )
                
                with col2:
                    field_options = ["numeroOab", "nomeParte", "numeroProcesso", "nomeAdvogado"]
                    field_idx = field_options.index(exc.field) if exc.field in field_options else 0
                    exc_field = st.selectbox(
                        "Campo",
                        options=field_options,
                        index=field_idx,
                        key=f"{prefix}_exc_{exc_idx}_field"
                    )
                
                with col3:
                    exc_value = st.text_input(
                        "Valor",
                        value=exc.value,
                        key=f"{prefix}_exc_{exc_idx}_value"
                    )
                
                with col4:
                    exc_enabled = st.checkbox(
                        "Ativa",
                        value=exc.enabled,
                        key=f"{prefix}_exc_{exc_idx}_enabled"
                    )
                
                if exc_name and exc_value:
                    exclusions.append(ExclusionRule(
                        name=exc_name,
                        field=exc_field,
                        value=exc_value,
                        enabled=exc_enabled
                    ))
        
        # Adicionar nova exclusão
        if st.button("➕ Adicionar Exclusão", key=f"{prefix}_add_exclusion"):
            st.session_state[f"{prefix}_new_exclusion"] = True
            st.rerun()
        
        if st.session_state.get(f"{prefix}_new_exclusion", False):
            st.markdown("**Nova Exclusão:**")
            col1, col2, col3 = st.columns([3, 2, 2])
            
            with col1:
                new_exc_name = st.text_input(
                    "Nome da Exclusão",
                    key=f"{prefix}_new_exc_name"
                )
            
            with col2:
                new_exc_field = st.selectbox(
                    "Campo a Filtrar",
                    options=["numeroOab", "nomeParte", "numeroProcesso", "nomeAdvogado"],
                    key=f"{prefix}_new_exc_field"
                )
            
            with col3:
                new_exc_value = st.text_input(
                    "Valor a Excluir",
                    key=f"{prefix}_new_exc_value"
                )
            
            if new_exc_name and new_exc_value:
                exclusions.append(ExclusionRule(
                    name=new_exc_name,
                    field=new_exc_field,
                    value=new_exc_value,
                    enabled=True
                ))
                st.session_state[f"{prefix}_new_exclusion"] = False
        
        # Cria parâmetros
        parameters = {}
        
        if numero_oab:
            parameters['numeroOab'] = numero_oab
        if uf_oab:
            parameters['ufOab'] = uf_oab
        if nome_advogado:
            parameters['nomeAdvogado'] = nome_advogado
        if nome_parte:
            parameters['nomeParte'] = nome_parte
        if numero_processo:
            parameters['numeroProcesso'] = numero_processo
        if numero_comunicacao > 0:
            parameters['numeroComunicacao'] = numero_comunicacao
        if sigla_tribunal:
            parameters['siglaTribunal'] = sigla_tribunal
        if orgao_id > 0:
            parameters['orgaoId'] = orgao_id
        if data_inicio:
            parameters['dataDisponibilizacaoInicio'] = data_inicio.strftime('%Y-%m-%d')
        if data_fim:
            parameters['dataDisponibilizacaoFim'] = data_fim.strftime('%Y-%m-%d')
        
        if parameters:
            return SearchRule(
                name=rule_name,
                enabled=rule_enabled,
                parameters=parameters,
                exclusions=exclusions
            )
        
        return None

def display_publication_card(pub: Dict, index: int):
    """Exibe uma publicação como card"""
    with st.container():
        st.markdown(f"""
        <div class="publication-card">
            <div class="publication-title">
                {pub.get('tipoComunicacao', 'N/A')} - {pub.get('siglaTribunal', 'N/A')}
                <span style="float: right; font-size: 12px; color: #999;">
                    Fonte: {pub.get('_source_rule', 'N/A')}
                </span>
            </div>
            <div class="publication-info">
                📅 <strong>Data:</strong> {pub.get('datadisponibilizacao', 'N/A')} | 
                🏛️ <strong>Órgão:</strong> {pub.get('nomeOrgao', 'N/A')}
            </div>
            <div class="publication-info">
                📋 <strong>Processo:</strong> {pub.get('numeroprocessocommascara', 'N/A')} | 
                📝 <strong>Classe:</strong> {pub.get('nomeClasse', 'N/A')}
            </div>
        """, unsafe_allow_html=True)
        
        # Texto da publicação
        texto = pub.get('texto', 'Texto não disponível')
        if len(texto) > 500:
            with st.expander("📄 Ver texto completo"):
                st.markdown(f'<div class="publication-text">{texto}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="publication-text">{texto}</div>', unsafe_allow_html=True)
        
        # Destinatários
        destinatarios = pub.get('destinatarios', [])
        if destinatarios:
            st.markdown("**👥 Destinatários:**")
            for dest in destinatarios:
                st.markdown(f"- {dest.get('nome', 'N/A')} ({dest.get('polo', 'N/A')})")
        
        # Advogados
        advogados = pub.get('destinatarioadvogados', [])
        if advogados:
            st.markdown("**⚖️ Advogados:**")
            for adv_info in advogados:
                adv = adv_info.get('advogado', {})
                st.markdown(f"""
                <div class="lawyer-info">
                    <strong>{adv.get('nome', 'N/A')}</strong><br>
                    OAB: {adv.get('numero_oab', 'N/A')}/{adv.get('uf_oab', 'N/A')}
                </div>
                """, unsafe_allow_html=True)
        
        # Link para o processo
        link = pub.get('link', '')
        if link:
            st.markdown(f"[🔗 Acessar processo]({link})")
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

def main():
    st.title("⚖️ Automação de Buscas pelo DJEN - CNJ")
    st.markdown("Sistema otimizado com sub-regras de exclusão para filtrar resultados indesejados")
    
    # Inicializa session state
    if 'rules' not in st.session_state:
        st.session_state.rules = []
    if 'template_loaded' not in st.session_state:
        st.session_state.template_loaded = False
    
    # Sidebar para configuração
    with st.sidebar:
        st.header("🔧 Configuração")
        
        # Botões para gerenciar regras
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Nova Regra"):
                st.session_state.rules.append(None)
                st.rerun()
        
        with col2:
            if st.button("🗑️ Limpar Tudo"):
                st.session_state.rules = []
                st.session_state.template_loaded = False
                st.rerun()
        
        # Templates
        st.markdown("### 📋 Templates")
        if st.button("📋 Carregar Template Exemplo"):
            st.session_state.rules = []
            
            # Template com sub-regras de exclusão
            default_rules = [
                SearchRule(
                    name="Sinales",
                    enabled=True,
                    parameters={
                        'nomeParte': 'Sinales',
                        'dataDisponibilizacaoInicio': date.today().strftime('%Y-%m-%d')
                    },
                    exclusions=[
                        ExclusionRule(
                            name="Excluir Itiel",
                            field="numeroOab",
                            value="14072",
                            enabled=True
                        )
                    ]
                ),
                SearchRule(
                    name="Darwin",
                    enabled=True,
                    parameters={
                        'nomeParte': 'Darwin',
                        'dataDisponibilizacaoInicio': date.today().strftime('%Y-%m-%d')
                    },
                    exclusions=[
                        ExclusionRule(
                            name="Excluir Itiel",
                            field="numeroOab",
                            value="14072",
                            enabled=True
                        )
                    ]
                ),
                SearchRule(
                    name="OAB Principal",
                    enabled=True,
                    parameters={
                        'numeroOab': '8773',
                        'ufOab': 'ES',
                        'dataDisponibilizacaoInicio': date.today().strftime('%Y-%m-%d')
                    },
                    exclusions=[]
                ),
                SearchRule(
                    name="Multivix",
                    enabled=True,
                    parameters={
                        'nomeParte': 'Multivix',
                        'dataDisponibilizacaoInicio': date.today().strftime('%Y-%m-%d')
                    },
                    exclusions=[
                        ExclusionRule(
                            name="Excluir Itiel",
                            field="numeroOab",
                            value="14072",
                            enabled=True
                        ),
                        ExclusionRule(
                            name="Excluir processos antigos",
                            field="numeroProcesso",
                            value="0001234",
                            enabled=False
                        )
                    ]
                )
            ]
            
            st.session_state.rules = default_rules
            st.session_state.template_loaded = True
            st.success("Template carregado com sucesso!")
            st.rerun()
        
        # Ajuda
        with st.expander("❓ Como funciona"):
            st.markdown("""
            ### 🎯 Sistema Otimizado
            
            1. **Regras de Busca**: Definem os critérios principais
            2. **Sub-regras de Exclusão**: Filtram resultados indesejados
            
            ### ⚡ Vantagens:
            - Muito mais rápido (sem buscas desnecessárias)
            - Exclusões aplicadas como filtros pós-busca
            - Estatísticas detalhadas
            - Interface mais intuitiva
            
            ### 💡 Exemplo:
            - Buscar: "Sinales" 
            - Excluir: OAB "14072"
            
            Isso busca APENAS por Sinales e depois remove os que têm OAB 14072.
            """)
    
    # Área principal
    st.markdown("## ⚙️ Configuração de Regras")
    
    # Formulários de regras
    configured_rules = []
    for i in range(len(st.session_state.rules)):
        existing_rule = st.session_state.rules[i]
        rule = create_rule_form(i, existing_rule)
        if rule:
            configured_rules.append(rule)
    
    # Atualiza regras no session state
    if not st.session_state.template_loaded:
        st.session_state.rules = configured_rules
    else:
        st.session_state.template_loaded = False
    
    # Exibe botão de busca se houver regras configuradas
    if configured_rules:
        # Botão de busca
        if st.button("🔍 Executar Busca", type="primary", use_container_width=True):
            searcher = OptimizedDJESearcher()
            
            # Progress bar e status
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message):
                status_text.markdown(f'<div class="search-progress">🔍 {message}</div>', 
                                   unsafe_allow_html=True)
            
            try:
                # Executa as regras
                publications, stats = searcher.execute_rules(configured_rules, update_progress)
                
                progress_bar.progress(100)
                status_text.success(f"✅ Busca concluída! {len(publications)} publicações encontradas.")
                
                # Armazena os resultados
                st.session_state.publications = publications
                st.session_state.search_stats = stats
                st.session_state.search_completed = True
                
            except Exception as e:
                st.error(f"Erro durante a busca: {str(e)}")
                return
    
    # Exibe os resultados
    if hasattr(st.session_state, 'publications') and st.session_state.publications:
        publications = st.session_state.publications
        
        # Filtros
        st.markdown("## 🔍 Filtros dos Resultados")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            tribunais = sorted(list(set([pub.get('siglaTribunal', 'N/A') 
                                       for pub in publications])))
            tribunal_filter = st.selectbox("Tribunal", ["Todos"] + tribunais)
        
        with col2:
            tipos = sorted(list(set([pub.get('tipoComunicacao', 'N/A') 
                                   for pub in publications])))
            tipo_filter = st.selectbox("Tipo de Comunicação", ["Todos"] + tipos)
        
        with col3:
            classes = sorted(list(set([pub.get('nomeClasse', 'N/A') 
                                     for pub in publications])))
            classe_filter = st.selectbox("Classe Processual", ["Todos"] + classes)
        
        with col4:
            source_rules = sorted(list(set([pub.get('_source_rule', 'N/A') 
                                          for pub in publications])))
            source_filter = st.selectbox("Regra de Origem", ["Todos"] + source_rules)
        
        # Aplicar filtros
        filtered_publications = publications
        if tribunal_filter != "Todos":
            filtered_publications = [pub for pub in filtered_publications 
                                   if pub.get('siglaTribunal') == tribunal_filter]
        if tipo_filter != "Todos":
            filtered_publications = [pub for pub in filtered_publications 
                                   if pub.get('tipoComunicacao') == tipo_filter]
        if classe_filter != "Todos":
            filtered_publications = [pub for pub in filtered_publications 
                                   if pub.get('nomeClasse') == classe_filter]
        if source_filter != "Todos":
            filtered_publications = [pub for pub in filtered_publications 
                                   if pub.get('_source_rule') == source_filter]
        
        # Paginação
        st.markdown("## 📋 Resultados")
        items_per_page = 10
        total_items = len(filtered_publications)
        total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
        
        if total_pages > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                page = st.selectbox("Página", range(1, total_pages + 1))
        else:
            page = 1
        
        # Exibe informações da paginação
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        current_items = filtered_publications[start_idx:end_idx]
        
        st.info(f"Mostrando {len(current_items)} de {total_items} publicações "
                f"(Página {page} de {total_pages})")
        
        # Exibe as publicações
        for i, pub in enumerate(current_items):
            display_publication_card(pub, start_idx + i)
        
        # Exportar resultados
        st.markdown("## 📊 Exportar Resultados")
        if st.button("📋 Exportar como JSON"):
            json_data = json.dumps(filtered_publications, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Baixar JSON",
                data=json_data,
                file_name=f"dje_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    elif hasattr(st.session_state, 'search_completed') and st.session_state.search_completed:
        st.info("Nenhuma publicação encontrada com os critérios especificados.")
    
    else:
        st.info("Configure as regras acima e clique em 'Executar Busca' para começar.")
        
        # Exemplo visual
        st.markdown("### 📚 Exemplo de Uso")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Método Antigo (lento):**
            1. Buscar TODAS publicações de Sinales ⏳
            2. Buscar TODAS publicações do OAB 14072 ⏳
            3. Comparar e remover intersecções 🐌
            
            Total: 2 buscas completas + processamento
            """)
        
        with col2:
            st.markdown("""
            **Método Novo (rápido):**
            1. Buscar publicações de Sinales ✅
            2. Filtrar OAB 14072 dos resultados ⚡
            
            Total: 1 busca + filtro rápido
            """)

if __name__ == "__main__":
    main()
