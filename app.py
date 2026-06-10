import streamlit as st
import random
import json
import os
import uuid
from github import Github

# --- CONFIGURAZIONE ---
FILE_STATISTICHE = 'statistiche.json'
FILE_PRESENTI = 'presenti.json' # REINSERITO PER MEMORIA A LUNGO TERMINE

GIOCATORI_DEFAULT = [
    "Lorenzo", "Luca", "Giovanni", "Alexander", "Alessandro"
]

# --- FUNZIONI GITHUB E SALVATAGGIO ---
def usa_github():
    return "GITHUB_TOKEN" in st.secrets and "REPO_NAME" in st.secrets

def carica_da_github(nome_file, default_data):
    if usa_github():
        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo(st.secrets["REPO_NAME"])
            contents = repo.get_contents(nome_file)
            return json.loads(contents.decoded_content.decode("utf-8"))
        except Exception:
            return default_data
    else:
        if os.path.exists(nome_file):
            with open(nome_file, 'r') as f:
                return json.load(f)
        return default_data

def salva_su_github(nome_file, dati):
    if usa_github():
        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo(st.secrets["REPO_NAME"])
            try:
                contents = repo.get_contents(nome_file)
                repo.update_file(contents.path, f"Aggiornamento {nome_file}", json.dumps(dati, indent=4), contents.sha)
            except Exception:
                repo.create_file(nome_file, f"Creazione {nome_file}", json.dumps(dati, indent=4))
        except Exception as e:
            st.error(f"Errore nel salvataggio su GitHub: {e}")
    else:
        with open(nome_file, 'w') as f:
            json.dump(dati, f, indent=4)

# --- FUNZIONI DI SUPPORTO SPECIFICHE ---
def carica_statistiche():
    default_stats = {g: {"ruolo": "Indifferente", "vinte": 0, "perse": 0, "elo": 1200} for g in GIOCATORI_DEFAULT}
    stats = carica_da_github(FILE_STATISTICHE, default_stats)
    
    for k, v in stats.items():
        if isinstance(v, int):
            stats[k] = {"ruolo": "Indifferente", "vinte": 0, "perse": 0, "elo": 1200}
        elif "elo" not in v:
            stats[k]["elo"] = 1200
            
    if stats == default_stats and not usa_github() and not os.path.exists(FILE_STATISTICHE):
        salva_su_github(FILE_STATISTICHE, stats)
        
    return stats

def carica_presenti(tutti_i_giocatori):
    lista = carica_da_github(FILE_PRESENTI, tutti_i_giocatori.copy())
    validi = [g for g in lista if g in tutti_i_giocatori]
    return validi if validi else tutti_i_giocatori.copy()

# --- INIZIALIZZAZIONE STATI (MEMORIA EFFIMERA) ---
if 'stats' not in st.session_state:
    st.session_state.stats = carica_statistiche()
if 'storico_squadre_oggi' not in st.session_state:
    st.session_state.storico_squadre_oggi = []
if 'partite_giocate_oggi' not in st.session_state:
    st.session_state.partite_giocate_oggi = {}
if 'coppie_giocate_oggi' not in st.session_state:
    st.session_state.coppie_giocate_oggi = set()

# Recupera la lista dei giocatori presenti per la memoria persistente
tutti_i_gioc_iniziali = sorted(list(st.session_state.stats.keys()))
if 'default_presenti' not in st.session_state:
    st.session_state.default_presenti = carica_presenti(tutti_i_gioc_iniziali)
# Conserva un backup per capire quando è il momento di salvare
if 'presenti_salvati' not in st.session_state:
    st.session_state.presenti_salvati = st.session_state.default_presenti.copy()


