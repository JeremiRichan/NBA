import os
import sys
import logging
import time
import math
import pandas as pd
import numpy as np
from datetime import datetime


NEO4J_URI      = "neo4j://127.0.0.1:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password123"
DATA_DIR       = "../data" 
LOG_DIR        = "../logs"
os.makedirs(LOG_DIR, exist_ok=True)

BATCH_SIZE  = 500
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "04_load_relationships.log"), mode="w"),
    ],
)
log = logging.getLogger(__name__)


def get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def safe_val(v):
    if v is None:
        return None
    try:
        if math.isnan(float(v)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def executer_batch(session, cypher, params_list, desc):
    for tentative in range(1, MAX_RETRIES + 1):
        try:
            result = session.run(cypher, {"rows": params_list})
            summary = result.consume()
            return summary.counters.relationships_created
        except Exception as e:
            if tentative == MAX_RETRIES:
                log.error(f"  ✗ {desc} — abandon : {e}")
                raise
            delai = 1.0 * (2 ** (tentative - 1))
            log.warning(f"  ⚠ {desc} retry {tentative} dans {delai:.1f}s ({e})")
            time.sleep(delai)


def ingerer_relations(session, cypher, records, label, batch_size=BATCH_SIZE):
    total = len(records)
    nb_batches = math.ceil(total / batch_size)
    total_crees = 0
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        bn = i // batch_size + 1
        crees = executer_batch(session, cypher, batch, f"{label} {bn}/{nb_batches}")
        total_crees += crees
        if bn % 20 == 0 or bn == nb_batches:
            log.info(f"  {label}: {bn}/{nb_batches} batches ({min(100, round(bn/nb_batches*100))}%)")
    return total_crees


def compter_relations(session, type_rel):
    r = session.run(f"MATCH ()-[r:{type_rel}]->() RETURN count(r) AS c")
    return r.single()["c"]


#  RELATION 1 — Saison -[:CONTIENT]-> Match

def charger_rel_saison_match(session, games_df):
    log.info("--- Relation CONTIENT (Saison→Match) ---")
    nb_avant = compter_relations(session, "CONTIENT")

    records = [
        {"saison_id": str(int(row["SEASON"])), "match_id": str(int(row["GAME_ID"]))}
        for _, row in games_df.iterrows()
    ]

    cypher = """
    UNWIND $rows AS row
    MATCH (s:Saison {id: row.saison_id})
    MATCH (m:Match  {id: row.match_id})
    MERGE (s)-[:CONTIENT]->(m)
    """
    crees = ingerer_relations(session, cypher, records, "CONTIENT")
    nb_apres = compter_relations(session, "CONTIENT")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créées:{crees}")


#  RELATION 2 — Equipe -[:DISPUTE]-> Match (domicile)
#  RELATION 3 — Equipe -[:VISITE]->  Match (visiteur)
#  Direction sémantique : équipe → match
#  Propriétés : score, resultat (calculé depuis home_wins)

def charger_rel_equipe_match(session, games_df):
    log.info("--- Relations DISPUTE/VISITE (Equipe→Match) ---")
    nb_avant_d = compter_relations(session, "DISPUTE")
    nb_avant_v = compter_relations(session, "VISITE")

    records_dom = []
    records_vis = []

    for _, row in games_df.iterrows():
        mid       = str(int(row["GAME_ID"]))
        home_id   = str(int(row["HOME_TEAM_ID"]))
        away_id   = str(int(row["VISITOR_TEAM_ID"]))
        score_h   = safe_val(row["PTS_home"])
        score_a   = safe_val(row["PTS_away"])
        home_wins = safe_val(row["HOME_TEAM_WINS"])

        # Résultat calculé (pas stocké sur le Match — calculé ici pour la relation)
        if home_wins is not None:
            res_home = "victoire" if int(home_wins) == 1 else "defaite"
            res_away = "defaite"  if int(home_wins) == 1 else "victoire"
        else:
            res_home = None
            res_away = None

        records_dom.append({
            "equipe_id": home_id,
            "match_id":  mid,
            "score":     score_h,
            "resultat":  res_home,
        })
        records_vis.append({
            "equipe_id": away_id,
            "match_id":  mid,
            "score":     score_a,
            "resultat":  res_away,
        })

    cypher_dom = """
    UNWIND $rows AS row
    MATCH (e:Equipe {id: row.equipe_id})
    MATCH (m:Match  {id: row.match_id})
    MERGE (e)-[r:DISPUTE]->(m)
    ON CREATE SET r.score = row.score, r.resultat = row.resultat
    ON MATCH  SET r.score = COALESCE(row.score, r.score),
                  r.resultat = COALESCE(row.resultat, r.resultat)
    """
    cypher_vis = """
    UNWIND $rows AS row
    MATCH (e:Equipe {id: row.equipe_id})
    MATCH (m:Match  {id: row.match_id})
    MERGE (e)-[r:VISITE]->(m)
    ON CREATE SET r.score = row.score, r.resultat = row.resultat
    ON MATCH  SET r.score = COALESCE(row.score, r.score),
                  r.resultat = COALESCE(row.resultat, r.resultat)
    """
    crees_d = ingerer_relations(session, cypher_dom, records_dom, "DISPUTE")
    crees_v = ingerer_relations(session, cypher_vis, records_vis, "VISITE")

    log.info(f"  DISPUTE  — Avant:{nb_avant_d} | Après:{compter_relations(session,'DISPUTE')} | Créées:{crees_d}")
    log.info(f"  VISITE   — Avant:{nb_avant_v} | Après:{compter_relations(session,'VISITE')}  | Créées:{crees_v}")


#  RELATION 4 — Joueur -[:JOUE_POUR]-> Equipe
#  Relation TEMPORELLE : on stocke la saison
#  Un joueur peut avoir plusieurs relations (une par saison)
#  MERGE sur (joueur, equipe, saison) pour éviter doublons
def charger_rel_joueur_equipe(session, players_df):
    log.info("--- Relation JOUE_POUR (Joueur→Equipe, temporelle) ---")
    nb_avant = compter_relations(session, "JOUE_POUR")

    # Dédupliquer : un joueur peut apparaître plusieurs fois dans la même saison/équipe
    df_dedup = players_df.drop_duplicates(["PLAYER_ID", "TEAM_ID", "SEASON"])

    # Déterminer l'année max par joueur pour marquer actif=true
    max_saison_par_joueur = (
        players_df.groupby("PLAYER_ID")["SEASON"].max().to_dict()
    )

    records = []
    for _, row in df_dedup.iterrows():
        pid     = str(int(row["PLAYER_ID"]))
        tid     = str(int(row["TEAM_ID"]))
        saison  = int(row["SEASON"])
        actif   = (saison == max_saison_par_joueur.get(int(row["PLAYER_ID"]), -1))
        records.append({
            "joueur_id": pid,
            "equipe_id": tid,
            "saison":    saison,
            "actif":     actif,
        })

    # MERGE sur les trois clés pour préserver l'historique complet
    cypher = """
    UNWIND $rows AS row
    MATCH (j:Joueur {id: row.joueur_id})
    MATCH (e:Equipe {id: row.equipe_id})
    MERGE (j)-[r:JOUE_POUR {saison: row.saison}]->(e)
    ON CREATE SET
        r.actif      = row.actif,
        r.created_at = datetime()
    ON MATCH SET
        r.actif      = row.actif,
        r.updated_at = datetime()
    """
    crees = ingerer_relations(session, cypher, records, "JOUE_POUR")
    nb_apres = compter_relations(session, "JOUE_POUR")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créées:{crees}")


#  RELATIONS 5, 6, 7 — Joueur→Performance→Match→Equipe
#  Ces trois relations sont créées ensemble (atomicité par batch)
def charger_rel_performance(session, details_df):
    log.info("--- Relations REALISE / LORS_DE / POUR_EQUIPE ---")
    nb_av_r = compter_relations(session, "REALISE")
    nb_av_l = compter_relations(session, "LORS_DE")
    nb_av_p = compter_relations(session, "POUR_EQUIPE")

    df_joue = details_df[details_df["a_joue"] == True]

    records = []
    for _, row in df_joue.iterrows():
        gid     = str(int(row["GAME_ID"]))
        pid     = str(int(row["PLAYER_ID"]))
        tid     = str(int(row["TEAM_ID"]))
        perf_id = f"{row['PLAYER_ID']}_{row['GAME_ID']}"
        records.append({
            "joueur_id":  pid,
            "perf_id":    perf_id,
            "match_id":   gid,
            "equipe_id":  tid,
        })

    # On crée les 3 relations en une seule requête UNWIND pour l'atomicité
    cypher = """
    UNWIND $rows AS row
    MATCH (j:Joueur      {id: row.joueur_id})
    MATCH (p:Performance {id: row.perf_id})
    MATCH (m:Match       {id: row.match_id})
    MATCH (e:Equipe      {id: row.equipe_id})
    MERGE (j)-[:REALISE]->(p)
    MERGE (p)-[:LORS_DE]->(m)
    MERGE (p)-[:POUR_EQUIPE]->(e)
    """
    # Cette requête crée 3 relations par ligne, mais counters retourne le total
    crees = ingerer_relations(session, cypher, records, "REALISE+LORS_DE+POUR_EQUIPE", batch_size=300)

    log.info(f"  REALISE    — Avant:{nb_av_r} | Après:{compter_relations(session,'REALISE')}")
    log.info(f"  LORS_DE    — Avant:{nb_av_l} | Après:{compter_relations(session,'LORS_DE')}")
    log.info(f"  POUR_EQUIPE— Avant:{nb_av_p} | Après:{compter_relations(session,'POUR_EQUIPE')}")


#  RELATION 8 — Equipe -[:A_CLASSEMENT]-> Classement

def charger_rel_equipe_classement(session, ranking_df):
    log.info("--- Relation A_CLASSEMENT (Equipe→Classement) ---")
    nb_avant = compter_relations(session, "A_CLASSEMENT")

    records = []
    for _, row in ranking_df.iterrows():
        tid    = str(int(row["TEAM_ID"]))
        date_v = row["STANDINGSDATE"]
        if pd.isna(date_v):
            continue
        date_str = date_v.strftime("%Y-%m-%d") if isinstance(date_v, pd.Timestamp) else str(date_v)[:10]
        cl_id    = f"{int(row['TEAM_ID'])}_{date_str}"
        records.append({"equipe_id": tid, "classement_id": cl_id})

    cypher = """
    UNWIND $rows AS row
    MATCH (e:Equipe     {id: row.equipe_id})
    MATCH (c:Classement {id: row.classement_id})
    MERGE (e)-[:A_CLASSEMENT]->(c)
    """
    crees = ingerer_relations(session, cypher, records, "A_CLASSEMENT", batch_size=1000)
    nb_apres = compter_relations(session, "A_CLASSEMENT")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créées:{crees}")


def main():
    log.info("=" * 60)
    log.info("ÉTAPE 4 — INGESTION DES RELATIONS")
    log.info("=" * 60)
    start = datetime.now()

    log.info("Chargement des données nettoyées...")
    parquet_dir = os.path.join(DATA_DIR, "logs")

    games_df   = pd.read_parquet(os.path.join(parquet_dir, "games_clean.parquet"))
    details_df = pd.read_parquet(os.path.join(parquet_dir, "details_clean.parquet"))
    players_df = pd.read_parquet(os.path.join(parquet_dir, "players_clean.parquet"))
    ranking_df = pd.read_parquet(os.path.join(parquet_dir, "ranking_clean.parquet"))

    driver = get_driver()
    with driver.session() as session:
        charger_rel_saison_match(session, games_df)         # Saison → Match
        charger_rel_equipe_match(session, games_df)         # Equipe → Match (dom + vis)
        charger_rel_joueur_equipe(session, players_df)      # Joueur → Equipe
        charger_rel_performance(session, details_df)        # Joueur → Perf → Match → Equipe
        charger_rel_equipe_classement(session, ranking_df)  # Equipe → Classement

    driver.close()

    duree = (datetime.now() - start).total_seconds()
    log.info("=" * 60)
    log.info(f"ÉTAPE 4 TERMINÉE en {duree:.0f}s ({duree/60:.1f} min)")
    log.info("Prochaine étape : python valider_graphe.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
