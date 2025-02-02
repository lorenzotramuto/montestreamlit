import streamlit as st
import numpy as np
import plotly.graph_objects as go
import traceback
import json
import time
from datetime import datetime
from utils_bq import ConfigurationManager
from sensitivita import run_sensitivity_simulation


# ============= App Configuration =============
st.set_page_config(layout="wide", page_title="Monte Carlo Simulation")

# ============= Configuration Manager Initialization =============
@st.cache_resource
def get_config_manager():
    # Create credentials dict from st.secrets
    credentials = {
        "type": st.secrets["gcp"]["type"],
        "project_id": st.secrets["gcp"]["project_id"],
        "private_key_id": st.secrets["gcp"]["private_key_id"],
        "private_key": st.secrets["gcp"]["private_key"],
        "client_email": st.secrets["gcp"]["client_email"],
        "client_id": st.secrets["gcp"]["client_id"],
        "auth_uri": st.secrets["gcp"]["auth_uri"],
        "token_uri": st.secrets["gcp"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp"]["client_x509_cert_url"]
    }
    return ConfigurationManager(credentials=credentials)

try:
    config_manager = get_config_manager()
except Exception as e:
    st.error(f"Failed to initialize configuration manager: {str(e)}")
    st.stop()

# ============= Login System =============
LOGIN = {
    'test@gmail.com': '1234',
    'riccardo.silvi@unibo.it': 'futura',
}

def authenticate(email, password):
    """Authenticate user with email and password"""
    return LOGIN.get(email) == password

def check_authentication():
    """Check if the user is authenticated and initialize session state if needed"""
    # Initialize authentication state if not present
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # If not authenticated, show login form
    if not st.session_state.authenticated:
        st.title("Login")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Accedi", use_container_width=True):
                if authenticate(email, password):
                    st.session_state.authenticated = True
                    st.session_state.user = email
                    st.rerun()
                else:
                    st.error("Credenziali errate. Riprova.")
        
        st.stop()

# ============= Session State Initialization =============
def init_session_state():
    if 'loaded_config' not in st.session_state:
        st.session_state.loaded_config = None
    if 'current_config_id' not in st.session_state:
        st.session_state.current_config_id = None

init_session_state()

# ============= Distribution Functions =============
def generate_samples(dist_type: str, params: dict, n_samples: int = 10000) -> np.ndarray:
    """Generate random samples based on distribution type and parameters."""
    generators = {
        "Triangular": lambda p: np.round(np.random.triangular(
            p['lower'], p['mode'], p['upper'], n_samples
        )),
        "Normal": lambda p: np.round(np.random.normal(
            p['mean'], p['std'], n_samples
        )),
        "Uniform": lambda p: np.round(np.random.uniform(
            p['min'], p['max'], n_samples
        )),
        "Fixed": lambda p: np.full(n_samples, p['value'])
    }
    return generators.get(dist_type, lambda _: None)(params)

def create_distribution_preview(dist_type: str, params: dict, var_name: str, n_samples: int = 1000):
    """Create a small preview plot for the distribution"""
    samples = generate_samples(dist_type, params, n_samples)
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=samples,
        nbinsx=20,
        name='Preview',
        marker_color='#2E7D32'
    ))
    
    fig.update_layout(
        title=f"Distribuzione {var_name}",
        showlegend=False,
        margin=dict(l=20, r=20, t=30, b=20),
        height=150
    )
    
    return fig

# ============= Variable Configuration =============
def render_fixed_config(i: int):
    """Render UI for fixed value parameters"""
    value = st.number_input("Valore Fisso", value=0, step=1, key=f"fixed_value_{i}")
    return {'value': value}

