import streamlit as st
import random
import json
import os

# --- CONFIGURAZIONE ---
FILE_STATISTICHE = 'statistiche.json'

GIOCATORI_DEFAULT = [
    "Marco", "Luca", "Giovanni", "Matteo", "Andrea", 
    "Paolo", "Giuseppe", "Antonio", "Davide", "Simone", 
    "Alessandro", "Federico", "Lorenzo", "Stefano", "Michele"
]

# --- FUNZIONI DI SUPPORTO ---
def carica_statistiche():
    if os.path.exists(FILE_STATISTICHE):
        with open(FILE_STATISTICHE, 'r') as f:
            return json.load(f)
    else:
        stats = {giocatore: 0 for giocatore in GIOCATORI_DEFAULT}
        salva_statistiche(stats)
        return stats

def salva_statistiche(stats):
    with open(FILE_STATISTICHE, 'w') as f:
        json.dump(stats, f)

# Inizializzazione degli stati globali e di sessione
if 'stats' not in st.session_state:
    st.session_state.stats = carica_statistiche()

# Strutture per la memoria giornaliera (odierna)
if 'storico_squadre_oggi' not in st.session_state:
    st.session_state.storico_squadre_oggi = []  # Memorizza i set di squadre già fatti oggi
if 'partite_giocate_oggi' not in st.session_state:
    st.session_state.partite_giocate_oggi = {}  # Conteggio partite solo per la sessione corrente

# --- PAGINA 1: GENERATORE SQUADRE ---
def pagina_generatore():
    st.title("⚽ Generatore Squadre Calcietto")
    st.write("Priorità globale basata sulla storia delle partite + blocco ripetizioni per la sessione di oggi.")

    stats = st.session_state.stats
    tutti_i_giocatori = sorted(list(stats.keys()))

    if not tutti_i_giocatori:
        st.info("⚠️ Non ci sono giocatori registrati. Vai nella pagina 'Gestione Giocatori' per aggiungerne.")
        return

    # 1. SELEZIONE PRESENTI OGGI
    presenti_oggi = st.multiselect(
        "👥 Chi c'è a pranzo oggi?", 
        options=tutti_i_giocatori, 
        default=tutti_i_giocatori
    )

    max_giocatori_campo = st.slider("Giocatori in campo (totali)", min_value=4, max_value=14, value=10, step=2)

    # Inizializza i presenti nella sessione odierna se non esistono ancora
    for g in presenti_oggi:
        if g not in st.session_state.partite_giocate_oggi:
            st.session_state.partite_giocate_oggi[g] = 0

    st.divider()

    # 2. BOTTONE GENERA
    if st.button("🎲 Genera Squadre e Registra Partita", use_container_width=True, type="primary"):
        if len(presenti_oggi) < max_giocatori_campo:
            st.warning(f"Siete solo in {len(presenti_oggi)}! Servono almeno {max_giocatori_campo} giocatori.")
        else:
            # Algoritmo anti-ripetizione: proviamo a generare una combinazione nuova per un max di 50 tentativi
            tentativi = 0
            squadra_a, squadra_b = [], []
            in_campo, in_panchina = [], []
            
            while tentativi < 50:
                # Mischiamo i presenti in modo casuale
                presenti_mischati = random.sample(presenti_oggi, len(presenti_oggi))
                
                # Ordiniamo prima per chi ha giocato meno OGGI, e poi per chi ha giocato meno in ASSOLUTO (storico globale)
                presenti_ordinati = sorted(
                    presenti_mischati, 
                    key=lambda x: (st.session_state.partite_giocate_oggi.get(x, 0), stats.get(x, 0))
                )
                
                # Scegliamo chi va in campo e chi in panchina
                tentativo_in_campo = presenti_ordinati[:max_giocatori_campo]
                tentativo_in_panchina = Rankin = presenti_ordinati[max_giocatori_campo:]
                
                # Dividiamo in due squadre
                random.shuffle(tentativo_in_campo)
                meta = len(tentativo_in_campo) // 2
                tentativo_a = sorted(tentativo_in_campo[:meta])
                tentativo_b = sorted(tentativo_in_campo[meta:])
                
                # Creiamo un identificativo unico per questa partita (es. "Marco,Luca VS Andrea,Matteo")
                coppia_squadre = (tuple(tentativo_a), tuple(tentativo_b))
                coppia_squadre_inversa = (tuple(tentativo_b), tuple(tentativo_a))
                
                # Se questa combinazione non è mai uscita oggi, la accettiamo
                if (coppia_squadre not in st.session_state.storico_squadre_oggi) and (coppia_squadre_inversa not in st.session_state.storico_squadre_oggi):
                    squadra_a, squadra_b = tentativo_a, tentativo_b
                    in_campo, in_panchina = tentativo_in_campo, tentativo_in_panchina
                    st.session_state.storico_squadre_oggi.append(coppia_squadre)
                    break
                
                tentativi += 1

            # Se dopo 50 tentativi sono tutte ripetute (es. siete sempre in 10 precisi), usa l'ultimo tentativo generato
            if not squadra_a:
                squadra_a, squadra_b = tentativo_a, tentativo_b
                in_campo, in_panchina = tentativo_in_campo, tentativo_in_panchina

            # AGGIORNAMENTO STATISTICHE (Globale + Odierna)
            for giocatore in in_campo:
                stats[giocatore] = stats.get(giocatore, 0) + 1
                st.session_state.partite_giocate_oggi[giocatore] = st.session_state.partite_giocate_oggi.get(giocatore, 0) + 1
            
            salva_statistiche(stats)
            st.session_state.stats = stats
            
            # Mostra Risultati
            st.success("Squadre generate evitando ripetizioni odierne!")
            col1, col2 = st.columns(2)
            with col1:
                st.header("👕 Squadra A")
                for g in squadra_a: st.write(f"- {g}")
            with col2:
                st.header("🎽 Squadra B")
                for g in squadra_b: st.write(f"- {g}")
                    
            if in_panchina:
                st.divider()
                st.warning(f"⏱️ **In panchina per questo turno:** {', '.join(in_panchina)}")

    st.divider()

    # 3. GESTIONE AZZERAMENTO SESSIONE ODIERNA
    st.subheader("🧹 Sessione Odierna")
    st.write(f"Partite generate in questo pranzo: **{len(st.session_state.storico_squadre_oggi)}**")
    
    if st.button("♻️ Azzera Sessione Odierna", use_container_width=True):
        st.session_state.storico_squadre_oggi = []
        st.session_state.partite_giocate_oggi = {}
        st.success("Sessione azzerata! Le combinazioni di oggi sono state dimenticate (lo storico globale dei giorni scorsi è salvo).")
        st.rerun()

    # Espander con le statistiche globali
    with st.expander("📊 Vedi Storico Globale (Tutti i giorni)"):
        stats_ordinate = dict(sorted(stats.items(), key=lambda item: item[1], reverse=True))
        for giocatore, partite in stats_ordinate.items():
            st.write(f"**{giocatore}**: {partite} presenze totali")


