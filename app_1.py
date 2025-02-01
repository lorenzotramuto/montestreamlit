import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy import stats

st.set_page_config(layout="wide")

def generate_samples(dist_type, params, n_samples=10000):
    if dist_type == "Triangular":
        return np.random.triangular(params['lower'], params['mode'], params['upper'], n_samples)
    elif dist_type == "Normal":
        return np.random.normal(params['mean'], params['std'], n_samples)
    elif dist_type == "Uniform":
        return np.random.uniform(params['min'], params['max'], n_samples)
    return None

# Configurazione sidebar
st.sidebar.title("Configurazione Simulazione")

# Numero di simulazioni nella sidebar
n_simulations = st.sidebar.slider("Numero di simulazioni", 
                                min_value=1000, 
                                max_value=100000, 
                                value=10000, 
                                step=1000)

# Dizionario per memorizzare le variabili
variables = {}

# Sezione variabili nella sidebar
st.sidebar.markdown("## Variabili")

# Container per mostrare la formula corrente
formula_container = st.sidebar.container()

# Aggiungi fino a 5 variabili nella sidebar
for i in range(5):
    var_active = st.sidebar.checkbox(f"Variabile {i+1}", key=f"var_active_{i}")
    
    if var_active:
        with st.sidebar.expander(f"Configurazione Variabile {i+1}", expanded=True):
            var_name = st.text_input("Nome", value=f"X{i+1}", key=f"var_name_{i}")
            
            dist_type = st.selectbox(
                "Distribuzione",
                ["Triangular", "Normal", "Uniform"],
                key=f"dist_type_{i}"
            )
            
            if dist_type == "Triangular":
                lower = st.slider("Lower", -10.0, 10.0, 0.0, 0.1, key=f"lower_{i}")
                mode = st.slider("Mode", lower, 10.0, (lower + 1.0), 0.1, key=f"mode_{i}")
                upper = st.slider("Upper", mode, 10.0, (mode + 1.0), 0.1, key=f"upper_{i}")
                params = {'lower': lower, 'mode': mode, 'upper': upper}
            
            elif dist_type == "Normal":
                mean = st.slider("Media", -10.0, 10.0, 0.0, 0.1, key=f"mean_{i}")
                std = st.slider("Deviazione Standard", 0.1, 5.0, 1.0, 0.1, key=f"std_{i}")
                params = {'mean': mean, 'std': std}
            
            elif dist_type == "Uniform":
                min_val = st.slider("Minimo", -10.0, 10.0, 0.0, 0.1, key=f"min_{i}")
                max_val = st.slider("Massimo", min_val, 10.0, (min_val + 1.0), 0.1, key=f"max_{i}")
                params = {'min': min_val, 'max': max_val}
            
            variables[var_name] = {
                'type': dist_type,
                'params': params
            }

# Formula nella sidebar
st.sidebar.markdown("## Formula")
available_vars = " ".join(variables.keys())
st.sidebar.write(f"Variabili disponibili: {available_vars}")
formula = st.sidebar.text_input("Formula", value=" + ".join(variables.keys()))

# Contenuto principale
st.title("Simulazione Monte Carlo")

# Auto-update dei risultati
if variables:
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
        
        # Layout per i risultati
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
        
        # Crea il grafico con Plotly
        fig = go.Figure()
        
        # Aggiunge l'istogramma principale
        fig.add_trace(go.Histogram(
            x=result,
            nbinsx=50,
            name='Distribuzione',
            showlegend=True
        ))
        
        # Aggiunge le linee per media e mediana
        fig.add_vline(x=mean_val, 
                     line_dash="dash", 
                     line_color="red", 
                     annotation_text=f"Media: {mean_val:.2f}")
        fig.add_vline(x=median_val, 
                     line_dash="dash", 
                     line_color="green", 
                     annotation_text=f"Mediana: {median_val:.2f}")
        
        # Personalizza il layout del grafico
        fig.update_layout(
            title="Distribuzione dei Risultati",
            xaxis_title="Valore",
            yaxis_title="Frequenza",
            showlegend=True,
            height=600
        )
        
        # Mostra il grafico
        st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Errore durante la simulazione: {str(e)}")
else:
    st.info("Attiva almeno una variabile nella sidebar per iniziare la simulazione.")

# Istruzioni nella sidebar
st.sidebar.markdown("""
---
### Istruzioni:
1. Attiva le variabili desiderate
2. Configura i parametri usando gli slider
3. Definisci la formula usando gli operatori (+, -, *, /, **)
4. Osserva i risultati aggiornati in tempo reale
""")