def render_triangular_config(i: int):
    """Render UI for triangular distribution parameters"""
    col1, col2 = st.columns(2)
    with col1:
        min_range = st.number_input("Min Range", value=-10, step=1, key=f"min_range_{i}")
    with col2:
        max_range = st.number_input("Max Range", value=10, step=1, key=f"max_range_{i}")
    
    st.write("Parametri Distribuzione:")
    lower = st.slider("Lower", min_range, max_range, 
                     int((max_range - min_range) * 0.3 + min_range), 1, 
                     key=f"lower_{i}")
    mode = st.slider("Mode", lower, max_range, 
                    int((lower + max_range) / 2), 1, 
                    key=f"mode_{i}")
    upper = st.slider("Upper", mode, max_range, 
                     max_range, 1, 
                     key=f"upper_{i}")
    
    return {'lower': lower, 'mode': mode, 'upper': upper}

def render_normal_config(i: int):
    """Render UI for normal distribution parameters"""
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
                    int((mean_min + mean_max) / 2), 1, 
                    key=f"mean_{i}")
    std = st.slider("Deviazione Standard", std_min, std_max, 
                   int((std_min + std_max) / 2), 1, 
                   key=f"std_{i}")
    
    return {'mean': mean, 'std': std}

def render_uniform_config(i: int):
    """Render UI for uniform distribution parameters"""
    col1, col2 = st.columns(2)
    with col1:
        range_min = st.number_input("Min Range", value=-10, step=1, key=f"uni_min_range_{i}")
    with col2:
        range_max = st.number_input("Max Range", value=10, step=1, key=f"uni_max_range_{i}")
    
    st.write("Parametri Distribuzione:")
    min_val = st.slider("Minimo", range_min, range_max, 
                       range_min, 1, 
                       key=f"min_{i}")
    max_val = st.slider("Massimo", min_val, range_max, 
                       range_max, 1, 
                       key=f"max_{i}")
    
    return {'min': min_val, 'max': max_val}

def render_variable_config(i: int, variables: dict):
    """Render configuration UI for a single variable"""
    var_active = st.sidebar.checkbox(f"Variabile {i+1}", key=f"var_active_{i}")
    
    if not var_active:
        return

    # Get variable name first
    var_name = st.session_state.get(f"var_name_{i}", f"Variabile {i+1}")
    
    # Use variable name in expander if it exists, otherwise use default name
    expander_title = var_name if var_name else f"Variabile {i+1}"
    with st.sidebar.expander(expander_title, expanded=True):
        var_name = st.text_input("Nome", key=f"var_name_{i}")
        dist_type = st.selectbox(
            "Distribuzione",
            ["Triangular", "Normal", "Uniform", "Fixed"],
            key=f"dist_type_{i}"
        )

        params = None
        if dist_type == "Triangular":
            params = render_triangular_config(i)
        elif dist_type == "Normal":
            params = render_normal_config(i)
        elif dist_type == "Uniform":
            params = render_uniform_config(i)
        elif dist_type == "Fixed":
            params = render_fixed_config(i)

        if params and var_name:
            variables[var_name] = {
                'type': dist_type,
                'params': params
            }
            # Show distribution preview only for non-fixed types
            if dist_type != "Fixed":
                st.plotly_chart(
                    create_distribution_preview(dist_type, params, var_name),
                    use_container_width=True
                )
            else:
                # Show fixed value info instead of distribution preview
                st.info(f"Valore fisso: {params['value']}")

# ============= Statistics Functions =============
def calculate_statistics(result, target_value, target_direction, formula_name):
    """Calculate and return statistics for the simulation results"""
    stats = {
        'mean': np.mean(result),
        'median': np.median(result),
        'std': np.std(result),
        'percentile_5': np.percentile(result, 5),
        'percentile_95': np.percentile(result, 95)
    }
    
    if target_direction == "Maggiore dell'obiettivo":
        prob = np.mean(result > target_value) * 100
        prob_text = f"P({formula_name} > {target_value}) = {prob:.1f}%"
    else:
        prob = np.mean(result < target_value) * 100
        prob_text = f"P({formula_name} < {target_value}) = {prob:.1f}%"
    
    return stats, prob_text

