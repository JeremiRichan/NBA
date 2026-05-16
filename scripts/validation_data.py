import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime


#  CONFIGURATION

DATA_DIR  = "../data"
LOG_DIR   = "../logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "validation_data.log"), mode="w"),
    ],
)
log = logging.getLogger(__name__)


POSTES_VALIDES = {"F", "C", "G", "F-G", "G-F", "F-C", "C-F", ""}


def parse_minutes_to_seconds(min_str):
    if pd.isna(min_str) or min_str is None:
        return None
    min_str = str(min_str).strip()
    if min_str == "" or min_str == "nan":
        return None
    try:
        if ":" in min_str:
            parts = min_str.split(":")
            minutes = int(parts[0])
            seconds = int(parts[1])
        else:
            minutes = int(float(min_str))
            seconds = 0
        total = minutes * 60 + seconds
        if total < 0 or total > 53 * 60:
            return None   # hors bornes — ignoré
        return total
    except (ValueError, IndexError):
        return None


def validate_games(df_raw):
    log.info("=== Validation games.csv ===")
    df = df_raw.copy()
    erreurs = []
    indices_invalides = set()

    # 1. Doublons sur GAME_ID
    dups = df[df.duplicated("GAME_ID", keep=False)]
    if len(dups):
        log.warning(f"  {len(dups)} lignes avec GAME_ID en doublon — conserve le premier")
        indices_invalides.update(df[df.duplicated("GAME_ID", keep="first")].index.tolist())

    # 2. GAME_ID non-null
    nulls = df[df["GAME_ID"].isna()]
    if len(nulls):
        log.error(f"  {len(nulls)} lignes avec GAME_ID null — rejetées")
        indices_invalides.update(nulls.index.tolist())

    # 3. HOME_TEAM_ID ≠ VISITOR_TEAM_ID
    reflexifs = df[df["HOME_TEAM_ID"] == df["VISITOR_TEAM_ID"]]
    if len(reflexifs):
        log.error(f"  {len(reflexifs)} matchs avec HOME=VISITOR — rejetés")
        indices_invalides.update(reflexifs.index.tolist())

    # 4. Scores valides (si non-null)
    for col in ["PTS_home", "PTS_away"]:
        invalides = df[df[col].notna() & ((df[col] < 0) | (df[col] > 200))]
        if len(invalides):
            log.warning(f"  {len(invalides)} scores hors [0,200] dans {col} — mis à NULL")
            df.loc[invalides.index, col] = np.nan

    # 5. Dates
    df["GAME_DATE_EST"] = pd.to_datetime(df["GAME_DATE_EST"], errors="coerce")
    dates_invalides = df[df["GAME_DATE_EST"].isna()]
    if len(dates_invalides):
        log.warning(f"  {len(dates_invalides)} dates invalides — matchs rejetés")
        indices_invalides.update(dates_invalides.index.tolist())

    # 6. Saison
    invalides_saison = df[(df["SEASON"] < 1990) | (df["SEASON"] > 2030)]
    if len(invalides_saison):
        log.warning(f"  {len(invalides_saison)} saisons hors [1990,2030] — rejetées")
        indices_invalides.update(invalides_saison.index.tolist())

    # 7. Cohérence TEAM_ID_home == HOME_TEAM_ID
    incoherents = df[df["TEAM_ID_home"] != df["HOME_TEAM_ID"]]
    if len(incoherents):
        log.warning(f"  {len(incoherents)} incohérences TEAM_ID_home vs HOME_TEAM_ID — corrigées")
        df.loc[incoherents.index, "TEAM_ID_home"] = df.loc[incoherents.index, "HOME_TEAM_ID"]

    df_clean = df.drop(index=list(indices_invalides)).reset_index(drop=True)


    log.info(f"  Lignes initiales : {len(df_raw)}")
    log.info(f"  Lignes rejetées  : {len(indices_invalides)}")
    log.info(f"  Lignes valides   : {len(df_clean)}")
    return df_clean