# --- PAGINA 2: GESTIONE GIOCATORI ---
def pagina_gestione():
    st.title("⚙️ Gestione Anagrafica Giocatori")
    stats = st.session_state.stats

    # Aggiungi
    st.subheader("➕ Aggiungi Nuovo Collega")
    nuovo = st.text_input("Nome:", placeholder="Es. Tommaso").strip()
    if st.button("Aggiungi"):
        if nuovo and nuovo not in stats:
            stats[nuovo] = 0
            salva_statistiche(stats)
            st.session_state.stats = stats
            st.success(f"{nuovo} aggiunto!")
            st.rerun()
        elif nuovo in stats:
            st.warning("Esiste già!")

    st.divider()

    # Rimuovi
    st.subheader("❌ Rimuovi Collega")
    tutti = sorted(list(stats.keys()))
    if tutti:
        da_rimuovere = st.selectbox("Seleziona chi eliminare:", tutti)
        if st.button("Elimina Giocatore", type="primary"):
            del stats[da_rimuovere]
            salva_statistiche(stats)
            st.session_state.stats = stats
            # Rimuoviamo anche dalla sessione se presente
            if da_rimuovere in st.session_state.partite_giocate_oggi:
                del st.session_state.partite_giocate_oggi[da_rimuovere]
            st.success(f"Rimosso {da_rimuovere}.")
            st.rerun()

# --- CONFIGURAZIONE NAVIGAZIONE ---
st.set_page_config(page_title="Calcietto Pro", page_icon="⚽", layout="centered")
pg = st.navigation([
    st.Page(pagina_generatore, title="Generatore Squadre", icon="⚽"),
    st.Page(pagina_gestione, title="Gestione Giocatori", icon="⚙️")
])
pg.run()