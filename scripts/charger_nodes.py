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

BATCH_SIZE     = 500    # lignes par transaction 
MAX_RETRIES    = 3      # tentatives avant abandon définitif
RETRY_DELAY    = 1.0    # délai initial en secondes (doublé à chaque retry)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "03_load_nodes.log"), mode="w"),
    ],
)
log = logging.getLogger(__name__)


def get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def safe_val(v):
    """Convertit NaN/NaT en None pour Neo4j."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return None
    return v


def row_to_dict_safe(row_dict):
    """Convertit toutes les valeurs d'un dict de ligne pandas en types Neo4j-compatibles."""
    clean = {}
    for k, v in row_dict.items():
        if isinstance(v, (np.integer,)):
            clean[k] = int(v)
        elif isinstance(v, (np.floating,)):
            clean[k] = None if math.isnan(v) else float(v)
        elif isinstance(v, pd.Timestamp):
            clean[k] = v.isoformat() if not pd.isna(v) else None
        else:
            clean[k] = safe_val(v)
    return clean


def executer_batch(session, cypher, params_list, description="batch"):
    for tentative in range(1, MAX_RETRIES + 1):
        try:
            result = session.run(cypher, {"rows": params_list})
            summary = result.consume()
            return summary.counters.nodes_created, summary.counters.properties_set
        except Exception as e:
            if tentative == MAX_RETRIES:
                log.error(f"  ✗ {description} — échec définitif après {MAX_RETRIES} tentatives : {e}")
                raise
            delai = RETRY_DELAY * (2 ** (tentative - 1))
            log.warning(f"  ⚠ {description} tentative {tentative} échouée ({e}) — retry dans {delai:.1f}s")
            time.sleep(delai)


def ingerer_par_batch(session, cypher, records, label, batch_size=BATCH_SIZE):
    total_records = len(records)
    total_crees = 0
    total_props = 0
    nb_batches = math.ceil(total_records / batch_size)

    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = i // batch_size + 1
        created, props = executer_batch(session, cypher, batch, f"{label} batch {batch_num}/{nb_batches}")
        total_crees += created
        total_props += props

        if batch_num % 10 == 0 or batch_num == nb_batches:
            pct = min(100, round(batch_num / nb_batches * 100))
            log.info(f"  {label}: {batch_num}/{nb_batches} batches ({pct}%)")

    return total_crees, total_props


def compter_noeuds(session, label):
    result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
    return result.single()["c"]


#  NŒUD 1 — SAISON

def charger_saisons(session, games_df, players_df):
    log.info("--- Nœuds Saison ---")
    nb_avant = compter_noeuds(session, "Saison")

    # Extraire les saisons uniques de games et players
    saisons_games   = set(games_df["SEASON"].dropna().unique())
    saisons_players = set(players_df["SEASON"].dropna().unique())
    toutes_saisons  = saisons_games | saisons_players

    records = [
        {
            "id":    str(int(s)),
            "annee": int(s),
        }
        for s in sorted(toutes_saisons)
    ]

    cypher = """
    UNWIND $rows AS row
    MERGE (s:Saison {id: row.id})
    ON CREATE SET
        s.annee      = row.annee,
        s.created_at = datetime()
    ON MATCH SET
        s.updated_at = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Saison")

    nb_apres = compter_noeuds(session, "Saison")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total saisons:{len(records)}")

#  NŒUD 2 — EQUIPE
def charger_equipes(session, games_df, details_df, ranking_df):
    log.info("--- Nœuds Equipe ---")
    nb_avant = compter_noeuds(session, "Equipe")

    # Construire le référentiel d'équipes depuis games + details + ranking
    equipes = {}

    # Source 1 : games (HOME_TEAM_ID et VISITOR_TEAM_ID)
    for _, row in games_df.iterrows():
        for col_id in ["HOME_TEAM_ID", "VISITOR_TEAM_ID"]:
            tid = int(row[col_id])
            if tid not in equipes:
                equipes[tid] = {"id": str(tid), "team_id": tid}

    # Source 2 : details (TEAM_ABBREVIATION + TEAM_CITY — données plus riches)
    for _, row in details_df.drop_duplicates("TEAM_ID").iterrows():
        tid = int(row["TEAM_ID"])
        if tid in equipes:
            equipes[tid]["abbreviation"] = safe_val(row.get("TEAM_ABBREVIATION"))
            equipes[tid]["ville"]        = safe_val(row.get("TEAM_CITY"))

    # Source 3 : ranking (TEAM nom + CONFERENCE)
    for _, row in ranking_df.drop_duplicates("TEAM_ID").iterrows():
        tid = int(row["TEAM_ID"])
        if tid in equipes:
            equipes[tid]["nom"]        = safe_val(row.get("TEAM"))
            equipes[tid]["conference"] = safe_val(row.get("CONFERENCE"))

    records = list(equipes.values())

    cypher = """
    UNWIND $rows AS row
    MERGE (e:Equipe {id: row.id})
    ON CREATE SET
        e.team_id     = row.team_id,
        e.nom         = row.nom,
        e.ville       = row.ville,
        e.abbreviation= row.abbreviation,
        e.conference  = row.conference,
        e.created_at  = datetime()
    ON MATCH SET
        e.nom         = COALESCE(row.nom, e.nom),
        e.ville       = COALESCE(row.ville, e.ville),
        e.abbreviation= COALESCE(row.abbreviation, e.abbreviation),
        e.conference  = COALESCE(row.conference, e.conference),
        e.updated_at  = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Equipe")

    nb_apres = compter_noeuds(session, "Equipe")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total équipes:{len(records)}")


