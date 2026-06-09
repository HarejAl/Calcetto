import streamlit as st
import random
import json
import os

# --- CONFIGURAZIONE ---
FILE_STATISTICHE = 'statistiche.json'
FILE_PRESENTI = 'presenti.json'

GIOCATORI_DEFAULT = [
    "Lorenzo", "Luca", "Giovanni", "Alexander", "Alessandro"
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

def carica_presenti(tutti_i_giocatori):
    if os.path.exists(FILE_PRESENTI):
        try:
            with open(FILE_PRESENTI, 'r') as f:
                lista = json.load(f)
                validi = [g for g in lista if g in tutti_i_giocatori]
                return validi if validi else tutti_i_giocatori.copy()
        except:
            return tutti_i_giocatori.copy()
    return tutti_i_giocatori.copy()

def salva_presenti(lista):
    with open(FILE_PRESENTI, 'w') as f:
        json.dump(lista, f)

# --- INIZIALIZZAZIONE STATI (MEMORIA) ---
if 'stats' not in st.session_state:
    st.session_state.stats = carica_statistiche()

if 'storico_squadre_oggi' not in st.session_state:
    st.session_state.storico_squadre_oggi = []

if 'partite_giocate_oggi' not in st.session_state:
    st.session_state.partite_giocate_oggi = {}

if 'coppie_giocate_oggi' not in st.session_state:
    st.session_state.coppie_giocate_oggi = set()

# --- PAGINA 1: GENERATORE BILIARDINO ---
def pagina_generatore():
    st.title("Generatore Calcio Balilla")
    st.write("Seleziona i presenti. L'algoritmo calcolera' le squadre in background basandosi sullo storico, privilegiando chi ha giocato meno.")

    stats = st.session_state.stats
    tutti_i_giocatori = sorted(list(stats.keys()))

    if not tutti_i_giocatori:
        st.info("Vai nella pagina 'Gestione Giocatori' per aggiungere i colleghi.", icon=None)
        return

    # Inizializza i contatori odierni
    for g in tutti_i_giocatori:
        if g not in st.session_state.partite_giocate_oggi:
            st.session_state.partite_giocate_oggi[g] = 0

    presenti_salvati = carica_presenti(tutti_i_giocatori)

    presenti_oggi = st.multiselect(
        "Chi gioca oggi?", 
        options=tutti_i_giocatori, 
        default=presenti_salvati
    )
    
    salva_presenti(presenti_oggi)

    st.divider()

    if st.button("Genera Prossima Partita (2 vs 2)", use_container_width=True, type="primary"):
        if len(presenti_oggi) < 4:
            st.warning("Servono almeno 4 giocatori per fare una partita.", icon=None)
        else:
            tentativi = 0
            squadra_a, squadra_b = [], []
            
            while tentativi < 100:
                presenti_mischati = random.sample(presenti_oggi, len(presenti_oggi))
                
                presenti_ordinati = sorted(
                    presenti_mischati, 
                    key=lambda x: st.session_state.partite_giocate_oggi.get(x, 0)
                )
                
                i_quattro_eletti =Screen = presenti_ordinati[:4]
                
                random.shuffle(i_quattro_eletti)
                tentativo_a = tuple(sorted(i_quattro_eletti[:2]))
                tentativo_b = tuple(sorted(i_quattro_eletti[2:]))
                
                if (tentativo_a not in st.session_state.coppie_giocate_oggi) and (tentativo_b not in st.session_state.coppie_giocate_oggi):
                    squadra_a, squadra_b = tentativo_a, tentativo_b
                    st.session_state.coppie_giocate_oggi.add(squadra_a)
                    st.session_state.coppie_giocate_oggi.add(squadra_b)
                    st.session_state.storico_squadre_oggi.append((squadra_a, squadra_b))
                    break
                
                tentativi += 1

            if not squadra_a:
                squadra_a, squadra_b = tentativo_a, tentativo_b
                st.session_state.storico_squadre_oggi.append((squadra_a, squadra_b))

            for giocatore in squadra_a + squadra_b:
                st.session_state.partite_giocate_oggi[giocatore] += 1
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Squadra 1")
                for g in squadra_a: st.write(g)
            with col2:
                st.subheader("Squadra 2")
                for g in squadra_b: st.write(g)

    st.divider()

    # MOSTRIAMO LE PARTITE DELLA SESSIONE ODIERNA (DA SOTTO IN SU)
    st.subheader("Partite della Sessione Odierna")
    if st.session_state.storico_squadre_oggi:
        for match in reversed(st.session_state.storico_squadre_oggi):
            squadra_1 = " e ".join(match[0])
            squadra_2 = " e ".join(match[1])
            st.write(f"{squadra_1} **VS** {squadra_2}")
    else:
        st.write("Nessuna partita generata in questa sessione.")
    
    st.write("") 
    if st.button("Azzera Sessione Odierna", use_container_width=True):
        st.session_state.storico_squadre_oggi = []
        st.session_state.coppie_giocate_oggi.clear()
        for g in st.session_state.partite_giocate_oggi:
            st.session_state.partite_giocate_oggi[g] = 0
        st.success("Sessione azzerata. Contatori di oggi e coppie resettate.", icon=None)
        st.rerun()


# --- CALLBACK PER AGGIUNGERE GIOCATORE ---
def aggiungi_giocatore():
    nuovo = st.session_state.input_nome.strip()
    if nuovo and nuovo not in st.session_state.stats:
        st.session_state.stats[nuovo] = 0
        salva_statistiche(st.session_state.stats)
        
        if 'partite_giocate_oggi' in st.session_state:
            st.session_state.partite_giocate_oggi[nuovo] = 0
            
        if os.path.exists(FILE_PRESENTI):
            try:
                with open(FILE_PRESENTI, 'r') as f:
                    lista = json.load(f)
            except:
                lista = []
        else:
            lista = list(st.session_state.stats.keys())
        
        if nuovo not in lista:
            lista.append(nuovo)
            salva_presenti(lista)
            
        st.session_state.msg_success = f"{nuovo} aggiunto!"
        st.session_state.input_nome = "" 
    elif nuovo in st.session_state.stats:
        st.session_state.msg_warning = "Esiste gia'!"

# --- PAGINA 2: GESTIONE GIOCATORI ---
def pagina_gestione():
    st.title("Gestione Colleghi")
    stats = st.session_state.stats
    tutti = sorted(list(stats.keys()))

    if "msg_success" in st.session_state:
        st.success(st.session_state.msg_success, icon=None)
        del st.session_state.msg_success
    if "msg_warning" in st.session_state:
        st.warning(st.session_state.msg_warning, icon=None)
        del st.session_state.msg_warning

    # --- NUOVA SEZIONE ELENCO GIOCATORI ---
    st.subheader("Colleghi Attualmente Registrati")
    if tutti:
        st.write(f"Totale nel database: **{len(tutti)}**")
        
        # Genera una griglia a 3 colonne
        col_A, col_B, col_C = st.columns(3)
        for indice, giocatore in enumerate(tutti):
            # Distribuisce i nomi equamente tra le colonne
            if indice % 3 == 0:
                col_A.write(f"• {giocatore}")
            elif indice % 3 == 1:
                col_B.write(f"• {giocatore}")
            else:
                col_C.write(f"• {giocatore}")
    else:
        st.info("Nessun giocatore presente nella lista.", icon=None)

    st.divider()

    st.subheader("Aggiungi Nuovo Collega")
    
    if "input_nome" not in st.session_state:
        st.session_state.input_nome = ""

    st.text_input("Nome:", key="input_nome", on_change=aggiungi_giocatore)
    st.button("Aggiungi", on_click=aggiungi_giocatore)

    st.divider()

    st.subheader("Rimuovi Collega")
    if tutti:
        da_rimuovere = st.selectbox("Seleziona chi eliminare:", tutti)
        if st.button("Elimina Giocatore"):
            del stats[da_rimuovere]
            salva_statistiche(stats)
            st.session_state.stats = stats
            if da_rimuovere in st.session_state.partite_giocate_oggi:
                del st.session_state.partite_giocate_oggi[da_rimuovere]
            
            st.session_state.msg_success = f"Rimosso {da_rimuovere}."
            st.rerun()

# --- CONFIGURAZIONE NAVIGAZIONE ---
st.set_page_config(page_title="Calcio Balilla", layout="centered")
pg = st.navigation([
    st.Page(pagina_generatore, title="Generatore Partite"),
    st.Page(pagina_gestione, title="Gestione Giocatori")
])
pg.run()