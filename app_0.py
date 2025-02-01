import streamlit as st
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
from scipy import stats

def generate_samples(dist_type, params, n_samples=10000):
    if dist_type == "Triangular":
        return np.random.triangular(params['lower'], params['mode'], params['upper'], n_samples)
    elif dist_type == "Normal":
        return np.random.normal(params['mean'], params['std'], n_samples)
    elif dist_type == "Uniform":
        return np.random.uniform(params['min'], params['max'], n_samples)
    return None

st.title("Monte Carlo Simulation Builder")

# Numero di simulazioni
n_simulations = st.sidebar.number_input("Numero di simulazioni", min_value=1000, max_value=100000, value=10000, step=1000)

# Dizionario per memorizzare le variabili
variables = {}

# Layout principale
st.header("1. Definisci le Variabili")

# Aggiungi fino a 5 variabili
for i in range(5):
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Checkbox per attivare/disattivare la variabile
        active = st.checkbox(f"Variabile {i+1}", key=f"var_active_{i}")
    
    if active:
        with col2:
            # Contenitore per i parametri della variabile
            with st.expander(f"Parametri Variabile {i+1}", expanded=True):
                # Nome della variabile
                var_name = st.text_input("Nome", value=f"X{i+1}", key=f"var_name_{i}")
                
                # Tipo di distribuzione
                dist_type = st.selectbox(
                    "Distribuzione",
                    ["Triangular", "Normal", "Uniform"],
                    key=f"dist_type_{i}"
                )
                
                # Parametri specifici per ogni distribuzione
                if dist_type == "Triangular":
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        lower = st.number_input("Lower", value=0.0, key=f"lower_{i}")
                    with col2:
                        mode = st.number_input("Mode", value=1.0, key=f"mode_{i}")
                    with col3:
                        upper = st.number_input("Upper", value=2.0, key=f"upper_{i}")
                    params = {'lower': lower, 'mode': mode, 'upper': upper}
                
                elif dist_type == "Normal":
                    col1, col2 = st.columns(2)
                    with col1:
                        mean = st.number_input("Media", value=0.0, key=f"mean_{i}")
                    with col2:
                        std = st.number_input("Deviazione Standard", value=1.0, min_value=0.0, key=f"std_{i}")
                    params = {'mean': mean, 'std': std}
                
                elif dist_type == "Uniform":
                    col1, col2 = st.columns(2)
                    with col1:
                        min_val = st.number_input("Minimo", value=0.0, key=f"min_{i}")
                    with col2:
                        max_val = st.number_input("Massimo", value=1.0, key=f"max_{i}")
                    params = {'min': min_val, 'max': max_val}
                
                variables[var_name] = {
                    'type': dist_type,
                    'params': params
                }

st.header("2. Definisci la Formula")

# Input per la formula
available_vars = " ".join(variables.keys())
st.write(f"Variabili disponibili: {available_vars}")
formula = st.text_input("Formula (usa operatori Python standard)", value=" + ".join(variables.keys()))

# Pulsante per eseguire la simulazione
if st.button("Esegui Simulazione"):
    try:
        # Genera i campioni per ogni variabile
        samples = {}
        for var_name, var_info in variables.items():
            samples[var_name] = generate_samples(var_info['type'], var_info['params'], n_simulations)
        
        # Valuta la formula
        result = eval(formula, {"__builtins__": {}}, samples)
        
        # Calcola le statistiche
        mean_val = np.mean(result)
        median_val = np.median(result)
        std_val = np.std(result)
        percentile_5 = np.percentile(result, 5)
        percentile_95 = np.percentile(result, 95)
        
        # Visualizza i risultati
        st.header("3. Risultati")
        
        # Crea il grafico con Plotly
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=result, nbinsx=50, name='Distribuzione'))
        fig.add_vline(x=mean_val, line_dash="dash", line_color="red", annotation_text=f"Media: {mean_val:.2f}")
        fig.add_vline(x=median_val, line_dash="dash", line_color="green", annotation_text=f"Mediana: {median_val:.2f}")
        
        fig.update_layout(
                            title="Distribuzione dei Risultati",
                            xaxis_title="Valore",
                            yaxis_title="Frequenza",
                            showlegend=True
                            )
        
        st.plotly_chart(fig)
        
        # Mostra le statistiche
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Media", f"{mean_val:.2f}")
        with col2:
            st.metric("Mediana", f"{median_val:.2f}")
        with col3:
            st.metric("Deviazione Standard", f"{std_val:.2f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("5° Percentile", f"{percentile_5:.2f}")
        with col2:
            st.metric("95° Percentile", f"{percentile_95:.2f}")
            
    except Exception as e:
        st.error(f"Errore durante la simulazione: {str(e)}")

# Aggiungi note informative
st.sidebar.markdown("""
### Note:
- Puoi attivare fino a 5 variabili
- La formula può usare operatori Python (+, -, *, /, **)
- Il grafico mostra la distribuzione dei risultati
""")