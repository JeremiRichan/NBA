
import sys
import os


NEO4J_URI      = "neo4j://127.0.0.1:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password123"
DATA_DIR       = "../data" 

CSV_FILES = [
    "games.csv",
    "games_details.csv",
    "players.csv",
    "ranking.csv",
]


def check_python_version():
    print("[1/4] Vérification Python...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"   Python {version.major}.{version.minor} détecté — Python 3.8+ requis")
        sys.exit(1)
    print(f"   Python {version.major}.{version.minor}.{version.micro}")


def check_dependencies():
    print("[2/4] Vérification des dépendances Python...")
    required = ["neo4j", "pandas"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"   {pkg}")
        except ImportError:
            print(f"   {pkg} manquant")
            missing.append(pkg)
    if missing:
        print(f"\n  Installer avec : pip install {' '.join(missing)}")
        sys.exit(1)


def check_csv_files():
    print("[3/4] Vérification des fichiers CSV...")
    all_ok = True
    for fname in CSV_FILES:
        path = os.path.join(DATA_DIR, fname)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"   {fname}  ({size_mb:.1f} MB)")
        else:
            print(f"   {fname} introuvable dans {DATA_DIR}")
            all_ok = False
    if not all_ok:
        print(f"\n  Vérifier que DATA_DIR = '{DATA_DIR}' est correct")
        sys.exit(1)


def check_neo4j_connection():
    print("[4/4] Vérification de la connexion Neo4j...")
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            val = result.single()["ok"]
            assert val == 1
        driver.close()
        print(f"   Connecté à {NEO4J_URI}")

        # Vérifier la version Neo4j
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            r = session.run("CALL dbms.components() YIELD name, versions RETURN name, versions")
            row = r.single()
            print(f"   {row['name']} version {row['versions'][0]}")
        driver.close()

    except ServiceUnavailable:
        print(f"   Neo4j inaccessible à {NEO4J_URI}")
        print("     Vérifier que Neo4j est démarré")
        print("     Ou modifier NEO4J_URI dans ce script")
        sys.exit(1)
    except AuthError:
        print(f"   Authentification échouée (user={NEO4J_USER})")
        print("     Modifier NEO4J_USER / NEO4J_PASSWORD dans ce script")
        sys.exit(1)


def main():
    print("=" * 50)
    print("ÉTAPE 0 — VÉRIFICATION DE L'ENVIRONNEMENT")
    print("=" * 50)
    check_python_version()
    check_dependencies()
    check_csv_files()
    check_neo4j_connection()
    print("\n Environnement valide — vous pouvez lancer le pipeline")
    print("  Prochaine étape : validation_data.py")


if __name__ == "__main__":
    main()