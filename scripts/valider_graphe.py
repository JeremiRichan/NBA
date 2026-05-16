import os
import sys
import logging
from datetime import datetime


NEO4J_URI      = "neo4j://127.0.0.1:7687"    
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password123"
DATA_DIR       = "../data" 
LOG_DIR        = "../logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "05_validate_graph.log"), mode="w"),
    ],
)
log = logging.getLogger(__name__)


ERREURS_CRITIQUES = []
WARNINGS          = []


def get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def erreur(msg):
    ERREURS_CRITIQUES.append(msg)
    log.error(f"  ✗ CRITIQUE : {msg}")


def warning(msg):
    WARNINGS.append(msg)
    log.warning(f"  ⚠ WARNING  : {msg}")


def ok(msg):
    log.info(f"  ✓ {msg}")



#  INVARIANT 1 — Nœuds isolés

def verifier_noeuds_isoles(session):
    log.info("--- Invariant 1 : Nœuds isolés ---")

    seuils = {
        "Joueur":      (0, "CRITIQUE"),   # un joueur sans équipe = données incomplètes
        "Match":       (0, "CRITIQUE"),   # un match sans équipes = inutilisable
        "Performance": (0, "CRITIQUE"),   # une perf sans joueur/match = orpheline
        "Equipe":      (0, "WARNING"),    # une équipe sans match peut exister en début de saison
        "Saison":      (5, "WARNING"),    # tolérance 5 saisons sans match (edge cases)
        "Classement":  (0, "WARNING"),
    }

    for label, (seuil, severite) in seuils.items():
        result = session.run(
            f"MATCH (n:{label}) WHERE NOT (n)--() RETURN count(n) AS c"
        )
        count = result.single()["c"]
        if count > seuil:
            msg = f"{count} nœuds {label} isolés (sans aucune relation)"
            if severite == "CRITIQUE":
                erreur(msg)
            else:
                warning(msg)
        else:
            ok(f"Nœuds {label} isolés : {count}")


