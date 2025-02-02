import streamlit as st
import numpy as np
import plotly.graph_objects as go

def calculate_variable_impacts(samples, formula, variables):
    """
    Calcola l'impatto relativo di ogni variabile sul risultato totale
    """
    base_result = eval(formula, {"__builtins__": {}}, samples)
    impacts = {}
    
    for var_name in variables.keys():
        # Creiamo una copia dei samples per la simulazione
        test_samples = samples.copy()
        # Calcoliamo la media della variabile
        var_mean = np.mean(test_samples[var_name])
        # Sostituiamo i valori della variabile con la sua media
        test_samples[var_name] = np.full_like(test_samples[var_name], var_mean)
        # Calcoliamo il risultato con questa variabile "fissa"
        test_result = eval(formula, {"__builtins__": {}}, test_samples)
        # L'impatto è la differenza nella varianza
        impact = 1 - (np.var(test_result) / np.var(base_result))
        impacts[var_name] = impact
    
    # Normalizziamo gli impatti per ottenere percentuali
    total_impact = sum(impacts.values())
    if total_impact > 0:
        impacts = {k: v/total_impact * 100 for k, v in impacts.items()}
    
    return impacts

def create_weighted_results_plot(result, mean_val, target_value, formula_name, prob_text, original_result=None):
    """
    Crea il grafico dei risultati con confronto opzionale con la distribuzione originale
    """
    fig = go.Figure()
    
    # Aggiungiamo la distribuzione pesata
    fig.add_trace(go.Histogram(
        x=result,
        nbinsx=50,
        name='Distribuzione Pesata',
        opacity=0.75
    ))
    
    # Se abbiamo i risultati originali, li aggiungiamo come riferimento
    if original_result is not None:
        fig.add_trace(go.Histogram(
            x=original_result,
            nbinsx=50,
            name='Distribuzione Originale',
            opacity=0.5
        ))
    
    fig.add_vline(
        x=mean_val, 
        line_dash="dash", 
        line_color="green", 
        annotation_text=f"Media Pesata: {mean_val:.1f}"
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
        height=600,
        barmode='overlay'
    )
    
    return fig

def render_sensitivity_analysis(variables, samples, formula, target_value, 
                              target_direction, formula_name, calculate_stats_fn):
    """
    Renderizza l'analisi di sensitività con slider interattivi
    """
    st.markdown("### Analisi di Sensitività")
    
    # Calcoliamo e mostriamo gli impatti iniziali
    impacts = calculate_variable_impacts(samples, formula, variables)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### Impatto delle Variabili sul Risultato")
        impact_cols = st.columns(len(variables))
        for i, (var_name, impact) in enumerate(impacts.items()):
            with impact_cols[i]:
                st.metric(
                    f"{var_name}", 
                    f"{impact:.1f}%",
                    help=f"Contributo di {var_name} alla variabilità del risultato"
                )
    
    # Creiamo slider per modificare i pesi delle variabili
    st.markdown("#### What If Analysis")
    weights = {}
    weight_cols = st.columns(len(variables))
    
    for i, var_name in enumerate(variables.keys()):
        with weight_cols[i]:
            weights[var_name] = st.slider(
                f"Var % {var_name}",
                min_value=0.0,
                max_value=2.0,
                value=1.0,
                step=0.01,
                key=f"weight_{var_name}",
                help=f"Modifica l'impatto di {var_name} sul risultato finale"
            )
    
    # Applichiamo i pesi alle distribuzioni
    weighted_samples = {
        var_name: samples[var_name] * weights[var_name]
        for var_name in variables.keys()
    }
    
    # Calcoliamo il nuovo risultato
    weighted_result = eval(formula, {"__builtins__": {}}, weighted_samples)
    original_result = eval(formula, {"__builtins__": {}}, samples)
    
    # Calcoliamo le statistiche e creiamo il grafico
    stats, prob_text = calculate_stats_fn(
        weighted_result, target_value, target_direction, formula_name
    )
    
    fig = create_weighted_results_plot(
        weighted_result, stats['mean'], target_value, formula_name, 
        prob_text, original_result
    )
    
    # Mostriamo i risultati pesati
    st.markdown("#### Risultati con Pesi Modificati")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Media Pesata", f"{stats['mean']:.1f}")
    with col2:
        st.metric("Mediana Pesata", f"{stats['median']:.1f}")
    with col3:
        st.metric("Deviazione Standard Pesata", f"{stats['std']:.1f}")
    
    # col1, col2 = st.columns(2)
    # with col1:
    #     st.metric("5° Percentile Pesato", f"{stats['percentile_5']:.1f}")
    # with col2:
    #     st.metric("95° Percentile Pesato", f"{stats['percentile_95']:.1f}")
    
    st.plotly_chart(fig, use_container_width=True)

def run_sensitivity_simulation(variables, formula, target_value, target_direction, 
                             formula_name, n_simulations, generate_samples_fn, 
                             calculate_stats_fn):
    """
    Esegue la simulazione completa con analisi di sensitività
    """
    try:
        # Generiamo i campioni
        samples = {
            var_name: generate_samples_fn(var_info['type'], var_info['params'], n_simulations)
            for var_name, var_info in variables.items()
        }
        
        # Mostriamo l'analisi di sensitività
        render_sensitivity_analysis(
            variables, samples, formula, 
            target_value, target_direction, formula_name,
            calculate_stats_fn
        )
        
    except Exception as e:
        st.error(f"Errore durante l'analisi di sensitività: {str(e)}")