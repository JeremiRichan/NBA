// Remplacer 2022 par l'annee souhaitee
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
WITH j,
     count(p)              AS matchs_joues,
     avg(p.pts)            AS moy_pts_brut,
     avg(p.reb)            AS moy_reb_brut,
     avg(p.ast)            AS moy_ast_brut,
     avg(p.min_secondes)   AS moy_sec_brut,
     sum(p.fgm)            AS total_fgm,
     sum(p.fga)            AS total_fga,
     sum(p.fg3m)           AS total_fg3m,
     sum(p.fg3a)           AS total_fg3a,
     sum(p.ftm)            AS total_ftm,
     sum(p.fta)            AS total_fta
RETURN
  j.nom                                                                   AS joueur,
  matchs_joues,
  round(moy_pts_brut  * 10) / 10.0                                        AS pts_par_match,
  round(moy_reb_brut  * 10) / 10.0                                        AS reb_par_match,
  round(moy_ast_brut  * 10) / 10.0                                        AS ast_par_match,
  round(moy_sec_brut / 60.0 * 10) / 10.0                                  AS min_par_match,
  CASE WHEN total_fga  = 0 OR total_fga  IS NULL THEN NULL
       ELSE round(total_fgm  * 1000.0 / total_fga)  / 1000.0 END          AS fg_pct,
  CASE WHEN total_fg3a = 0 OR total_fg3a IS NULL THEN NULL
       ELSE round(total_fg3m * 1000.0 / total_fg3a) / 1000.0 END          AS fg3_pct,
  CASE WHEN total_fta  = 0 OR total_fta  IS NULL THEN NULL
       ELSE round(total_ftm  * 1000.0 / total_fta)  / 1000.0 END          AS ft_pct
ORDER BY pts_par_match DESC
LIMIT 20;


MATCH (j:Joueur)
WHERE j.nom CONTAINS 'LeBron'
WITH j
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
WITH j,
     count(p)      AS matchs,
     avg(p.pts)    AS moy_pts_brut,
     avg(p.reb)    AS moy_reb_brut,
     avg(p.ast)    AS moy_ast_brut,
     avg(p.stl)    AS moy_stl_brut,
     avg(p.blk)    AS moy_blk_brut,
     avg(p.tov)    AS moy_tov_brut,
     avg(p.plus_minus) AS moy_pm_brut,
     sum(p.fgm)    AS sfgm,
     sum(p.fga)    AS sfga,
     sum(p.fg3m)   AS sfg3m,
     sum(p.fg3a)   AS sfg3a,
     sum(p.ftm)    AS sftm,
     sum(p.fta)    AS sfta
RETURN
  j.nom                                                               AS joueur,
  matchs,
  round(moy_pts_brut * 10) / 10.0                                     AS moy_pts,
  round(moy_reb_brut * 10) / 10.0                                     AS moy_reb,
  round(moy_ast_brut * 10) / 10.0                                     AS moy_ast,
  round(moy_stl_brut * 10) / 10.0                                     AS moy_stl,
  round(moy_blk_brut * 10) / 10.0                                     AS moy_blk,
  round(moy_tov_brut * 10) / 10.0                                     AS moy_tov,
  round(moy_pm_brut  * 10) / 10.0                                     AS moy_plus_minus,
  CASE WHEN sfga  = 0 OR sfga  IS NULL THEN NULL
       ELSE round(sfgm  * 1000.0 / sfga)  / 1000.0 END               AS fg_pct,
  CASE WHEN sfg3a = 0 OR sfg3a IS NULL THEN NULL
       ELSE round(sfg3m * 1000.0 / sfg3a) / 1000.0 END               AS fg3_pct,
  CASE WHEN sfta  = 0 OR sfta  IS NULL THEN NULL
       ELSE round(sftm  * 1000.0 / sfta)  / 1000.0 END               AS ft_pct;


// 1.3 Double-doubles et triple-doubles sur la saison
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
  AND p.reb IS NOT NULL
  AND p.ast IS NOT NULL
WITH j,
     count(p) AS matchs,
     sum(CASE WHEN p.pts >= 10 AND p.reb >= 10 AND p.ast >= 10 THEN 1 ELSE 0 END) AS triple_doubles,
     sum(CASE WHEN p.pts >= 10 AND p.reb >= 10                  THEN 1 ELSE 0 END) AS dd_pts_reb,
     sum(CASE WHEN p.pts >= 10 AND p.ast >= 10                  THEN 1 ELSE 0 END) AS dd_pts_ast,
     sum(CASE WHEN p.reb >= 10 AND p.ast >= 10                  THEN 1 ELSE 0 END) AS dd_reb_ast