#  INVARIANT 2 — Complétude de chaque Match
def verifier_completude_matchs(session):
    log.info("--- Invariant 2 : Complétude des matchs ---")

    # 2a : exactement 2 équipes par match (DISPUTE + VISITE)
    result = session.run("""
        MATCH (m:Match)
        OPTIONAL MATCH (dom:Equipe)-[:DISPUTE]->(m)
        OPTIONAL MATCH (vis:Equipe)-[:VISITE]->(m)
        WITH m,
             count(DISTINCT dom) AS nb_dom,
             count(DISTINCT vis) AS nb_vis
        WHERE nb_dom <> 1 OR nb_vis <> 1
        RETURN count(m) AS nb_problemes,
               sum(CASE WHEN nb_dom <> 1 THEN 1 ELSE 0 END) AS dom_pb,
               sum(CASE WHEN nb_vis <> 1 THEN 1 ELSE 0 END) AS vis_pb
    """)
    row = result.single()
    if row["nb_problemes"] > 0:
        erreur(f"{row['nb_problemes']} matchs avec structure d'équipes incorrecte "
               f"(domicile: {row['dom_pb']}, visiteur: {row['vis_pb']})")
    else:
        ok("Tous les matchs ont exactement 1 équipe domicile + 1 visiteur")

    # 2b : chaque match relié à une saison
    result = session.run("""
        MATCH (m:Match)
        WHERE NOT (:Saison)-[:CONTIENT]->(m)
        RETURN count(m) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} matchs non reliés à une Saison")
    else:
        ok("Tous les matchs sont reliés à une Saison")

    # 2c : nombre de performances par match (min 10 pour un vrai match)
    result = session.run("""
        MATCH (m:Match)
        WHERE (:Equipe)-[:DISPUTE]->(m)   // seulement les vrais matchs (pas les futurs)
          AND m.score_home IS NOT NULL     // match terminé
        OPTIONAL MATCH (p:Performance)-[:LORS_DE]->(m)
        WITH m, count(p) AS nb_perfs
        WHERE nb_perfs < 10 OR nb_perfs > 30
        RETURN count(m) AS nb_problemes,
               sum(CASE WHEN nb_perfs < 10 THEN 1 ELSE 0 END) AS trop_peu,
               sum(CASE WHEN nb_perfs > 30 THEN 1 ELSE 0 END) AS trop
    """)
    row = result.single()
    if row["nb_problemes"] > 0:
        warning(f"{row['nb_problemes']} matchs terminés avec nombre de performances anormal "
                f"(< 10: {row['trop_peu']}, > 30: {row['trop']})")
    else:
        ok("Nombre de performances par match dans les bornes [10, 30]")


#  INVARIANT 3 — Cohérence des stats Performance

def verifier_stats_performances(session):
    log.info("--- Invariant 3 : Cohérence des statistiques ---")

    # FGM ≤ FGA
    result = session.run("""
        MATCH (p:Performance)
        WHERE p.fgm IS NOT NULL AND p.fga IS NOT NULL AND p.fgm > p.fga
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances avec FGM > FGA — impossible")
    else:
        ok("FGM ≤ FGA sur toutes les Performances")

    # FG3M ≤ FG3A
    result = session.run("""
        MATCH (p:Performance)
        WHERE p.fg3m IS NOT NULL AND p.fg3a IS NOT NULL AND p.fg3m > p.fg3a
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances avec FG3M > FG3A — impossible")
    else:
        ok("FG3M ≤ FG3A sur toutes les Performances")

    # FTM ≤ FTA
    result = session.run("""
        MATCH (p:Performance)
        WHERE p.ftm IS NOT NULL AND p.fta IS NOT NULL AND p.ftm > p.fta
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances avec FTM > FTA — impossible")
    else:
        ok("FTM ≤ FTA sur toutes les Performances")

    # Cohérence des points (tolérance ±1)
    result = session.run("""
        MATCH (p:Performance)
        WHERE p.fgm IS NOT NULL AND p.fg3m IS NOT NULL
          AND p.ftm IS NOT NULL AND p.pts IS NOT NULL
        WITH p,
             ((p.fgm - p.fg3m) * 2 + p.fg3m * 3 + p.ftm) AS pts_calc
        WHERE abs(pts_calc - p.pts) > 1
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances avec points incohérents vs tirs (tolérance 1)")
    else:
        ok("Cohérence points/tirs vérifiée (tolérance ±1)")

    # Minutes dans [0, 3180] secondes (53 min max)
    result = session.run("""
        MATCH (p:Performance)
        WHERE p.min_secondes IS NOT NULL
          AND (p.min_secondes < 0 OR p.min_secondes > 3180)
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        warning(f"{count} Performances avec minutes hors [0, 53min]")
    else:
        ok("Minutes dans les bornes [0, 53min]")


#  INVARIANT 4 — JOUE_POUR actif unique par joueur

def verifier_contrats_actifs(session):
    log.info("--- Invariant 4 : Unicité des contrats actifs ---")

    result = session.run("""
        MATCH (j:Joueur)-[r:JOUE_POUR {actif: true}]->(e:Equipe)
        WITH j, count(r) AS nb_actifs
        WHERE nb_actifs > 1
        RETURN count(j) AS nb_conflits
    """)
    count = result.single()["nb_conflits"]
    if count > 0:
        erreur(f"{count} joueurs avec plus d'un contrat actif=true simultané")
    else:
        ok("Chaque joueur a au maximum 1 relation JOUE_POUR actif=true")


#  INVARIANT 5 — Cohérence W+L=G dans Classement

def verifier_classements(session):
    log.info("--- Invariant 5 : Cohérence des classements ---")

    result = session.run("""
        MATCH (c:Classement)
        WHERE c.victoires IS NOT NULL
          AND c.defaites IS NOT NULL
          AND c.matchs_joues IS NOT NULL
          AND (c.victoires + c.defaites) <> c.matchs_joues
        RETURN count(c) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Classements avec W+L ≠ G")
    else:
        ok("W + L = G sur tous les Classements")


#  INVARIANT 6 — Performances orphelines

def verifier_performances_orphelines(session):
    log.info("--- Invariant 6 : Performances orphelines ---")

    # Perf sans REALISE (pas de joueur)
    result = session.run("""
        MATCH (p:Performance)
        WHERE NOT (:Joueur)-[:REALISE]->(p)
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances sans relation REALISE (pas de joueur)")
    else:
        ok("Toutes les Performances ont un Joueur via REALISE")

    # Perf sans LORS_DE (pas de match)
    result = session.run("""
        MATCH (p:Performance)
        WHERE NOT (p)-[:LORS_DE]->(:Match)
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances sans relation LORS_DE (pas de match)")
    else:
        ok("Toutes les Performances ont un Match via LORS_DE")

    # Perf sans POUR_EQUIPE (pas d'équipe)
    result = session.run("""
        MATCH (p:Performance)
        WHERE NOT (p)-[:POUR_EQUIPE]->(:Equipe)
        RETURN count(p) AS c
    """)
    count = result.single()["c"]
    if count > 0:
        erreur(f"{count} Performances sans relation POUR_EQUIPE (pas d'équipe)")
    else:
        ok("Toutes les Performances ont une Equipe via POUR_EQUIPE")


#  INVARIANT 7 — Rapport de volume

def rapport_volume(session):
    log.info("--- Invariant 7 : Rapport de volume ---")

    noeuds = {
        "Saison":      (10,   50),
        "Equipe":      (28,   32),
        "Joueur":      (500,  5000),
        "Match":       (10000, 30000),
        "Performance": (100000, 700000),
        "Classement":  (50000, 300000),
    }
    for label, (min_v, max_v) in noeuds.items():
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
        count = result.single()["c"]
        if count < min_v:
            erreur(f"Trop peu de nœuds {label}: {count} (min attendu: {min_v})")
        elif count > max_v:
            warning(f"Beaucoup de nœuds {label}: {count} (max attendu: {max_v})")
        else:
            ok(f"{label}: {count:,}")

    relations = [
        "CONTIENT", "DISPUTE", "VISITE",
        "JOUE_POUR", "REALISE", "LORS_DE", "POUR_EQUIPE", "A_CLASSEMENT"
    ]
    for rel in relations:
        result = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c")
        count = result.single()["c"]
        log.info(f"  Relations {rel}: {count:,}")


#  INVARIANT 8 — Exemples de requêtes analytiques
#  (vérification que les requêtes retournent des résultats sensés)

def verifier_requetes_analytiques(session):
    log.info("--- Invariant 8 : Requêtes analytiques de sanité ---")

    # Top scoreur de la dernière saison disponible
    result = session.run("""
        MATCH (s:Saison)-[:CONTIENT]->(m:Match)
        WITH max(s.annee) AS derniere_saison
        MATCH (s2:Saison {annee: derniere_saison})-[:CONTIENT]->(m2:Match)
        MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m2)
        WHERE p.pts IS NOT NULL
        RETURN j.nom AS joueur,
               round(avg(p.pts), 1) AS moy_pts,
               count(p) AS nb_matchs
        ORDER BY moy_pts DESC
        LIMIT 1
    """)
    row = result.single()
    if row is None:
        erreur("Requête top scoreur retourne aucun résultat")
    else:
        ok(f"Top scoreur dernière saison: {row['joueur']} ({row['moy_pts']} pts/match sur {row['nb_matchs']} matchs)")
        if row["moy_pts"] < 5 or row["moy_pts"] > 60:
            warning(f"Moyenne du top scoreur hors bornes réalistes: {row['moy_pts']}")

    # Vérifier qu'on peut relier un joueur à ses matchs
    result = session.run("""
        MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m:Match)
        RETURN count(DISTINCT j) AS nb_joueurs_avec_matchs
    """)
    nb = result.single()["nb_joueurs_avec_matchs"]
    ok(f"Joueurs avec au moins 1 match via Performance: {nb:,}")
    if nb < 100:
        erreur(f"Trop peu de joueurs avec des matchs: {nb}")


def main():
    log.info("=" * 60)
    log.info("ÉTAPE 5 — VALIDATION DES INVARIANTS DU GRAPHE")
    log.info("=" * 60)
    start = datetime.now()

    driver = get_driver()
    with driver.session() as session:
        verifier_noeuds_isoles(session)
        verifier_completude_matchs(session)
        verifier_stats_performances(session)
        verifier_contrats_actifs(session)
        verifier_classements(session)
        verifier_performances_orphelines(session)
        rapport_volume(session)
        verifier_requetes_analytiques(session)

    driver.close()

    duree = (datetime.now() - start).total_seconds()
    log.info("=" * 60)

    if ERREURS_CRITIQUES:
        log.error(f"GRAPHE DÉGRADÉ — {len(ERREURS_CRITIQUES)} erreur(s) critique(s) :")
        for e in ERREURS_CRITIQUES:
            log.error(f"  • {e}")
        log.error("Consulter cypher/reparation.cypher pour les requêtes de réparation")
        statut = "DÉGRADÉ"
    else:
        statut = "SAIN"

    if WARNINGS:
        log.warning(f"{len(WARNINGS)} warning(s) :")
        for w in WARNINGS:
            log.warning(f"  • {w}")

    log.info(f"ÉTAPE 5 TERMINÉE en {duree:.1f}s — Statut : {statut}")
    log.info("=" * 60)

    if ERREURS_CRITIQUES:
        sys.exit(1)


if __name__ == "__main__":
    main()
