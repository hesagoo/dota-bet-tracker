-- Заготовка схемы будущей базы analytics.db (пока не используется приложением).
PRAGMA user_version = 1;
CREATE TABLE teams(id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, name TEXT, tag TEXT, region TEXT, updated_at TEXT, UNIQUE(source, source_id));
CREATE TABLE players(id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, nickname TEXT, UNIQUE(source, source_id));
CREATE TABLE team_rosters(team_id INTEGER, player_id INTEGER, role TEXT, from_date TEXT, to_date TEXT);
CREATE TABLE tournaments(id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, name TEXT, tier TEXT, start_date TEXT, end_date TEXT, UNIQUE(source, source_id));
CREATE TABLE matches(id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, tournament_id INTEGER, team_a INTEGER, team_b INTEGER,
                     best_of INTEGER, scheduled_at TEXT, status TEXT, winner INTEGER, score_a INTEGER, score_b INTEGER, fetched_at TEXT, UNIQUE(source, source_id));
CREATE TABLE games(id INTEGER PRIMARY KEY, match_id INTEGER, game_no INTEGER, duration_sec INTEGER, kills_a INTEGER, kills_b INTEGER, radiant_team INTEGER, winner INTEGER);
CREATE TABLE picks_bans(game_id INTEGER, team_id INTEGER, hero_id INTEGER, is_pick INTEGER, order_no INTEGER);
CREATE TABLE player_game_stats(game_id INTEGER, player_id INTEGER, hero_id INTEGER, kills INTEGER, deaths INTEGER, assists INTEGER, gpm INTEGER, xpm INTEGER, net_worth INTEGER);
CREATE TABLE raw_responses(id INTEGER PRIMARY KEY, source TEXT, url TEXT, fetched_at TEXT, body TEXT);
CREATE TABLE predictions(id INTEGER PRIMARY KEY, match_id INTEGER, created_at TEXT, model_version TEXT, stage TEXT, -- 'pre_draft' | 'post_draft'
                         p_team_a REAL, exp_kills REAL, exp_duration_sec REAL, confidence REAL, data_quality REAL, missing TEXT, features_json TEXT, explanation TEXT);
CREATE TABLE prediction_outcomes(prediction_id INTEGER PRIMARY KEY, evaluated_at TEXT, actual_winner INTEGER, actual_kills INTEGER, actual_duration_sec INTEGER, brier REAL, log_loss REAL);
CREATE INDEX idx_matches_sched ON matches(scheduled_at); CREATE INDEX idx_pred_match ON predictions(match_id);
