import streamlit as st
import numpy as np
import plotly.graph_objects as go
import json
from datetime import datetime
import pandas as pd
from utils_bq import write_dataframe_to_bigquery, execute_bigquery_and_get_dataframe

# ====================== SETUP ======================
st.set_page_config(layout="wide")

# ====================== DATABASE FUNCTIONS ======================
def save_configuration(name: str, description: str, config_data: dict):
    """Save a new configuration to BigQuery."""
    df = pd.DataFrame({
        'id': [int(datetime.now().timestamp())],
        'name': [name],
        'description': [description],
        'config_data': [json.dumps(config_data)],
        'created_at': [datetime.now()]
    })
    write_dataframe_to_bigquery(df, how="WRITE_APPEND")

def update_configuration(config_id: int, config_data: dict):
    """Update an existing configuration in BigQuery."""
    query = f"""
    UPDATE `monte_carlo_configs.configurations`
    SET config_data = '{json.dumps(config_data)}',
        updated_at = CURRENT_TIMESTAMP()
    WHERE id = {config_id}
    """
    df = pd.DataFrame([{'query': query}])
    write_dataframe_to_bigquery(df, how="WRITE_APPEND")

def load_configurations():
    """Load all configurations from BigQuery."""
    df = execute_bigquery_and_get_dataframe()
    if df is not None and not df.empty:
        df = df.sort_values('created_at', ascending=False)
        return df[['id', 'name', 'description', 'created_at']].values.tolist()
    return []

def get_configuration(config_id: int):
    """Get a specific configuration by ID."""
    df = execute_bigquery_and_get_dataframe()
    if df is not None and not df.empty:
        config = df[df['id'] == config_id]
        if not config.empty:
            st.write(f"Configuration found for ID {config_id}: {config.iloc[0]['config_data']}")
            return json.loads(config.iloc[0]['config_data'])
    st.write(f"No configuration found for ID {config_id}")
    return None

def delete_configuration(config_id: int):
    """Delete a configuration by ID."""
    query = f"""
    DELETE FROM monte_carlo_configs.configurations 
    WHERE id = {config_id}
    """
    df = pd.DataFrame({'statement': [query]})
    write_dataframe_to_bigquery(df, how="WRITE_APPEND")

# ====================== SIMULATION FUNCTIONS ======================
def generate_samples(dist_type: str, params: dict, n_samples: int = 10000) -> np.ndarray:
    """Generate random samples based on distribution type and parameters."""
    if dist_type == "Triangular":
        return np.round(np.random.triangular(
            params['lower'], params['mode'], params['upper'], n_samples))
    elif dist_type == "Normal":
        return np.round(np.random.normal(
            params['mean'], params['std'], n_samples))
    elif dist_type == "Uniform":
        return np.round(np.random.uniform(
            params['min'], params['max'], n_samples))
    return None

# ====================== SESSION STATE INITIALIZATION ======================
if 'loaded_config' not in st.session_state:
    st.session_state.loaded_config = None
if 'current_config_id' not in st.session_state:
    st.session_state.current_config_id = None

# ====================== SIDEBAR CONFIGURATION ======================
st.sidebar.title("Configurazione Simulazione")