def create_results_plot(result, mean_val, target_value, formula_name, prob_text):
    """Create and return the results visualization plot"""
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=result,
        nbinsx=50,
        name='Distribuzione',
        showlegend=True
    ))
    
    fig.add_vline(
        x=mean_val, 
        line_dash="dash", 
        line_color="green", 
        annotation_text=f"Media: {mean_val:.1f}"
    )
    fig.add_vline(
        x=target_value,
        line=dict(color="red", width=2),
        annotation_text=f"Obiettivo: {target_value}"
    )
    
    fig.update_layout(
        title=f"Distribuzione di {formula_name} - {prob_text}",
        xaxis_title=formula_name,
        yaxis_title="Frequenza",
        showlegend=True,
        height=600
    )
    
    return fig

def display_results(stats, prob_text, fig):
    """Display simulation results and visualization"""
    st.markdown(f"### {prob_text}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Media", f"{stats['mean']:.1f}")
    with col2:
        st.metric("Mediana", f"{stats['median']:.1f}")
    with col3:
        st.metric("Deviazione Standard", f"{stats['std']:.1f}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("5° Percentile", f"{stats['percentile_5']:.1f}")
    with col2:
        st.metric("95° Percentile", f"{stats['percentile_95']:.1f}")
    
    st.plotly_chart(fig, use_container_width=True)

# ============= Configuration Management =============
def load_configuration(config_id):
    with st.spinner("Caricamento in corso..."):
        try:
            config_data = config_manager.get_configuration(config_id, st.session_state.user)
            if config_data:
                for key in list(st.session_state.keys()):
                    if key.startswith(('var_', 'loaded_config')):
                        del st.session_state[key]
                
                st.session_state.loaded_config = config_data
                st.session_state.current_config_id = config_id
                st.rerun()
            else:
                st.error("Configurazione non trovata")
        except Exception as e:
            st.error(f"Errore durante il caricamento: {str(e)}")

def delete_configuration(config_id):
    with st.spinner("Eliminazione in corso..."):
        try:
            config_manager.delete_configuration(config_id, st.session_state.user)
            if st.session_state.current_config_id == config_id:
                st.session_state.current_config_id = None
                st.session_state.loaded_config = None
            st.success("Configurazione eliminata!")
            st.rerun()
        except Exception as e:
            st.error(f"Errore durante l'eliminazione: {str(e)}")

def render_config_loader():
    st.markdown("## Carica Configurazione")
    try:
        configs = config_manager.load_configurations(st.session_state.user)
        if not configs:
            st.info("Nessuna configurazione salvata")
            return

        config_options = {f"{c['name']}": c['id'] for c in configs}
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_config = st.selectbox(
                "Seleziona Configurazione",
                list(config_options.keys())
            )
        
        with col2:
            if st.button("Carica", key="load_top"):
                load_configuration(config_options[selected_config])
        
        with col3:
            if st.button("Elimina", key="delete_top"):
                delete_configuration(config_options[selected_config])
                
    except Exception as e:
        st.error(f"Errore nella sezione di caricamento: {str(e)}")

def update_current_config(variables, formula_name, formula, target_value, 
                         target_direction, n_simulations):
    """Update existing configuration"""
    if not variables:
        st.error("Aggiungi almeno una variabile prima di salvare")
        return
                        
    with st.spinner("Aggiornamento configurazione in corso..."):
        try:
            config_id = int(st.session_state.current_config_id)
            
            config_data = {
                'variables': variables,
                'formula_name': formula_name,
                'formula': formula,
                'target_value': target_value,
                'target_direction': target_direction,
                'n_simulations': n_simulations
            }
            
            try:
                config_manager.update_configuration(
                    config_id, 
                    config_data,
                    st.session_state.user
                )
                
                st.session_state.loaded_config = config_data
                
                for key in list(st.session_state.keys()):
                    if key.startswith('var_'):
                        del st.session_state[key]
                
                st.success("✅ Configurazione aggiornata!")
                time.sleep(0.5)
                st.rerun()
                
            except Exception as e:
                st.error(f"Errore nell'aggiornamento: {str(e)}")
                st.error(traceback.format_exc())
                return False
            
        except Exception as e:
            st.error(f"Errore nella preparazione dell'aggiornamento: {str(e)}")
            st.error(traceback.format_exc())
            return False

def save_new_config(save_name, save_desc, variables, formula_name, formula, 
                   target_value, target_direction, n_simulations):
    """Save new configuration"""
    if not variables:
        st.error("Aggiungi almeno una variabile prima di salvare")
        return
        
    with st.spinner("Salvataggio in corso..."):
        config_data = {
            'variables': variables,
            'formula_name': formula_name,
            'formula': formula,
            'target_value': target_value,
            'target_direction': target_direction,
            'n_simulations': n_simulations
        }
        try:
            config_id = config_manager.save_configuration(
                save_name,
                save_desc,
                config_data,
                st.session_state.user
            )
            st.session_state.current_config_id = config_id
            st.success("Nuova configurazione salvata con successo!")
        except Exception as e:
            st.error(f"Errore durante il salvataggio: {str(e)}")

def render_config_management(variables, formula_name, formula, target_value, 
                           target_direction, n_simulations):
    """Render configuration management UI"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## Gestione Configurazioni")
    
    with st.sidebar.expander("Salva Configurazione", expanded=False):
        try:
            if st.session_state.current_config_id:
                st.write("Configurazione corrente:", st.session_state.current_config_id)
                
                # Display current values for verification
                st.write(f"Nome Risultato: {formula_name}")
                st.write(f"Formula: {formula}")
                st.write(f"Valore Obiettivo: {target_value}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Aggiorna Configurazione", key="update_config"):
                        update_current_config(variables, formula_name, formula, 
                                           target_value, target_direction, n_simulations)
                with col2:
                    if st.button("Ricarica", key="reload_current"):
                        st.rerun()
            
            save_name = st.text_input("Nome Nuova Configurazione")
            save_desc = st.text_area("Descrizione")
            
            if st.button("Salva Come Nuova") and save_name:
                save_new_config(save_name, save_desc, variables, formula_name, 
                              formula, target_value, target_direction, n_simulations)
        except Exception as e:
            st.error(f"Errore nella sezione di salvataggio: {str(e)}")
            st.error(traceback.format_exc())

def init_variable_state(i, var_name, var_info):
    """Initialize session state for a variable from loaded config"""
    if f"var_active_{i}" not in st.session_state:
        st.session_state[f"var_active_{i}"] = True
        st.session_state[f"var_name_{i}"] = var_name
        st.session_state[f"dist_type_{i}"] = var_info['type']
        
        params = var_info['params']
        if var_info['type'] == "Triangular":
            st.session_state[f"lower_{i}"] = params['lower']
            st.session_state[f"mode_{i}"] = params['mode']
            st.session_state[f"upper_{i}"] = params['upper']
            st.session_state[f"min_range_{i}"] = params['lower'] - 5
            st.session_state[f"max_range_{i}"] = params['upper'] + 5
        elif var_info['type'] == "Normal":
            st.session_state[f"mean_{i}"] = params['mean']
            st.session_state[f"std_{i}"] = params['std']
            st.session_state[f"mean_min_{i}"] = params['mean'] - 10
            st.session_state[f"mean_max_{i}"] = params['mean'] + 10
            st.session_state[f"std_min_{i}"] = 1
            st.session_state[f"std_max_{i}"] = max(params['std'] + 2, 5)
        elif var_info['type'] == "Uniform":
            st.session_state[f"min_{i}"] = params['min']
            st.session_state[f"max_{i}"] = params['max']
            st.session_state[f"uni_min_range_{i}"] = params['min'] - 5
            st.session_state[f"uni_max_range_{i}"] = params['max'] + 5
        elif var_info['type'] == "Fixed":
            st.session_state[f"fixed_value_{i}"] = params['value']

def show_instructions():
    st.sidebar.markdown("""
    ---
    ### Istruzioni:
    1. Attiva le variabili desiderate
    2. Configura i parametri per ogni variabile:
       - Per distribuzioni: imposta i range e usa gli slider
       - Per costi fissi: inserisci il valore costante
    3. Definisci la formula usando gli operatori (+, -, *, /, **)
    4. Imposta il valore obiettivo e la direzione
    5. Osserva i risultati e la probabilità calcolata
    6. Usa l'analisi di sensitività per capire l'impatto di ogni variabile
    7. Salva la configurazione per uso futuro
    """)

def main():
    # Check authentication at the start
    check_authentication()
    
    st.title("Simulazione Monte Carlo")
    
    # Display user welcome message and logout button in a row
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.write(f"Benvenuto, {st.session_state.user}!")
    with col2:
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
    
    # Load configuration section at the top
    render_config_loader()
    
    # Sidebar configuration
    st.sidebar.title("Configurazione Simulazione")
    
    # Number of simulations
    n_simulations = st.sidebar.slider(
        "Numero di simulazioni", 
        min_value=1000, 
        max_value=10000, 
        value=st.session_state.loaded_config['n_simulations'] if st.session_state.loaded_config else 5000, 
        step=1000
    )
    
    # Variables dictionary and configuration
    variables = {}
    st.sidebar.markdown("## Variabili")
    
    # Initialize variables from loaded config
    if st.session_state.loaded_config:
        config_data = st.session_state.loaded_config
        for i, (var_name, var_info) in enumerate(config_data['variables'].items()):
            init_variable_state(i, var_name, var_info)
    
    # Render variable configurations
    for i in range(5):
        render_variable_config(i, variables)
    
    # Formula Section
    st.sidebar.markdown("## Formula")
    available_vars = " ".join(variables.keys())
    st.sidebar.write(f"Variabili disponibili: {available_vars}")
    
    formula_name = st.sidebar.text_input(
        "Nome del Risultato",
        value=st.session_state.loaded_config['formula_name'] if st.session_state.loaded_config else "Risultato Totale"
    )
    
    formula = st.sidebar.text_input(
        "Formula",
        value=st.session_state.loaded_config['formula'] if st.session_state.loaded_config else " + ".join(variables.keys())
    )
    
    # Target Section
    st.sidebar.markdown("## Obiettivo")
    target_value = st.sidebar.number_input(
        "Valore Obiettivo",
        value=st.session_state.loaded_config.get('target_value', 0) if st.session_state.loaded_config else 0,
        step=1
    )
    target_direction = st.sidebar.radio(
        "Calcola Probabilità", 
        ["Maggiore dell'obiettivo", "Minore dell'obiettivo"],
        horizontal=True,
        index=0 if not st.session_state.loaded_config else 
              0 if st.session_state.loaded_config.get('target_direction') == "Maggiore dell'obiettivo" else 1
    )
    
    # Configuration Management
    render_config_management(
        variables, formula_name, formula, 
        target_value, target_direction, n_simulations
    )
    
    # Run Simulation
    if variables:
        try:
            # Generate samples
            samples = {
                var_name: generate_samples(var_info['type'], var_info['params'], n_simulations)
                for var_name, var_info in variables.items()
            }
            
            # Evaluate formula
            result = eval(formula, {"__builtins__": {}}, samples)
            
            # Calculate statistics
            stats, prob_text = calculate_statistics(
                result, target_value, target_direction, formula_name
            )
            
            # Create and display results plot
            fig = create_results_plot(
                result, stats['mean'], target_value, formula_name, prob_text
            )
            display_results(stats, prob_text, fig)
            
            # Add sensitivity analysis
            st.markdown("---")
            run_sensitivity_simulation(
                variables=variables,
                formula=formula,
                target_value=target_value,
                target_direction=target_direction,
                formula_name=formula_name,
                n_simulations=n_simulations,
                generate_samples_fn=generate_samples,
                calculate_stats_fn=calculate_statistics
            )
            
        except Exception as e:
            st.error(f"Errore durante la simulazione: {str(e)}")
    else:
        st.info("Attiva almeno una variabile nella sidebar per iniziare la simulazione.")

    # Show instructions
    show_instructions()

if __name__ == "__main__":
    main()