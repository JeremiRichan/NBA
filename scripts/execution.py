import subprocess
import sys
import time
from datetime import datetime

ETAPES = [
    ("/home/jeremi/NBA/scripts/verifiEnvironnement.py",         "Vérification environnement"),
    ("/home/jeremi/NBA/scripts/validation_data.py",      "Validation et nettoyage CSV"),
    ("/home/jeremi/NBA/scripts/config_contraint.py",  "Index et contraintes Neo4j"),
    ("/home/jeremi/NBA/scripts/charger_nodes.py",         "Ingestion des nœuds"),
    ("/home/jeremi/NBA/scripts/charger_relation.py", "Ingestion des relations"),
    ("/home/jeremi/NBA/scripts/valider_graphe.py",     "Validation des invariants"),
]


def main():
    print("=" * 60)
    print("NBA NEO4J — PIPELINE COMPLET")
    print(f"Début : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    debut_global = time.time()

    for i, (script, description) in enumerate(ETAPES, 1):
        print(f"\n[{i}/{len(ETAPES)}] {description}...")
        debut = time.time()

        result = subprocess.run(
            [sys.executable, script],
            capture_output=False,   # affiche la sortie en temps réel
        )

        duree = time.time() - debut

        if result.returncode != 0:
            print(f"\n✗ ÉCHEC à l'étape {i} ({script}) après {duree:.1f}s")
            print("  Le pipeline est arrêté. Corriger l'erreur et relancer.")
            sys.exit(1)

        print(f"  ✓ Étape {i} terminée en {duree:.1f}s")

    duree_totale = time.time() - debut_global
    print("\n" + "=" * 60)
    print(f"✓ PIPELINE COMPLET en {duree_totale:.0f}s ({duree_totale/60:.1f} min)")
    print("  Graphe NBA prêt dans Neo4j.")
    print("  Ouvrir http://localhost:7474 pour explorer.")
    print("  Consulter cypher/queries_examples.cypher pour les requêtes.")
    print("=" * 60)


if __name__ == "__main__":
    main()
