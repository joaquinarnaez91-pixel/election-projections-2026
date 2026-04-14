import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import numpy as np

# Page configuration
st.set_page_config(
    page_title="ONPE 2026 - Proyección Electoral",
    page_icon="🗳️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'election_data' not in st.session_state:
    st.session_state.election_data = None

# ONPE API Configuration
BASE_URL = "https://resultadoelectoral.onpe.gob.pe/api"

def fetch_onpe_data():
    """Fetch election data from ONPE API"""
    try:
        response = requests.get(
            f"{BASE_URL}/totales",
            params={'idEleccion': 15},  # Updated election ID
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success', True):  # Handle different response formats
                return data.get('data', data.get('r', []))
        
        return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def calculate_projections(candidates_df):
    """Simple projection model for Lima vs Provinces"""
    
    # Regional completion estimates
    lima_completion = 0.89
    province_completion = 0.45
    
    # Population weights
    lima_weight = 0.32
    province_weight = 0.68
    
    projections = []
    
    for _, row in candidates_df.iterrows():
        candidate_name = row['candidate_name']
        current_votes = row['current_votes']
        
        # Estimate urban/rural strength (simplified heuristic)
        urban_strength = 0.5  # Default neutral
        
        if any(term in candidate_name.upper() for term in ['LOPEZ ALIAGA', 'RENOVACION']):
            urban_strength = 0.75  # Strong in Lima
        elif any(term in candidate_name.upper() for term in ['SANCHEZ', 'POPULAR']):
            urban_strength = 0.35  # Strong in provinces
        
        # Calculate remaining votes
        lima_remaining = (1 - lima_completion) * lima_weight
        province_remaining = (1 - province_completion) * province_weight
        
        # Estimate total votes when 100% counted
        current_national_completion = 0.65  # Estimated overall completion
        estimated_total_votes = current_votes / current_national_completion
        
        # Project additional votes
        additional_votes = (
            urban_strength * lima_remaining * estimated_total_votes +
            (1 - urban_strength) * province_remaining * estimated_total_votes
        )
        
        projected_total = current_votes + additional_votes
        
        projections.append({
            'candidate': candidate_name,
            'current_votes': current_votes,
            'projected_votes': projected_total,
            'urban_strength': urban_strength,
            'additional_votes': additional_votes
        })
    
    return projections

def create_dashboard():
    """Create the main dashboard"""
    
    # Header
    st.markdown('<div class="main-header">🗳️ ONPE 2026 - Proyección Electoral</div>', unsafe_allow_html=True)
    
    current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f"**Última actualización:** {current_time}")
    
    # Fetch data
    with st.spinner('Obteniendo datos de ONPE...'):
        data = fetch_onpe_data()
    
    if not data:
        st.error("❌ No se pudieron obtener datos de ONPE")
        st.info("Esto puede deberse a que la API está temporalmente no disponible o el ID de elección ha cambiado.")
        return
    
    # Process data
    candidates = []
    
    # Handle different API response formats
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                candidates.append({
                    'candidate_name': item.get('nombreAgrupacionPolitica', item.get('name', 'Unknown')),
                    'current_votes': int(item.get('totalVotosValidos', item.get('votes', 0))),
                    'percentage': float(item.get('porcentajeVotosValidos', item.get('percentage', 0)))
                })
    
    if not candidates:
        st.error("❌ No se encontraron datos de candidatos")
        return
    
    # Convert to DataFrame and get top 5
    df = pd.DataFrame(candidates)
    df = df.sort_values('current_votes', ascending=False).head(5)
    
    # Calculate projections
    projections = calculate_projections(df)
    proj_df = pd.DataFrame(projections)
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Progreso Estimado", "65%")
    with col2:
        st.metric("🏙️ Lima", "89%")
    with col3:
        st.metric("🌾 Provincias", "45%")
    with col4:
        total_votes = df['current_votes'].sum()
        st.metric("🗳️ Votos Contados", f"{total_votes:,}")
    
    st.markdown("---")
    
    # Main results table
    st.subheader("📊 Top 5 Candidatos - Proyección vs Actual")
    
    # Prepare display dataframe
    display_data = []
    total_projected = proj_df['projected_votes'].sum()
    
    for _, row in proj_df.iterrows():
        current_pct = (row['current_votes'] / df['current_votes'].sum()) * 100
        projected_pct = (row['projected_votes'] / total_projected) * 100
        change = projected_pct - current_pct
        
        display_data.append({
            'Candidato': row['candidate'][:30],
            'Votos Actuales': f"{row['current_votes']:,}",
            '% Actual': f"{current_pct:.2f}%",
            'Votos Proyectados': f"{int(row['projected_votes']):,}",
            '% Proyectado': f"{projected_pct:.2f}%",
            'Cambio': f"{change:+.2f}%",
            'Fortaleza Urbana': f"{row['urban_strength']*100:.0f}%"
        })
    
    display_df = pd.DataFrame(display_data)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Charts using native Streamlit
    st.subheader("📈 Visualizaciones")
    
    # Bar chart comparison
    chart_data = pd.DataFrame({
        'Candidato': [row['candidate'][:15] for _, row in proj_df.iterrows()],
        'Actual': proj_df['current_votes'].values,
        'Proyectado': proj_df['projected_votes'].values
    })
    
    st.bar_chart(chart_data.set_index('Candidato'))
    
    # Methodology
    with st.expander("📖 Metodología"):
        st.markdown("""
        ### Modelo de Proyección
        
        **Supuestos del modelo:**
        - Lima: 89% contabilizado (procesa rápido)
        - Provincias: 45% contabilizado (procesa lento)
        - Lima representa 32% del electorado nacional
        - Provincias representan 68% del electorado nacional
        
        **Candidatos por fortaleza regional:**
        - **Urbanos (75% Lima)**: López Aliaga, Renovación Popular
        - **Rurales (35% Lima)**: Candidatos con "Sánchez" o "Popular"
        - **Neutrales (50% Lima)**: Otros candidatos
        
        **Cálculo:**
        1. Estimar votos totales cuando esté 100% contabilizado
        2. Calcular votos pendientes por región
        3. Proyectar distribución según fortaleza regional del candidato
        4. Sumar votos actuales + votos adicionales proyectados
        """)

def main():
    """Main application"""
    
    # Auto-refresh logic
    should_refresh = False
    
    if st.session_state.last_update is None:
        should_refresh = True
    else:
        elapsed = (datetime.now() - st.session_state.last_update).seconds
        if elapsed >= 45:  # Refresh every 45 seconds
            should_refresh = True
    
    if should_refresh:
        st.session_state.last_update = datetime.now()
        create_dashboard()
    else:
        create_dashboard()
    
    # Countdown to next refresh
    if st.session_state.last_update:
        elapsed = (datetime.now() - st.session_state.last_update).seconds
        remaining = max(0, 45 - elapsed)
        st.markdown(f"🔄 Próxima actualización en: **{remaining}** segundos")
    
    # Auto-refresh
    time.sleep(2)
    st.rerun()

if __name__ == "__main__":
    main()