# --- ALGORITMI E MOTORE (SISTEMA ELO) ---
def aggiorna_elo(vincenti, perdenti):
    K = 40 
    
    elo_v = (st.session_state.stats[vincenti[0]].get("elo", 1200) + st.session_state.stats[vincenti[1]].get("elo", 1200)) / 2
    elo_p = (st.session_state.stats[perdenti[0]].get("elo", 1200) + st.session_state.stats[perdenti[1]].get("elo", 1200)) / 2

    prob_v = 1 / (1 + 10 ** ((elo_p - elo_v) / 400))
    prob_p = 1 / (1 + 10 ** ((elo_v - elo_p) / 400))

    delta_v = K * (1 - prob_v)
    delta_p = K * (0 - prob_p)

    for g in vincenti:
        st.session_state.stats[g]["elo"] = st.session_state.stats[g].get("elo", 1200) + delta_v
    for g in perdenti:
        st.session_state.stats[g]["elo"] = st.session_state.stats[g].get("elo", 1200) + delta_p

def valuta_formazione(sq1, sq2):
    penalita = 0
    
    elo_sq1 = (st.session_state.stats[sq1[0]].get("elo", 1200) + st.session_state.stats[sq1[1]].get("elo", 1200)) / 2
    elo_sq2 = (st.session_state.stats[sq2[0]].get("elo", 1200) + st.session_state.stats[sq2[1]].get("elo", 1200)) / 2
    penalita += abs(elo_sq1 - elo_sq2) 
    
    def conta_ruolo(sq, r):
        return sum(1 for g in sq if st.session_state.stats[g].get("ruolo", "Indifferente") == r)
    
    if conta_ruolo(sq1, "Difesa") == 2 or conta_ruolo(sq2, "Difesa") == 2: penalita += 500
    if conta_ruolo(sq1, "Attaccante") == 2 or conta_ruolo(sq2, "Attaccante") == 2: penalita += 150
    if sq1 in st.session_state.coppie_giocate_oggi or sq2 in st.session_state.coppie_giocate_oggi: penalita += 5000
    return penalita

def registra_vittoria(match, squadra_vincente):
    match["risolta"] = True
    match["vincitrice"] = squadra_vincente
    vincenti = match["sq1"] if squadra_vincente == 1 else match["sq2"]
    perdenti = match["sq2"] if squadra_vincente == 1 else match["sq1"]
    
    aggiorna_elo(vincenti, perdenti)
    
    for g in vincenti: st.session_state.stats[g]["vinte"] += 1
    for g in perdenti: st.session_state.stats[g]["perse"] += 1
    
    # COMMIT DELLA CLASSIFICA
    salva_su_github(FILE_STATISTICHE, st.session_state.stats)

    # SMART COMMIT: Salva i presenti SOLO se sono cambiati dall'ultima partita!
    if st.session_state.default_presenti != st.session_state.presenti_salvati:
        salva_su_github(FILE_PRESENTI, st.session_state.default_presenti)
        st.session_state.presenti_salvati = st.session_state.default_presenti.copy()

def scarta_partita(match):
    st.session_state.storico_squadre_oggi.remove(match)
    for g in match["sq1"] + match["sq2"]:
        st.session_state.partite_giocate_oggi[g] -= 1
    st.session_state.coppie_giocate_oggi.discard(match["sq1"])
    st.session_state.coppie_giocate_oggi.discard(match["sq2"])