WITH j, matchs, triple_doubles,
     dd_pts_reb + dd_pts_ast + dd_reb_ast - 2 * triple_doubles AS double_doubles
RETURN j.nom, matchs, triple_doubles, double_doubles
ORDER BY triple_doubles DESC, double_doubles DESC
LIMIT 20;


// 1.4 Record de points sur un match unique (top 10 all-time)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m:Match)
WHERE p.pts IS NOT NULL
WITH j, m, p
ORDER BY p.pts DESC
LIMIT 10
RETURN
  j.nom        AS joueur,
  m.date_est   AS date_match,
  m.saison_id  AS saison,
  p.pts        AS points,
  p.reb        AS rebonds,
  p.ast        AS passes,
  p.fgm        AS fgm,
  p.fga        AS fga,
  p.fg3m       AS fg3m,
  p.ftm        AS ftm;


MATCH (j:Joueur)
WHERE j.nom CONTAINS 'James'
WITH j
MATCH (s:Saison)-[:CONTIENT]->(m:Match)
MATCH (j)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
WITH s.annee AS annee,
     count(p)    AS matchs,
     avg(p.pts)  AS moy_pts_brut,
     avg(p.reb)  AS moy_reb_brut,
     avg(p.ast)  AS moy_ast_brut,
     sum(p.fgm)  AS sfgm,
     sum(p.fga)  AS sfga
RETURN
  annee,
  matchs,
  round(moy_pts_brut * 10) / 10.0                                     AS moy_pts,
  round(moy_reb_brut * 10) / 10.0                                     AS moy_reb,
  round(moy_ast_brut * 10) / 10.0                                     AS moy_ast,
  CASE WHEN sfga = 0 OR sfga IS NULL THEN NULL
       ELSE round(sfgm * 1000.0 / sfga) / 1000.0 END                  AS fg_pct
ORDER BY annee;


MATCH (e:Equipe {abbreviation: 'LAL'})
WITH e
OPTIONAL MATCH (e)-[rd:DISPUTE]->(md:Match)
WITH e,
     count(rd) AS matchs_dom,
     sum(CASE WHEN rd.resultat = 'victoire' THEN 1 ELSE 0 END) AS vic_dom,
     sum(CASE WHEN rd.resultat = 'defaite'  THEN 1 ELSE 0 END) AS def_dom
OPTIONAL MATCH (e)-[rv:VISITE]->(mv:Match)
WITH e, matchs_dom, vic_dom, def_dom,
     count(rv) AS matchs_ext,
     sum(CASE WHEN rv.resultat = 'victoire' THEN 1 ELSE 0 END) AS vic_ext,
     sum(CASE WHEN rv.resultat = 'defaite'  THEN 1 ELSE 0 END) AS def_ext
RETURN
  e.nom       AS equipe,
  matchs_dom,
  vic_dom,
  def_dom,
  matchs_ext,
  vic_ext,
  def_ext,
  matchs_dom + matchs_ext                                     AS total_matchs,
  vic_dom    + vic_ext                                        AS total_victoires;


// 2.2 Classement d'une conference a une date donnee
MATCH (e:Equipe)-[:A_CLASSEMENT]->(c:Classement)
WHERE c.date = '2022-12-22'
  AND c.conference = 'West'
WITH e, c
RETURN
  e.nom           AS equipe,
  c.victoires     AS V,
  c.defaites      AS D,
  c.matchs_joues  AS G,
  CASE WHEN c.matchs_joues = 0 OR c.matchs_joues IS NULL THEN NULL
       ELSE round(c.victoires * 1000.0 / c.matchs_joues) / 1000.0
  END             AS win_pct_calcule,
  c.home_record   AS domicile,
  c.road_record   AS exterieur
ORDER BY c.victoires DESC, c.defaites ASC;


// 2.3 Evolution du classement d'une equipe sur une saison
MATCH (e:Equipe {abbreviation: 'GSW'})-[:A_CLASSEMENT]->(c:Classement)
WHERE c.season_id = 22022
RETURN
  c.date         AS date,
  c.victoires    AS V,
  c.defaites     AS D,
  c.home_record  AS domicile,
  c.road_record  AS exterieur
ORDER BY c.date;


// 2.4 Comparaison de deux equipes (head-to-head)
MATCH (dom:Equipe {abbreviation: 'LAL'})-[rd:DISPUTE]->(m:Match)
MATCH (vis:Equipe {abbreviation: 'BOS'})-[rv:VISITE]->(m)
RETURN
  m.date_est          AS date,
  rd.score            AS score_LAL,
  rv.score            AS score_BOS,
  rd.resultat         AS resultat_LAL
