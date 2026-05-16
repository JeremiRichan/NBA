import sys
import os
import logging
import time
from datetime import datetime

#  CONFIGURATION

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
        logging.FileHandler(os.path.join(LOG_DIR, "02_setup_constraints.log"), mode="w"),
    ],
)
log = logging.getLogger(__name__)

#  DÉFINITION DES CONTRAINTES ET INDEX
#  Ordre : entités racines d'abord (tri topologique)

CONTRAINTES_UNICITE = [
    ("contrainte_saison_id",       "Saison",       "id"),
    ("contrainte_equipe_id",       "Equipe",       "id"),
    ("contrainte_joueur_id",       "Joueur",       "id"),
    ("contrainte_match_id",        "Match",        "id"),
    ("contrainte_classement_id",   "Classement",   "id"),
    ("contrainte_performance_id",  "Performance",  "id"),
]

INDEX_RANGE = [
    ("idx_match_date",         "Match",      "date_est"),
    ("idx_classement_date",    "Classement", "date"),
    ("idx_saison_annee",       "Saison",     "annee"),
]

INDEX_FULLTEXT = [
    ("idx_ft_joueur_nom",  ["Joueur"],  ["nom"]),
    ("idx_ft_equipe_nom",  ["Equipe"],  ["nom", "ville"]),
]


def get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def creer_contraintes_unicite(session):
    log.info("--- Création des contraintes d'unicité ---")
    for nom, label, prop in CONTRAINTES_UNICITE:
        cypher = (
            f"CREATE CONSTRAINT {nom} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        try:
            session.run(cypher)
            log.info(f"  ✓ Contrainte : {label}.{prop}")
        except Exception as e:
            log.error(f"  ✗ Contrainte {nom} : {e}")
            raise


def creer_index_range(session):
    log.info("--- Création des index RANGE ---")
    for nom, label, prop in INDEX_RANGE:
        cypher = (
            f"CREATE INDEX {nom} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.{prop})"
        )
        try:
            session.run(cypher)
            log.info(f"  ✓ Index range : {label}.{prop}")
        except Exception as e:
            log.error(f"  ✗ Index range {nom} : {e}")
            raise


def creer_index_fulltext(session):
    log.info("--- Création des index Full-Text ---")
    for nom, labels, props in INDEX_FULLTEXT:
        labels_str = "|".join(labels)
        props_str  = ", ".join([f"n.{p}" for p in props])
        cypher = (
            f"CREATE FULLTEXT INDEX {nom} IF NOT EXISTS "
            f"FOR (n:{labels_str}) ON EACH [{props_str}]"
        )
        try:
            session.run(cypher)
            log.info(f"  ✓ Index fulltext : {labels} sur {props}")
        except Exception as e:
            log.error(f"  ✗ Index fulltext {nom} : {e}")
            raise


def attendre_index_online(session, timeout_sec=120):
    log.info("--- Attente que tous les index soient ONLINE ---")
    debut = time.time()
    while True:
        result = session.run(
            "SHOW INDEXES YIELD name, state, type "
            "WHERE state <> 'ONLINE' RETURN name, state, type"
        )
        en_attente = result.data()

        if not en_attente:
            log.info("  ✓ Tous les index sont ONLINE")
            return

        if time.time() - debut > timeout_sec:
            noms = [r["name"] for r in en_attente]
            raise TimeoutError(
                f"Index toujours pas ONLINE après {timeout_sec}s : {noms}"
            )

        noms_attente = [f"{r['name']}({r['state']})" for r in en_attente]
        log.info(f"  En attente : {noms_attente} — retry dans 3s")
        time.sleep(3)


def verifier_index_failed(session):
    result = session.run(
        "SHOW INDEXES YIELD name, state WHERE state = 'FAILED' RETURN name"
    )
    failed = [r["name"] for r in result.data()]
    if failed:
        raise RuntimeError(
            f"Index en état FAILED — reconstruire avant de continuer : {failed}"
        )


def afficher_registre_index(session):
    """Affiche tous les index existants pour traçabilité."""
    log.info("--- Registre complet des index ---")
    result = session.run(
        "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state "
        "RETURN name, type, labelsOrTypes, properties, state "
        "ORDER BY type, name"
    )
    for row in result.data():
        log.info(
            f"  [{row['state']}] {row['type']:20s} {row['name']:40s} "
            f"({row['labelsOrTypes']} → {row['properties']})"
        )


def main():
    log.info("=" * 60)
    log.info("ÉTAPE 2 — INDEX ET CONTRAINTES NEO4J")
    log.info("=" * 60)
    start = datetime.now()

    driver = get_driver()
    with driver.session() as session:
        creer_contraintes_unicite(session)
        creer_index_range(session)
        creer_index_fulltext(session)
        attendre_index_online(session)
        verifier_index_failed(session)
        afficher_registre_index(session)

    driver.close()

    duree = (datetime.now() - start).total_seconds()
    log.info("=" * 60)
    log.info(f"ÉTAPE 2 TERMINÉE en {duree:.1f}s")
    log.info("Prochaine étape : python charger_nodes.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()