# --- PAGINA 1: GENERATORE ---
def pagina_generatore():
    st.title("Generatore Calcio Balilla")
    if usa_github():
        st.caption("🟢 Connesso al Database Cloud")
    else:
        st.caption("🟡 Modalità Locale")

    st.write("Seleziona i presenti. Il sistema darà priorità a chi ha giocato meno oggi.")
    tutti_i_giocatori = sorted(list(st.session_state.stats.keys()))

    if not tutti_i_giocatori:
        st.info("Vai nella pagina 'Gestione Giocatori' per aggiungere i colleghi.")
        return

    for g in tutti_i_giocatori:
        if g not in st.session_state.partite_giocate_oggi:
            st.session_state.partite_giocate_oggi[g] = 0

    # Rimuove dalla selezione eventuali giocatori appena cancellati dal DB
    st.session_state.default_presenti = [g for g in st.session_state.default_presenti if g in tutti_i_giocatori]

    presenti_oggi = st.multiselect("Chi gioca oggi?", options=tutti_i_giocatori, default=st.session_state.default_presenti)
    
    # Aggiorna la memoria RAM con le tue scelte a schermo (saranno committate solo a fine partita)
    st.session_state.default_presenti = presenti_oggi
    
    usa_ranking = st.toggle("⚖️ Bilancia squadre (Livello Elo e Ruoli)", value=True)
    st.divider()

    if st.button("🎲 Genera Prossima Partita (2 vs 2)", use_container_width=True, type="primary"):
        if len(presenti_oggi) < 4:
            st.warning("Servono almeno 4 giocatori per fare una partita.")
        else:
            presenti_mischati = random.sample(presenti_oggi, len(presenti_oggi))
            presenti_ordinati = sorted(presenti_mischati, key=lambda x: st.session_state.partite_giocate_oggi.get(x, 0))
            P = presenti_ordinati[:4]
            random.shuffle(P) 
            
            squadra_a, squadra_b = tuple(), tuple()

            if usa_ranking:
                combinazioni = [
                    (tuple(sorted([P[0], P[1]])), tuple(sorted([P[2], P[3]]))),
                    (tuple(sorted([P[0], P[2]])), tuple(sorted([P[1], P[3]]))),
                    (tuple(sorted([P[0], P[3]])), tuple(sorted([P[1], P[2]])))
                ]
                miglior_formazione = min(combinazioni, key=lambda f: valuta_formazione(f[0], f[1]))
                squadra_a, squadra_b = miglior_formazione
            else:
                tentativi = 0
                while tentativi < 50:
                    random.shuffle(P)
                    tentativo_a = tuple(sorted(P[:2]))
                    tentativo_b = tuple(sorted(P[2:]))
                    if (tentativo_a not in st.session_state.coppie_giocate_oggi) and (tentativo_b not in st.session_state.coppie_giocate_oggi):
                        squadra_a, squadra_b = tentativo_a, tentativo_b
                        break
                    tentativi += 1
                if not squadra_a:
                    squadra_a, squadra_b = tuple(sorted(P[:2])), tuple(sorted(P[2:]))

            st.session_state.coppie_giocate_oggi.add(squadra_a)
            st.session_state.coppie_giocate_oggi.add(squadra_b)
            
            nuovo_match = {"id": str(uuid.uuid4()), "sq1": squadra_a, "sq2": squadra_b, "risolta": False, "vincitrice": None}
            st.session_state.storico_squadre_oggi.append(nuovo_match)

            for giocatore in squadra_a + squadra_b:
                st.session_state.partite_giocate_oggi[giocatore] += 1
            st.rerun()

    st.subheader("📝 Partite della Sessione Odierna")
    if st.session_state.storico_squadre_oggi:
        for match in reversed(st.session_state.storico_squadre_oggi):
            elo_sq1_g1 = int(st.session_state.stats[match["sq1"][0]].get("elo", 1200))
            elo_sq1_g2 = int(st.session_state.stats[match["sq1"][1]].get("elo", 1200))
            elo_sq2_g1 = int(st.session_state.stats[match["sq2"][0]].get("elo", 1200))
            elo_sq2_g2 = int(st.session_state.stats[match["sq2"][1]].get("elo", 1200))
            
            media_sq1 = int((elo_sq1_g1 + elo_sq1_g2) / 2)
            media_sq2 = int((elo_sq2_g1 + elo_sq2_g2) / 2)
            
            sq1_str = f"{match['sq1'][0]} ({elo_sq1_g1} pt) e {match['sq1'][1]} ({elo_sq1_g2} pt)"
            sq2_str = f"{match['sq2'][0]} ({elo_sq2_g1} pt) e {match['sq2'][1]} ({elo_sq2_g2} pt)"
            
            with st.container(border=True):
                st.write(f"🔵 **Squadra 1 (Media: {media_sq1} pt):** {sq1_str}  \n🔴 **Squadra 2 (Media: {media_sq2} pt):** {sq2_str}")
                if not match["risolta"]:
                    colA, colB, colC = st.columns(3)
                    if colA.button("🏆 Vince Sq. 1", key=f"v1_{match['id']}", use_container_width=True):
                        with st.spinner("Salvataggio su Cloud..."):
                            registra_vittoria(match, 1)
                        st.rerun()
                    if colB.button("🏆 Vince Sq. 2", key=f"v2_{match['id']}", use_container_width=True):
                        with st.spinner("Salvataggio su Cloud..."):
                            registra_vittoria(match, 2)
                        st.rerun()
                    if colC.button("❌ Scarta", key=f"sc_{match['id']}", use_container_width=True):
                        scarta_partita(match)
                        st.rerun()
                else:
                    vincitrice_str = "Squadra 1" if match["vincitrice"] == 1 else "Squadra 2"
                    st.success(f"Conclusa. Ha vinto la **{vincitrice_str}**", icon=None)
    else:
        st.write("Nessuna partita generata in questa sessione.")
    
    st.write("") 
    if st.button("♻️ Azzera Sessione Odierna", use_container_width=True):
        st.session_state.storico_squadre_oggi = []
        st.session_state.coppie_giocate_oggi.clear()
        for g in st.session_state.partite_giocate_oggi:
            st.session_state.partite_giocate_oggi[g] = 0
        st.success("Sessione azzerata. Contatori di oggi e coppie resettate.", icon=None)
        st.rerun()
    
    st.caption("💡 *Questo tasto serve solo a svuotare la lista dei match sullo schermo, resettare i contatori delle partite fatte oggi e azzerare la memoria di chi ha già fatto coppia con chi per fare nuove rotazioni dei presenti. **NON cancella** la classifica globale.*")