ORDER BY m.date_est DESC
LIMIT 10;



// 3.1 Coequipiers d'un joueur sur une saison donnee
MATCH (j1:Joueur)
WHERE j1.nom CONTAINS 'Curry'
WITH j1
MATCH (j1)-[:JOUE_POUR {saison: 2022}]->(e:Equipe)<-[:JOUE_POUR {saison: 2022}]-(j2:Joueur)
WHERE j1 <> j2
RETURN j2.nom AS coequipier, e.nom AS equipe
ORDER BY j2.nom;


// 3.2 Historique des equipes d'un joueur (toutes les saisons)
MATCH (j:Joueur)
WHERE j.nom CONTAINS 'Durant'
WITH j
MATCH (j)-[r:JOUE_POUR]->(e:Equipe)
RETURN
  j.nom        AS joueur,
  e.nom        AS equipe,
  r.saison     AS saison,
  r.actif      AS contrat_actif
ORDER BY r.saison;


// 3.3 Joueurs ayant joue pour plusieurs equipes (trades)
MATCH (j:Joueur)-[:JOUE_POUR]->(e:Equipe)
WITH j, count(DISTINCT e) AS nb_equipes, collect(DISTINCT e.nom) AS liste_equipes
WHERE nb_equipes > 1
RETURN j.nom, nb_equipes, liste_equipes
ORDER BY nb_equipes DESC
LIMIT 20;


MATCH (j1:Joueur), (j2:Joueur)
WHERE j1.nom CONTAINS 'Curry'
  AND j2.nom CONTAINS 'James'
  AND j1 <> j2
WITH j1, j2
MATCH chemin = shortestPath((j1)-[:JOUE_POUR*..6]-(j2))
RETURN
  [n IN nodes(chemin) | COALESCE(n.nom, n.id)] AS noeuds_du_chemin,
  length(chemin)                                AS distance;


// 3.5 Equipes les plus connectees (joueurs en commun avec d'autres equipes)
MATCH (e1:Equipe)<-[:JOUE_POUR]-(j:Joueur)-[:JOUE_POUR]->(e2:Equipe)
WHERE e1 <> e2
WITH e1, e2, count(DISTINCT j) AS joueurs_communs
WHERE joueurs_communs >= 2
RETURN
  e1.nom            AS equipe_1,
  e2.nom            AS equipe_2,
  joueurs_communs
ORDER BY joueurs_communs DESC
LIMIT 15;


// -------------------------------------------------------------
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
  AND p.fga IS NOT NULL
  AND p.fta IS NOT NULL
WITH j,
     count(p)   AS nb_matchs,
     sum(p.pts) AS total_pts,
     sum(p.fga) AS total_fga,
     sum(p.fta) AS total_fta
WHERE nb_matchs >= 20
WITH j, nb_matchs, total_pts, total_fga, total_fta,
     2.0 * (total_fga + 0.44 * total_fta) AS denominateur
RETURN
  j.nom     AS joueur,
  nb_matchs,
  CASE WHEN denominateur = 0 OR denominateur IS NULL THEN NULL
       ELSE round(total_pts * 1000.0 / denominateur) / 1000.0
  END       AS true_shooting_pct,
  round(total_pts * 10.0 / nb_matchs) / 10.0 AS pts_par_match
ORDER BY true_shooting_pct DESC
LIMIT 20;


// 4.2 Player Efficiency Rating simplifie (PER approche)
// Formula simplifiee : (PTS + REB + AST + STL + BLK - TOV - (FGA-FGM) - (FTA-FTM)) / MIN
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
  AND p.min_secondes IS NOT NULL
  AND p.min_secondes > 0
WITH j,
     count(p) AS nb_matchs,
     sum(p.pts)                                                   AS s_pts,
     sum(p.reb)                                                   AS s_reb,
     sum(p.ast)                                                   AS s_ast,
     sum(p.stl)                                                   AS s_stl,
     sum(p.blk)                                                   AS s_blk,
     sum(CASE WHEN p.tov IS NOT NULL THEN p.tov ELSE 0 END)       AS s_tov,
     sum(CASE WHEN p.fga IS NOT NULL AND p.fgm IS NOT NULL
              THEN p.fga - p.fgm ELSE 0 END)                      AS s_fgm,
     sum(CASE WHEN p.fta IS NOT NULL AND p.ftm IS NOT NULL
              THEN p.fta - p.ftm ELSE 0 END)                      AS s_ftm,
     sum(p.min_secondes) / 60.0                                   AS total_min
