
// (créent automatiquement un index B-tree)

CREATE CONSTRAINT contrainte_saison_id IF NOT EXISTS
  FOR (n:Saison) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contrainte_equipe_id IF NOT EXISTS
  FOR (n:Equipe) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contrainte_joueur_id IF NOT EXISTS
  FOR (n:Joueur) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contrainte_match_id IF NOT EXISTS
  FOR (n:Match) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contrainte_classement_id IF NOT EXISTS
  FOR (n:Classement) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contrainte_performance_id IF NOT EXISTS
  FOR (n:Performance) REQUIRE n.id IS UNIQUE;


CREATE INDEX idx_match_date IF NOT EXISTS
  FOR (n:Match) ON (n.date_est);

CREATE INDEX idx_classement_date IF NOT EXISTS
  FOR (n:Classement) ON (n.date);

CREATE INDEX idx_saison_annee IF NOT EXISTS
  FOR (n:Saison) ON (n.annee);

// ── INDEX FULL-TEXT (recherche textuelle) ─────────────────

CREATE FULLTEXT INDEX idx_ft_joueur_nom IF NOT EXISTS
  FOR (n:Joueur) ON EACH [n.nom];

CREATE FULLTEXT INDEX idx_ft_equipe_nom IF NOT EXISTS
  FOR (n:Equipe) ON EACH [n.nom, n.ville];

// Lancer après création pour s'assurer que tout est ONLINE

SHOW INDEXES YIELD name, state, type
WHERE state <> 'ONLINE'
RETURN name, state, type;