# --- PAGINA 2: CLASSIFICA ---
def pagina_classifica():
    st.title("🏆 Classifica Elo")
    st.write("Sistema di ranking avanzato: sconfiggere avversari forti conferisce più punti.")
    stats = st.session_state.stats
    if not stats:
        st.info("Nessun giocatore registrato.")
        return

    classifica = []
    for giocatore, dati in stats.items():
        vinte = dati.get("vinte", 0)
        perse = dati.get("perse", 0)
        totali = vinte + perse
        win_rate = (vinte / totali * 100) if totali > 0 else 0.0
        elo = dati.get("elo", 1200)
        classifica.append({"nome": giocatore, "win_rate": win_rate, "totali": totali, "vinte": vinte, "perse": perse, "elo": elo})

    classifica_ordinata = sorted(classifica, key=lambda x: (x["elo"], x["vinte"]), reverse=True)
    giocatori_attivi = [p for p in classifica_ordinata if p["totali"] > 0]
    giocatori_inattivi = [p for p in classifica_ordinata if p["totali"] == 0]

    st.divider()

    if giocatori_attivi:
        for i, p in enumerate(giocatori_attivi):
            pos = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
            with st.container():
                st.markdown(f"### {pos} {p['nome']} - {p['elo']:.0f} pt")
                st.caption(f"Vittorie: {p['vinte']} | Sconfitte: {p['perse']} (Win-Rate: {p['win_rate']:.1f}%)")
                st.divider()
    else:
        st.info("Non è stata ancora registrata nessuna vittoria.")

    if giocatori_inattivi:
        st.write("👤 **Ancora nessuna partita registrata (1200 pt base):**")
        st.write(", ".join([p["nome"] for p in giocatori_inattivi]))


# --- PAGINA 3: GESTIONE ---
def aggiungi_giocatore():
    nuovo = st.session_state.input_nome.strip()
    if nuovo and nuovo not in st.session_state.stats:
        st.session_state.stats[nuovo] = {"ruolo": "Indifferente", "vinte": 0, "perse": 0, "elo": 1200}
        salva_su_github(FILE_STATISTICHE, st.session_state.stats)
        
        if 'partite_giocate_oggi' in st.session_state:
            st.session_state.partite_giocate_oggi[nuovo] = 0
            
        if 'default_presenti' in st.session_state and nuovo not in st.session_state.default_presenti:
            st.session_state.default_presenti.append(nuovo)
            salva_su_github(FILE_PRESENTI, st.session_state.default_presenti)
            st.session_state.presenti_salvati = st.session_state.default_presenti.copy()
            
        st.session_state.msg_success = f"{nuovo} aggiunto!"
        st.session_state.input_nome = "" 
    elif nuovo in st.session_state.stats:
        st.session_state.msg_warning = "Esiste gia'!"

