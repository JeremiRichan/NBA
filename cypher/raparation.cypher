

// Voir les nœuds isolés avant suppression
MATCH (n) WHERE NOT (n)--()
RETURN labels(n)[0] AS label, count(n) AS nb;

// Supprimer les Performances isolées (orphelines)
MATCH (p:Performance) WHERE NOT (p)--()
DELETE p;

// Supprimer les Matchs isolés (sans équipes ni saison)
MATCH (m:Match) WHERE NOT (m)--()
DELETE m;


// Voir les joueurs concernés
MATCH (j:Joueur)-[r:JOUE_POUR {actif: true}]->(e:Equipe)
WITH j, count(r) AS nb, collect({rel: r, equipe: e.nom, saison: r.saison}) AS rels
WHERE nb > 1
RETURN j.nom, nb, [x IN rels | x.equipe + ' (' + toString(x.saison) + ')'] AS equipes;

// Garder seulement la relation avec la saison la plus récente comme actif=true
MATCH (j:Joueur)-[r:JOUE_POUR {actif: true}]->(e:Equipe)
WITH j, collect(r) AS rels
WHERE size(rels) > 1
WITH j, rels,
     reduce(max_r = rels[0], r2 IN rels |
       CASE WHEN r2.saison > max_r.saison THEN r2 ELSE max_r END
     ) AS rel_plus_recente
UNWIND rels AS r
WITH j, r, rel_plus_recente
WHERE r <> rel_plus_recente
SET r.actif = false;


// Performances sans LORS_DE mais ayant match_id stocké
MATCH (p:Performance)
WHERE NOT (p)-[:LORS_DE]->(:Match)
  AND p.match_id IS NOT NULL
MATCH (m:Match {id: p.match_id})
MERGE (p)-[:LORS_DE]->(m)
RETURN count(*) AS reparees;


MATCH (p:Performance)
WHERE NOT (:Joueur)-[:REALISE]->(p)
  AND p.joueur_id IS NOT NULL
MATCH (j:Joueur {id: p.joueur_id})
MERGE (j)-[:REALISE]->(p)
RETURN count(*) AS reparees;



MATCH (p:Performance)
WHERE NOT (p)-[:POUR_EQUIPE]->(:Equipe)
  AND p.equipe_id IS NOT NULL
MATCH (e:Equipe {id: p.equipe_id})
MERGE (p)-[:POUR_EQUIPE]->(e)
RETURN count(*) AS reparees;


MATCH (m:Match)
WHERE NOT (:Saison)-[:CONTIENT]->(m)
  AND m.saison_id IS NOT NULL
MATCH (s:Saison {id: m.saison_id})
MERGE (s)-[:CONTIENT]->(m)
RETURN count(*) AS reparees;


// Matchs sans équipe domicile
MATCH (m:Match)
WHERE NOT (:Equipe)-[:DISPUTE]->(m)
  AND m.home_team_id IS NOT NULL
MATCH (e:Equipe {id: m.home_team_id})
MERGE (e)-[:DISPUTE {score: m.score_home}]->(m)
RETURN count(*) AS reparees_domicile;

// Matchs sans équipe visiteur
MATCH (m:Match)
WHERE NOT (:Equipe)-[:VISITE]->(m)
  AND m.away_team_id IS NOT NULL
MATCH (e:Equipe {id: m.away_team_id})
MERGE (e)-[:VISITE {score: m.score_away}]->(m)
RETURN count(*) AS reparees_visiteur;



// Voir les classements incohérents
MATCH (c:Classement)
WHERE (c.victoires + c.defaites) <> c.matchs_joues
RETURN c.id, c.victoires, c.defaites, c.matchs_joues
LIMIT 20;

// Corriger G = W + L (si G est la valeur erronée)
MATCH (c:Classement)
WHERE (c.victoires + c.defaites) <> c.matchs_joues
  AND c.victoires IS NOT NULL AND c.defaites IS NOT NULL
SET c.matchs_joues = c.victoires + c.defaites;


// Re-lancer tous les compteurs
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS nb ORDER BY nb DESC;
MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS nb ORDER BY nb DESC;