#  NŒUD 3 — JOUEUR
def charger_joueurs(session, players_df, details_df):
    log.info("--- Nœuds Joueur ---")
    nb_avant = compter_noeuds(session, "Joueur")

    # Construire le référentiel joueurs depuis players + details
    joueurs = {}

    # Source 1 : players.csv
    for _, row in players_df.iterrows():
        pid = int(row["PLAYER_ID"])
        if pid not in joueurs:
            joueurs[pid] = {
                "id":  str(pid),
                "pid": pid,
                "nom": safe_val(row["PLAYER_NAME"]),
            }

    # Source 2 : details (enrichir avec NICKNAME et PLAYER_NAME)
    for _, row in details_df.drop_duplicates("PLAYER_ID").iterrows():
        pid = int(row["PLAYER_ID"])
        if pid not in joueurs:
            joueurs[pid] = {
                "id":  str(pid),
                "pid": pid,
                "nom": safe_val(row["PLAYER_NAME"]),
            }
        # Ajouter nickname si disponible
        nn = safe_val(row.get("NICKNAME"))
        if nn and nn != "nan":
            joueurs[pid]["nickname"] = nn

    records = list(joueurs.values())

    cypher = """
    UNWIND $rows AS row
    MERGE (j:Joueur {id: row.id})
    ON CREATE SET
        j.player_id  = row.pid,
        j.nom        = row.nom,
        j.nickname   = row.nickname,
        j.created_at = datetime()
    ON MATCH SET
        j.nom        = COALESCE(row.nom, j.nom),
        j.nickname   = COALESCE(row.nickname, j.nickname),
        j.updated_at = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Joueur")

    nb_apres = compter_noeuds(session, "Joueur")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total joueurs:{len(records)}")


#  NŒUD 4 — MATCH
def charger_matchs(session, games_df):
    log.info("--- Nœuds Match ---")
    nb_avant = compter_noeuds(session, "Match")

    records = []
    for _, row in games_df.iterrows():
        # date_est est déjà un Timestamp après validate_games
        date_val = row["GAME_DATE_EST"]
        date_str = date_val.strftime("%Y-%m-%d") if pd.notna(date_val) else None

        records.append(row_to_dict_safe({
            "id":          str(int(row["GAME_ID"])),
            "game_id":     int(row["GAME_ID"]),
            "date_est":    date_str,
            "statut":      safe_val(row["GAME_STATUS_TEXT"]),
            "saison_id":   str(int(row["SEASON"])),
            "home_wins":   int(row["HOME_TEAM_WINS"]) if pd.notna(row["HOME_TEAM_WINS"]) else None,
            "score_home":  int(row["PTS_home"]) if pd.notna(row["PTS_home"]) else None,
            "score_away":  int(row["PTS_away"]) if pd.notna(row["PTS_away"]) else None,
            "ast_home":    int(row["AST_home"]) if pd.notna(row["AST_home"]) else None,
            "reb_home":    int(row["REB_home"]) if pd.notna(row["REB_home"]) else None,
            "ast_away":    int(row["AST_away"]) if pd.notna(row["AST_away"]) else None,
            "reb_away":    int(row["REB_away"]) if pd.notna(row["REB_away"]) else None,
            "home_team_id": str(int(row["HOME_TEAM_ID"])),
            "away_team_id": str(int(row["VISITOR_TEAM_ID"])),
        }))

    cypher = """
    UNWIND $rows AS row
    MERGE (m:Match {id: row.id})
    ON CREATE SET
        m.game_id      = row.game_id,
        m.date_est     = row.date_est,
        m.statut       = row.statut,
        m.saison_id    = row.saison_id,
        m.home_wins    = row.home_wins,
        m.score_home   = row.score_home,
        m.score_away   = row.score_away,
        m.ast_home     = row.ast_home,
        m.reb_home     = row.reb_home,
        m.ast_away     = row.ast_away,
        m.reb_away     = row.reb_away,
        m.home_team_id = row.home_team_id,
        m.away_team_id = row.away_team_id,
        m.created_at   = datetime()
    ON MATCH SET
        m.statut       = row.statut,
        m.score_home   = COALESCE(row.score_home, m.score_home),
        m.score_away   = COALESCE(row.score_away, m.score_away),
        m.updated_at   = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Match")

    nb_apres = compter_noeuds(session, "Match")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total matchs:{len(records)}")