def pagina_gestione():
    st.title("⚙️ Gestione Colleghi")
    stats = st.session_state.stats
    tutti = sorted(list(stats.keys()))

    if "msg_success" in st.session_state:
        st.success(st.session_state.msg_success, icon=None); del st.session_state.msg_success
    if "msg_warning" in st.session_state:
        st.warning(st.session_state.msg_warning, icon=None); del st.session_state.msg_warning

    st.subheader("👥 Colleghi Attualmente Registrati")
    if tutti:
        st.write(f"Totale nel database: **{len(tutti)}**")
        col_A, col_B, col_C = st.columns(3)
        for indice, giocatore in enumerate(tutti):
            ruolo = stats[giocatore].get("ruolo", "Indifferente")
            testo = f"• **{giocatore}** ({ruolo[:3]})"
            if indice % 3 == 0: col_A.markdown(testo)
            elif indice % 3 == 1: col_B.markdown(testo)
            else: col_C.markdown(testo)
    else:
        st.info("Nessun giocatore presente nella lista.", icon=None)

    st.divider()

    st.subheader("Aggiungi Nuovo Collega")
    if "input_nome" not in st.session_state: st.session_state.input_nome = ""
    st.text_input("Nome:", key="input_nome", on_change=aggiungi_giocatore)
    st.button("Aggiungi", on_click=aggiungi_giocatore)

    st.divider()

    st.subheader("Modifica Preferenza Ruolo")
    if tutti:
        g_sel = st.selectbox("Seleziona giocatore:", tutti)
        ruolo_attuale = stats[g_sel].get("ruolo", "Indifferente")
        nuovo_ruolo = st.radio("Ruolo in campo:", ["Attaccante", "Difesa", "Indifferente"], index=["Attaccante", "Difesa", "Indifferente"].index(ruolo_attuale))
        if st.button("Aggiorna Ruolo"):
            stats[g_sel]["ruolo"] = nuovo_ruolo
            salva_su_github(FILE_STATISTICHE, stats)
            st.session_state.msg_success = f"Ruolo di {g_sel} aggiornato!"
            st.rerun()
    else:
        st.info("Nessun giocatore registrato.")

    st.divider()

    st.subheader("Rimuovi Collega")
    if tutti:
        da_rimuovere = st.selectbox("Seleziona chi eliminare dalla lista permanente:", tutti)
        if st.button("Elimina Giocatore"):
            del stats[da_rimuovere]
            salva_su_github(FILE_STATISTICHE, stats)
            if da_rimuovere in st.session_state.partite_giocate_oggi:
                del st.session_state.partite_giocate_oggi[da_rimuovere]
            
            if 'default_presenti' in st.session_state and da_rimuovere in st.session_state.default_presenti:
                st.session_state.default_presenti.remove(da_rimuovere)
                salva_su_github(FILE_PRESENTI, st.session_state.default_presenti)
                st.session_state.presenti_salvati = st.session_state.default_presenti.copy()
                
            st.session_state.msg_success = f"Rimosso {da_rimuovere}."
            st.rerun()


# --- CONFIGURAZIONE NAVIGAZIONE ---
st.set_page_config(page_title="Calcio Balilla", layout="centered", page_icon="⚽")
pg = st.navigation([
    st.Page(pagina_generatore, title="Generatore Partite", icon="⚽"),
    st.Page(pagina_classifica, title="Classifica", icon="🏆"),
    st.Page(pagina_gestione, title="Gestione Giocatori", icon="⚙️")
])
pg.run()