def validate_games_details(df_raw):
    log.info("=== Validation games_details.csv (668k lignes — patience) ===")
    df = df_raw.copy()
    indices_invalides = set()

    # 1. Clés obligatoires
    nulls_cles = df[df["GAME_ID"].isna() | df["PLAYER_ID"].isna()]
    if len(nulls_cles):
        log.error(f"  {len(nulls_cles)} lignes sans GAME_ID/PLAYER_ID — rejetées")
        indices_invalides.update(nulls_cles.index.tolist())

    # 2. Doublons GAME_ID + PLAYER_ID
    dups = df[df.duplicated(["GAME_ID", "PLAYER_ID"], keep=False)]
    if len(dups):
        log.warning(f"  {len(dups)} doublons (GAME_ID+PLAYER_ID) — garde le premier")
        indices_invalides.update(
            df[df.duplicated(["GAME_ID", "PLAYER_ID"], keep="first")].index.tolist()
        )

    # 3. Statistiques : vérifier uniquement les lignes avec MIN non-null (joueurs ayant joué)
    df["a_joue"] = df["MIN"].notna() & (df["MIN"].astype(str).str.strip() != "")

    masque_joue = df["a_joue"] & df.index.isin(set(df.index) - indices_invalides)

    # FGM ≤ FGA
    invalide_fg = df[masque_joue & df["FGM"].notna() & df["FGA"].notna() & (df["FGM"] > df["FGA"])]
    if len(invalide_fg):
        log.error(f"  {len(invalide_fg)} lignes FGM > FGA — rejetées")
        indices_invalides.update(invalide_fg.index.tolist())

    # FG3M ≤ FG3A ≤ FGA
    invalide_3p = df[masque_joue & df["FG3M"].notna() & df["FG3A"].notna() & (df["FG3M"] > df["FG3A"])]
    if len(invalide_3p):
        log.error(f"  {len(invalide_3p)} lignes FG3M > FG3A — rejetées")
        indices_invalides.update(invalide_3p.index.tolist())

    invalide_3p_fg = df[masque_joue & df["FG3A"].notna() & df["FGA"].notna() & (df["FG3A"] > df["FGA"])]
    if len(invalide_3p_fg):
        log.error(f"  {len(invalide_3p_fg)} lignes FG3A > FGA — rejetées")
        indices_invalides.update(invalide_3p_fg.index.tolist())

    # FTM ≤ FTA
    invalide_ft = df[masque_joue & df["FTM"].notna() & df["FTA"].notna() & (df["FTM"] > df["FTA"])]
    if len(invalide_ft):
        log.error(f"  {len(invalide_ft)} lignes FTM > FTA — rejetées")
        indices_invalides.update(invalide_ft.index.tolist())

    # 4. Cohérence des points (tolérance ±1 pour les technicals)
    cols_pts = ["FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "PTS"]
    df_check = df[masque_joue].copy()
    df_check_complet = df_check.dropna(subset=cols_pts)

    pts_calc = (
        (df_check_complet["FGM"] - df_check_complet["FG3M"]) * 2
        + df_check_complet["FG3M"] * 3
        + df_check_complet["FTM"]
    )
    ecart = (pts_calc - df_check_complet["PTS"]).abs()
    incoherents_pts = df_check_complet[ecart > 1]
    if len(incoherents_pts):
        log.warning(f"  {len(incoherents_pts)} incohérences points/tirs (tolérance 1) — rejetées")
        indices_invalides.update(incoherents_pts.index.tolist())

    # 5. Convertir MIN en secondes
    df["MIN_SECONDES"] = df["MIN"].apply(parse_minutes_to_seconds)

    # 6. Position : normaliser
    df["START_POSITION"] = df["START_POSITION"].fillna("").str.strip().str.upper()
    invalides_pos = df[~df["START_POSITION"].isin(POSTES_VALIDES)]
    if len(invalides_pos):
        log.warning(f"  {len(invalides_pos)} positions inconnues — mises à vide")
        df.loc[invalides_pos.index, "START_POSITION"] = ""

    df_clean = df.drop(index=list(indices_invalides)).reset_index(drop=True)

    log.info(f"  Lignes initiales : {len(df_raw)}")
    log.info(f"  Lignes rejetées  : {len(indices_invalides)}")
    log.info(f"  Lignes valides   : {len(df_clean)}")
    log.info(f"  Dont DNP (sans MIN): {(~df_clean['a_joue']).sum()}")
    log.info(f"  Dont ont joué     : {df_clean['a_joue'].sum()}")
    return df_clean


def validate_players(df_raw):
    log.info("=== Validation players.csv ===")
    df = df_raw.copy()
    indices_invalides = set()

    # 1. Clés obligatoires
    nulls = df[df["PLAYER_ID"].isna() | df["TEAM_ID"].isna() | df["PLAYER_NAME"].isna()]
    if len(nulls):
        log.error(f"  {len(nulls)} lignes avec clés nulles — rejetées")
        indices_invalides.update(nulls.index.tolist())

    # 2. Nom vide
    noms_vides = df[df["PLAYER_NAME"].astype(str).str.strip() == ""]
    if len(noms_vides):
        log.warning(f"  {len(noms_vides)} noms vides — rejetés")
        indices_invalides.update(noms_vides.index.tolist())

    # 3. Saison
    invalides = df[(df["SEASON"] < 1990) | (df["SEASON"] > 2030)]
    if len(invalides):
        log.warning(f"  {len(invalides)} saisons hors bornes — rejetées")
        indices_invalides.update(invalides.index.tolist())

    # 4. Doublons
    dups = df[df.duplicated(["PLAYER_ID", "SEASON", "TEAM_ID"], keep=False)]
    if len(dups):
        log.warning(f"  {len(dups)} doublons (PLAYER_ID+SEASON+TEAM_ID) — garde premier")
        indices_invalides.update(
            df[df.duplicated(["PLAYER_ID", "SEASON", "TEAM_ID"], keep="first")].index.tolist()
        )

    df_clean = df.drop(index=list(indices_invalides)).reset_index(drop=True)
    df_clean["PLAYER_NAME"] = df_clean["PLAYER_NAME"].str.strip()

    log.info(f"  Lignes initiales : {len(df_raw)}")
    log.info(f"  Lignes rejetées  : {len(indices_invalides)}")
    log.info(f"  Lignes valides   : {len(df_clean)}")
    return df_clean


def validate_ranking(df_raw):
    log.info("=== Validation ranking.csv ===")
    df = df_raw.copy()
    indices_invalides = set()

    # 1. Clés obligatoires
    nulls = df[df["TEAM_ID"].isna() | df["STANDINGSDATE"].isna()]
    if len(nulls):
        log.error(f"  {len(nulls)} lignes avec clés nulles — rejetées")
        indices_invalides.update(nulls.index.tolist())

    # 2. W + L = G
    df_check = df.drop(index=list(indices_invalides))
    incoherents = df_check[(df_check["W"] + df_check["L"]) != df_check["G"]]
    if len(incoherents):
        log.warning(f"  {len(incoherents)} incohérences W+L≠G — rejetées")
        indices_invalides.update(incoherents.index.tolist())

    # 3. W_PCT cohérent (tolérance 0.01)
    df_check2 = df.drop(index=list(indices_invalides))
    df_check2 = df_check2[df_check2["G"] > 0]
    w_pct_calc = df_check2["W"] / df_check2["G"]
    ecart = (w_pct_calc - df_check2["W_PCT"]).abs()
    incoherents_pct = df_check2[ecart > 0.01]
    if len(incoherents_pct):
        log.warning(f"  {len(incoherents_pct)} W_PCT incohérents — recalculés")
        df.loc[incoherents_pct.index, "W_PCT"] = (
            df.loc[incoherents_pct.index, "W"] / df.loc[incoherents_pct.index, "G"]
        ).round(3)

    # 4. Conférence
    invalides_conf = df[~df["CONFERENCE"].isin(["East", "West"])]
    if len(invalides_conf):
        log.warning(f"  {len(invalides_conf)} conférences inconnues — rejetées")
        indices_invalides.update(invalides_conf.index.tolist())

    # 5. Doublons
    dups = df[df.duplicated(["TEAM_ID", "STANDINGSDATE"], keep=False)]
    if len(dups):
        log.warning(f"  {len(dups)} doublons (TEAM_ID+DATE) — garde premier")
        indices_invalides.update(
            df[df.duplicated(["TEAM_ID", "STANDINGSDATE"], keep="first")].index.tolist()
        )

    df_clean = df.drop(index=list(indices_invalides)).reset_index(drop=True)
    df_clean["STANDINGSDATE"] = pd.to_datetime(df_clean["STANDINGSDATE"], errors="coerce")
    df_clean = df_clean.dropna(subset=["STANDINGSDATE"])

    log.info(f"  Lignes initiales : {len(df_raw)}")
    log.info(f"  Lignes rejetées  : {len(indices_invalides)}")
    log.info(f"  Lignes valides   : {len(df_clean)}")
    return df_clean


def cross_validate(games_clean, details_clean, players_clean, ranking_clean):
    log.info("=== Validation croisée entre fichiers ===")

    # 1. Les GAME_ID dans details doivent exister dans games
    games_ids    = set(games_clean["GAME_ID"].unique())
    details_gids = set(details_clean["GAME_ID"].unique())
    orphelins_details = details_gids - games_ids
    if orphelins_details:
        log.warning(f"  {len(orphelins_details)} GAME_ID dans details absents de games — ces lignes seront ignorées lors du chargement")

    # 2. Les TEAM_ID dans players doivent exister dans games
    games_teams  = set(games_clean["HOME_TEAM_ID"].tolist() + games_clean["VISITOR_TEAM_ID"].tolist())
    players_teams= set(players_clean["TEAM_ID"].unique())
    orphelins_players = players_teams - games_teams
    if orphelins_players:
        log.warning(f"  {len(orphelins_players)} TEAM_ID dans players absents de games : {orphelins_players}")

    # 3. Les TEAM_ID dans ranking doivent exister dans games
    ranking_teams = set(ranking_clean["TEAM_ID"].unique())
    orphelins_ranking = ranking_teams - games_teams
    if orphelins_ranking:
        log.warning(f"  {len(orphelins_ranking)} TEAM_ID dans ranking absents de games : {orphelins_ranking}")

    log.info("  Validation croisée terminée")


def main():
    log.info("=" * 60)
    log.info("ÉTAPE 1 — VALIDATION ET NETTOYAGE DES DONNÉES")
    log.info("=" * 60)
    start = datetime.now()

    # Chargement brut
    log.info("Chargement des CSV bruts...")
    games_raw   = pd.read_csv(os.path.join(DATA_DIR, "games.csv"))
    details_raw = pd.read_csv(os.path.join(DATA_DIR, "games_details.csv"), low_memory=False)
    players_raw = pd.read_csv(os.path.join(DATA_DIR, "players.csv"))
    ranking_raw = pd.read_csv(os.path.join(DATA_DIR, "ranking.csv"))
    log.info("Chargement terminé")

    # Validation individuelle
    games_clean   = validate_games(games_raw)
    details_clean = validate_games_details(details_raw)
    players_clean = validate_players(players_raw)
    ranking_clean = validate_ranking(ranking_raw)

    # Validation croisée
    cross_validate(games_clean, details_clean, players_clean, ranking_clean)

    # Sauvegarder les données nettoyées pour les étapes suivantes
    out = os.path.join(DATA_DIR, "logs")
    os.makedirs(out, exist_ok=True)
    games_clean.to_parquet(os.path.join(out, "games_clean.parquet"),   index=False)
    details_clean.to_parquet(os.path.join(out, "details_clean.parquet"), index=False)
    players_clean.to_parquet(os.path.join(out, "players_clean.parquet"), index=False)
    ranking_clean.to_parquet(os.path.join(out, "ranking_clean.parquet"), index=False)

    duree = (datetime.now() - start).total_seconds()
    log.info("=" * 60)
    log.info(f"ÉTAPE 1 TERMINÉE en {duree:.1f}s")
    log.info("Données nettoyées sauvegardées dans logs/*.parquet")
    log.info("Prochaine étape : python config_contraint.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()