# ----------------------- Load Configuration Section -----------------------
load_expander = st.sidebar.expander("Carica Configurazione")
with load_expander:
    configs = load_configurations()
    if configs:
        config_options = {f"{c[1]}": c[0] for c in configs}
        selected_config = st.selectbox(
            "Seleziona Configurazione", 
            list(config_options.keys()),
            key="load_configuration_selectbox"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Carica", key="load_button"):
                config_id = config_options[selected_config]
                st.write(f"Loading configuration ID: {config_id}")
                config_data = get_configuration(config_id)
                if config_data:
                    st.write(f"Loaded configuration data: {config_data}")
                    # Reset all variable-related session state
                    for i in range(5):
                        keys_to_reset = [
                            f"var_active_{i}", f"var_name_{i}", f"dist_type_{i}",
                            f"lower_{i}", f"mode_{i}", f"upper_{i}",
                            f"min_range_{i}", f"max_range_{i}",
                            f"mean_{i}", f"std_{i}",
                            f"mean_min_{i}", f"mean_max_{i}",
                            f"std_min_{i}", f"std_max_{i}",
                            f"min_{i}", f"max_{i}",
                            f"uni_min_range_{i}", f"uni_max_range_{i}"
                        ]
                        for key in keys_to_reset:
                            if key in st.session_state:
                                del st.session_state[key]
                    
                    st.session_state.loaded_config = config_data
                    st.session_state.current_config_id = config_id
                    
                    # Load variables from config
                    var_names = list(config_data['variables'].keys())
                    for i, var_name in enumerate(var_names[:5]):
                        var_info = config_data['variables'][var_name]
                        st.session_state[f"var_active_{i}"] = True
                        st.session_state[f"var_name_{i}"] = var_name
                        st.session_state[f"dist_type_{i}"] = var_info['type']
                        
                        params = var_info['params']
                        if var_info['type'] == "Triangular":
                            # CORREZIONE APPLICATA QUI
                            value_range = params['upper'] - params['lower']
                            st.session_state[f"min_range_{i}"] = int(round(params['lower'] - (value_range * 0.1)))
                            st.session_state[f"max_range_{i}"] = int(round(params['upper'] + (value_range * 0.1)))
                            st.session_state[f"lower_{i}"] = params['lower']
                            st.session_state[f"mode_{i}"] = params['mode']
                            st.session_state[f"upper_{i}"] = params['upper']
                        
                        elif var_info['type'] == "Normal":
                            st.session_state[f"mean_{i}"] = params['mean']
                            st.session_state[f"std_{i}"] = params['std']
                            st.session_state[f"mean_min_{i}"] = params['mean'] - (3 * params['std'])
                            st.session_state[f"mean_max_{i}"] = params['mean'] + (3 * params['std'])
                            st.session_state[f"std_min_{i}"] = max(1, params['std'] * 0.5)
                            st.session_state[f"std_max_{i}"] = params['std'] * 2
                        
                        elif var_info['type'] == "Uniform":
                            value_range = params['max'] - params['min']
                            st.session_state[f"uni_min_range_{i}"] = params['min'] - (value_range * 0.1)
                            st.session_state[f"uni_max_range_{i}"] = params['max'] + (value_range * 0.1)
                            st.session_state[f"min_{i}"] = params['min']
                            st.session_state[f"max_{i}"] = params['max']
                    
                    st.rerun()
        
        with col2:
            if st.button("Elimina", key="delete_button"):
                config_id = config_options[selected_config]
                delete_configuration(config_id)
                if st.session_state.current_config_id == config_id:
                    st.session_state.current_config_id = None
                    st.session_state.loaded_config = None
                st.success("Configurazione eliminata!")
                st.rerun()
    else:
        st.info("Nessuna configurazione salvata")

# ----------------------- Simulation Parameters -----------------------
n_simulations = st.sidebar.slider(
    "Numero di simulazioni", 
    min_value=1000, 
    max_value=100000, 
    value=st.session_state.loaded_config['n_simulations'] if st.session_state.loaded_config else 10000, 
    step=1000,
    key="n_simulations_slider"
)

# ----------------------- Variables Section -----------------------
st.sidebar.markdown("## Variabili")
variables = {}

for i in range(5):
    var_active = st.sidebar.checkbox(f"Variabile {i+1}", key=f"var_active_{i}")
    
    if var_active:
        with st.sidebar.expander(f"Configurazione Variabile {i+1}", expanded=True):
            var_name = st.text_input("Nome", key=f"var_name_{i}")
            
            dist_type = st.selectbox(
                "Distribuzione",
                ["Triangular", "Normal", "Uniform"],
                key=f"dist_type_{i}"
            )
            
            st.write("Configura Range Slider:")
            if dist_type == "Triangular":
                col1, col2 = st.columns(2)
                with col1:
                    min_range = st.number_input("Min Range", value=-10, step=1, key=f"min_range_{i}")
                with col2:
                    max_range = st.number_input("Max Range", value=10, step=1, key=f"max_range_{i}")
                
                st.write("Parametri Distribuzione:")
                lower = st.slider("Lower", min_range, max_range, 
                                int((max_range - min_range) * 0.3 + min_range), 1, key=f"lower_{i}")
                mode = st.slider("Mode", lower, max_range, 
                               int((lower + max_range) / 2), 1, key=f"mode_{i}")
                upper = st.slider("Upper", mode, max_range, 
                                max_range, 1, key=f"upper_{i}")
                params = {'lower': lower, 'mode': mode, 'upper': upper}
            
            elif dist_type == "Normal":
                col1, col2 = st.columns(2)
                with col1:
                    mean_min = st.number_input("Min Media", value=-10, step=1, key=f"mean_min_{i}")
                with col2:
                    mean_max = st.number_input("Max Media", value=10, step=1, key=f"mean_max_{i}")
                
                col1, col2 = st.columns(2)
                with col1:
                    std_min = st.number_input("Min Std", value=1, min_value=1, step=1, key=f"std_min_{i}")
                with col2:
                    std_max = st.number_input("Max Std", value=5, min_value=1, step=1, key=f"std_max_{i}")
                
                st.write("Parametri Distribuzione:")
                mean = st.slider("Media", mean_min, mean_max, 
                               int((mean_min + mean_max) / 2), 1, key=f"mean_{i}")
                std = st.slider("Deviazione Standard", std_min, std_max, 
                              int((std_min + std_max) / 2), 1, key=f"std_{i}")
                params = {'mean': mean, 'std': std}
            
            elif dist_type == "Uniform":
                col1, col2 = st.columns(2)
                with col1:
                    range_min = st.number_input("Min Range", value=-10, step=1, key=f"uni_min_range_{i}")
                with col2:
                    range_max = st.number_input("Max Range", value=10, step=1, key=f"uni_max_range_{i}")
                
                st.write("Parametri Distribuzione:")
                min_val = st.slider("Minimo", range_min, range_max, 
                                  range_min, 1, key=f"min_{i}")
                max_val = st.slider("Massimo", min_val, range_max, 
                                  range_max, 1, key=f"max_{i}")
                params = {'min': min_val, 'max': max_val}
            
            if var_name:
                variables[var_name] = {
                    'type': dist_type,
                    'params': params
                }

# ----------------------- Formula Section -----------------------
st.sidebar.markdown("## Formula")
available_vars = " ".join(variables.keys())
st.sidebar.write(f"Variabili disponibili: {available_vars}")
formula_name = st.sidebar.text_input("Nome del Risultato", 
                                   value="Risultato Totale", 
                                   key="formula_name")
formula = st.sidebar.text_input("Formula", 
                               value=" + ".join(variables.keys()) if variables else "", 
                               key="formula")

# ----------------------- Target Section -----------------------
st.sidebar.markdown("## Obiettivo")
target_value = st.sidebar.number_input("Valore Obiettivo", 
                                     value=0, 
                                     step=1, 
                                     key="target_value")
target_direction = st.sidebar.radio("Calcola Probabilità", 
                                  ["Maggiore dell'obiettivo", "Minore dell'obiettivo"],
                                  horizontal=True,
                                  key="target_direction")

# ----------------------- Save Configuration Section -----------------------
save_expander = st.sidebar.expander("Salva Configurazione")
with save_expander:
    if st.session_state.current_config_id:
        st.write("Configurazione corrente:", st.session_state.current_config_id)
        if st.button("Aggiorna Configurazione Corrente", key="update_config_button"):
            config_data = {
                'variables': variables,
                'formula_name': formula_name,
                'formula': formula,
                'target_value': target_value,
                'target_direction': target_direction,
                'n_simulations': n_simulations
            }
            update_configuration(st.session_state.current_config_id, config_data)
            st.success("Configurazione aggiornata con successo!")
    
    save_name = st.text_input("Nome Nuova Configurazione", key="save_name")
    save_desc = st.text_area("Descrizione", key="save_desc")
    if st.button("Salva Come Nuova", key="save_new_button") and save_name:
        config_data = {
            'variables': variables,
            'formula_name': formula_name,
            'formula': formula,
            'target_value': target_value,
            'target_direction': target_direction,
            'n_simulations': n_simulations
        }
        save_configuration(save_name, save_desc, config_data)
        st.success("Nuova configurazione salvata con successi!")

# ====================== MAIN CONTENT ======================
st.title("Simulazione Monte Carlo")

# ----------------------- Simulation Results -----------------------
if variables:
    try:
        # Generate samples
        samples = {}
        for var_name, var_info in variables.items():
            samples[var_name] = generate_samples(var_info['type'], 
                                              var_info['params'], 
                                              n_simulations)
        
        # Evaluate formula with restricted globals
        result = eval(formula, {"__builtins__": {}}, samples)
        
        # Calculate statistics
        mean_val = np.mean(result)
        median_val = np.median(result)
        std_val = np.std(result)
        percentile_5 = np.percentile(result, 5)
        percentile_95 = np.percentile(result, 95)
        
        # Calculate probability relative to target
        if target_direction == "Maggiore dell'obiettivo":
            prob = np.mean(result > target_value) * 100
            prob_text = f"P({formula_name} > {target_value}) = {prob:.1f}%"
        else:
            prob = np.mean(result < target_value) * 100
            prob_text = f"P({formula_name} < {target_value}) = {prob:.1f}%"
        
        # Display Results
        st.markdown(f"### {prob_text}")
        
        # Metrics Display
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Media", f"{mean_val:.1f}")
        with col2:
            st.metric("Mediana", f"{median_val:.1f}")
        with col3:
            st.metric("Deviazione Standard", f"{std_val:.1f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("5° Percentile", f"{percentile_5:.1f}")
        with col2:
            st.metric("95° Percentile", f"{percentile_95:.1f}")
        
        # Create visualization
        fig = go.Figure()
        
        # Add distribution histogram
        fig.add_trace(go.Histogram(
            x=result,
            nbinsx=50,
            name='Distribuzione',
            showlegend=True
        ))
        
        # Add reference lines
        fig.add_vline(x=mean_val, 
                     line_dash="dash", 
                     line_color="green", 
                     annotation_text=f"Media: {mean_val:.1f}")
        fig.add_vline(x=target_value,
                     line=dict(color="red", width=2),
                     annotation_text=f"Obiettivo: {target_value}")
        
        # Layout customization
        fig.update_layout(
            title=f"Distribuzione di {formula_name} - {prob_text}",
            xaxis_title=formula_name,
            yaxis_title="Frequenza",
            showlegend=True,
            height=600
        )
        
        # Display chart
        st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Errore durante la simulazione: {str(e)}")
else:
    st.info("Attiva almeno una variabile nella sidebar per iniziare la simulazione.")

# ----------------------- Instructions -----------------------
st.sidebar.markdown("""
---
### Istruzioni:
1. Attiva le variabili desiderate
2. Configura i range degli slider per ogni variabile
3. Imposta i parametri delle distribuzioni usando gli slider
4. Definisci la formula usando gli operatori (+, -, *, /, **)
5. Imposta il valore obiettivo e la direzione
6. Osserva i risultati e la probabilità calcolata
7. Salva la configurazione per uso futuro o aggiorna quella esistente
""")