#  NŒUD 5 — PERFORMANCE
#  Uniquement pour les joueurs ayant joué (MIN non-null)
def charger_performances(session, details_df):
    log.info("--- Nœuds Performance (joueurs ayant joué) ---")
    nb_avant = compter_noeuds(session, "Performance")

    # Uniquement les lignes avec MIN valide
    df_joue = details_df[details_df["a_joue"] == True].copy()
    log.info(f"  Lignes avec MIN valide : {len(df_joue)}")

    records = []
    for _, row in df_joue.iterrows():
        gid = int(row["GAME_ID"])
        pid = int(row["PLAYER_ID"])
        tid = int(row["TEAM_ID"])
        perf_id = f"{pid}_{gid}"

        records.append({
            "id":           perf_id,
            "joueur_id":    str(pid),
            "match_id":     str(gid),
            "equipe_id":    str(tid),
            "position":     safe_val(row["START_POSITION"]) or "",
            "min_secondes": safe_val(row.get("MIN_SECONDES")),
            # Données brutes uniquement — PAS de ratios calculés
            "fgm":          safe_val(row["FGM"]),
            "fga":          safe_val(row["FGA"]),
            "fg3m":         safe_val(row["FG3M"]),
            "fg3a":         safe_val(row["FG3A"]),
            "ftm":          safe_val(row["FTM"]),
            "fta":          safe_val(row["FTA"]),
            "oreb":         safe_val(row["OREB"]),
            "dreb":         safe_val(row["DREB"]),
            "reb":          safe_val(row["REB"]),
            "ast":          safe_val(row["AST"]),
            "stl":          safe_val(row["STL"]),
            "blk":          safe_val(row["BLK"]),
            "tov":          safe_val(row["TO"]),
            "pf":           safe_val(row["PF"]),
            "pts":          safe_val(row["PTS"]),
            "plus_minus":   safe_val(row["PLUS_MINUS"]),
            # FG_PCT, FG3_PCT, FT_PCT NE SONT PAS STOCKÉS — calculés à la requête
        })

    cypher = """
    UNWIND $rows AS row
    MERGE (p:Performance {id: row.id})
    ON CREATE SET
        p.joueur_id    = row.joueur_id,
        p.match_id     = row.match_id,
        p.equipe_id    = row.equipe_id,
        p.position     = row.position,
        p.min_secondes = row.min_secondes,
        p.fgm          = row.fgm,
        p.fga          = row.fga,
        p.fg3m         = row.fg3m,
        p.fg3a         = row.fg3a,
        p.ftm          = row.ftm,
        p.fta          = row.fta,
        p.oreb         = row.oreb,
        p.dreb         = row.dreb,
        p.reb          = row.reb,
        p.ast          = row.ast,
        p.stl          = row.stl,
        p.blk          = row.blk,
        p.tov          = row.tov,
        p.pf           = row.pf,
        p.pts          = row.pts,
        p.plus_minus   = row.plus_minus,
        p.created_at   = datetime()
    ON MATCH SET
        p.updated_at   = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Performance", batch_size=1000)

    nb_apres = compter_noeuds(session, "Performance")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total perfs:{len(records)}")


#  NŒUD 6 — CLASSEMENT

def charger_classements(session, ranking_df):
    log.info("--- Nœuds Classement ---")
    nb_avant = compter_noeuds(session, "Classement")

    records = []
    for _, row in ranking_df.iterrows():
        tid    = int(row["TEAM_ID"])
        date_v = row["STANDINGSDATE"]
        date_str = date_v.strftime("%Y-%m-%d") if pd.notna(date_v) else None
        if date_str is None:
            continue
        cl_id = f"{tid}_{date_str}"

        records.append({
            "id":           cl_id,
            "team_id":      str(tid),
            "date":         date_str,
            "season_id":    safe_val(row["SEASON_ID"]),
            "conference":   safe_val(row["CONFERENCE"]),
            "nom_equipe":   safe_val(row["TEAM"]),
            "matchs_joues": safe_val(row["G"]),
            "victoires":    safe_val(row["W"]),
            "defaites":     safe_val(row["L"]),
            # W_PCT NE SERA PAS STOCKÉ — calculé à la requête (victoires/matchs_joues)
            # Exception : on le garde ici car c'est la valeur officielle NBA
            "w_pct":        safe_val(row["W_PCT"]),
            "home_record":  safe_val(row["HOME_RECORD"]),
            "road_record":  safe_val(row["ROAD_RECORD"]),
        })

    cypher = """
    UNWIND $rows AS row
    MERGE (c:Classement {id: row.id})
    ON CREATE SET
        c.team_id      = row.team_id,
        c.date         = row.date,
        c.season_id    = row.season_id,
        c.conference   = row.conference,
        c.nom_equipe   = row.nom_equipe,
        c.matchs_joues = row.matchs_joues,
        c.victoires    = row.victoires,
        c.defaites     = row.defaites,
        c.w_pct        = row.w_pct,
        c.home_record  = row.home_record,
        c.road_record  = row.road_record,
        c.created_at   = datetime()
    ON MATCH SET
        c.updated_at   = datetime()
    """
    created, _ = ingerer_par_batch(session, cypher, records, "Classement", batch_size=1000)

    nb_apres = compter_noeuds(session, "Classement")
    log.info(f"  Avant:{nb_avant} | Après:{nb_apres} | Créés:{created} | Total classements:{len(records)}")


def main():
    log.info("=" * 60)
    log.info("ÉTAPE 3 — INGESTION DES NŒUDS")
    log.info("=" * 60)
    start = datetime.now()

    # Charger les données nettoyées
    log.info("Chargement des données nettoyées...")
    parquet_dir = os.path.join(DATA_DIR, "logs")

    parquet_games   = os.path.join(parquet_dir, "games_clean.parquet")
    parquet_details = os.path.join(parquet_dir, "details_clean.parquet")
    parquet_players = os.path.join(parquet_dir, "players_clean.parquet")
    parquet_ranking = os.path.join(parquet_dir, "ranking_clean.parquet")

    if os.path.exists(parquet_games):
        games_df   = pd.read_parquet(parquet_games)
        details_df = pd.read_parquet(parquet_details)
        players_df = pd.read_parquet(parquet_players)
        ranking_df = pd.read_parquet(parquet_ranking)
        log.info("  Données nettoyées chargées depuis parquet")
    else:
        log.warning("  Parquet absent — chargement CSV bruts (validation minimale)")
        games_df   = pd.read_csv(os.path.join(DATA_DIR, "games.csv"))
        details_df = pd.read_csv(os.path.join(DATA_DIR, "games_details.csv"), low_memory=False)
        players_df = pd.read_csv(os.path.join(DATA_DIR, "players.csv"))
        ranking_df = pd.read_csv(os.path.join(DATA_DIR, "ranking.csv"))
        details_df["a_joue"] = details_df["MIN"].notna()
        from scripts_01 import parse_minutes_to_seconds
        details_df["MIN_SECONDES"] = details_df["MIN"].apply(parse_minutes_to_seconds)
        games_df["GAME_DATE_EST"] = pd.to_datetime(games_df["GAME_DATE_EST"], errors="coerce")
        ranking_df["STANDINGSDATE"] = pd.to_datetime(ranking_df["STANDINGSDATE"], errors="coerce")

    driver = get_driver()

    with driver.session() as session:
        # ORDRE TOPOLOGIQUE STRICT
        charger_saisons(session, games_df, players_df)      # niveau 1 — aucune dépendance
        charger_equipes(session, games_df, details_df, ranking_df)  # niveau 1
        charger_joueurs(session, players_df, details_df)    # niveau 2
        charger_matchs(session, games_df)                   # niveau 3 — dépend de Saison+Equipe
        charger_performances(session, details_df)           # niveau 4 — dépend de Joueur+Match
        charger_classements(session, ranking_df)            # niveau 4 — dépend de Equipe

    driver.close()

    duree = (datetime.now() - start).total_seconds()
    log.info("=" * 60)
    log.info(f"ÉTAPE 3 TERMINÉE en {duree:.0f}s ({duree/60:.1f} min)")
    log.info("Prochaine étape : python charger_relation.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()