WHERE nb_matchs >= 20
  AND total_min > 0
WITH j, nb_matchs, total_min,
     (s_pts + s_reb + s_ast + s_stl + s_blk - s_tov - s_fgm - s_ftm) AS contributions
RETURN
  j.nom     AS joueur,
  nb_matchs,
  round(total_min / nb_matchs * 10) / 10.0                       AS min_par_match,
  round(contributions * 100.0 / total_min) / 100.0               AS per_simplifie
ORDER BY per_simplifie DESC
LIMIT 20;


// 4.3 Plus gros ecarts de score dans l'histoire du graphe
MATCH (dom:Equipe)-[rd:DISPUTE]->(m:Match)
MATCH (vis:Equipe)-[rv:VISITE]->(m)
WHERE rd.score IS NOT NULL
  AND rv.score IS NOT NULL
WITH dom, vis, m, rd, rv,
     abs(rd.score - rv.score) AS ecart
ORDER BY ecart DESC
LIMIT 10
RETURN
  dom.nom      AS equipe_domicile,
  rd.score     AS score_dom,
  vis.nom      AS equipe_visiteur,
  rv.score     AS score_vis,
  ecart        AS ecart_points,
  m.date_est   AS date,
  m.saison_id  AS saison;

// (top pts + reb + ast combines sur un seul match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m:Match)
WHERE p.pts IS NOT NULL
  AND p.reb IS NOT NULL
  AND p.ast IS NOT NULL
WITH j, m, p,
     p.pts + p.reb + p.ast AS total_pra
ORDER BY total_pra DESC
LIMIT 10
RETURN
  j.nom      AS joueur,
  m.date_est AS date,
  p.pts      AS points,
  p.reb      AS rebonds,
  p.ast      AS passes,
  total_pra  AS pts_reb_ast;


// 5.1 Nombre de noeuds par label
MATCH (n)
WITH labels(n)[0] AS label, count(n) AS nb
RETURN label, nb
ORDER BY nb DESC;

// 5.2 Nombre de relations par type
MATCH ()-[r]->()
WITH type(r) AS type_relation, count(r) AS nb
RETURN type_relation, nb
ORDER BY nb DESC;

// 5.3 Saisons disponibles et nombre de matchs associes
MATCH (s:Saison)-[:CONTIENT]->(m:Match)
WITH s.annee AS annee, count(m) AS nb_matchs
RETURN annee, nb_matchs
ORDER BY annee;

// 5.4 Joueurs les plus actifs (nombre total de matchs joues)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)
WITH j, count(p) AS nb_matchs
ORDER BY nb_matchs DESC
LIMIT 15
RETURN j.nom AS joueur, nb_matchs;

// 5.5 Noeuds potentiellement orphelins (sans aucune relation)
MATCH (n)
WHERE NOT (n)--()
RETURN labels(n)[0] AS label, count(n) AS nb_orphelins
ORDER BY nb_orphelins DESC;

// 5.6 Verifier qu'un match a bien ses deux equipes reliees
MATCH (m:Match)
WITH m,
     size([(e:Equipe)-[:DISPUTE]->(m) | e]) AS nb_dom,
     size([(e:Equipe)-[:VISITE]->(m)  | e]) AS nb_vis
WHERE nb_dom <> 1 OR nb_vis <> 1
RETURN
  m.id       AS match_id,
  m.date_est AS date,
  nb_dom,
  nb_vis
LIMIT 20;

// 5.7 Verifier les invariants statistiques (FGM <= FGA)
MATCH (p:Performance)
WHERE p.fgm IS NOT NULL
  AND p.fga IS NOT NULL
  AND p.fgm > p.fga
RETURN count(p) AS nb_invalides_fgm_fga;

// 5.8 Distribution des points par match pour une saison
MATCH (s:Saison {annee: 2022})-[:CONTIENT]->(m:Match)
MATCH (j:Joueur)-[:REALISE]->(p:Performance)-[:LORS_DE]->(m)
WHERE p.pts IS NOT NULL
WITH
  CASE WHEN p.pts = 0       THEN '00'
       WHEN p.pts <= 9      THEN '01-09'
       WHEN p.pts <= 19     THEN '10-19'
       WHEN p.pts <= 29     THEN '20-29'
       WHEN p.pts <= 39     THEN '30-39'
       WHEN p.pts <= 49     THEN '40-49'
       ELSE                      '50+'
  END AS tranche,
  count(p) AS nb_performances
RETURN tranche, nb_performances
ORDER BY tranche;
