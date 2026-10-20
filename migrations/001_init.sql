-- Smart-city traffic research prototype: initial schema (PostgreSQL 16 + PostGIS 3)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE IF NOT EXISTS source_registry (
  source_id TEXT PRIMARY KEY, official_title TEXT, publisher TEXT, dataset_id TEXT, endpoint TEXT,
  license_or_terms_url TEXT, role TEXT, availability_status TEXT, limitations TEXT, updated_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE IF NOT EXISTS source_fetches (
  fetch_id BIGSERIAL PRIMARY KEY, source_id TEXT, raw_file TEXT, url TEXT, params JSONB, retrieved_at TIMESTAMPTZ,
  http_status INT, rows INT, sha256 TEXT, UNIQUE (source_id, raw_file, sha256));

CREATE TABLE IF NOT EXISTS road_links (
  link_id TEXT PRIMARY KEY, link_name TEXT, borough TEXT, owner TEXT, length_m DOUBLE PRECISION,
  geom geometry(LineString, 4326), graph_hash TEXT, first_seen_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS road_links_geom_idx ON road_links USING GIST (geom);

CREATE TABLE IF NOT EXISTS traffic_observations (
  link_id TEXT REFERENCES road_links(link_id), source_timestamp_local TEXT, event_time TIMESTAMPTZ NOT NULL,
  speed_mph DOUBLE PRECISION, travel_time_s DOUBLE PRECISION, status TEXT, valid BOOLEAN,
  raw_file TEXT, ingested_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (link_id, event_time));
CREATE INDEX IF NOT EXISTS traffic_obs_time_idx ON traffic_observations (event_time);

CREATE TABLE IF NOT EXISTS weather_records (
  kind TEXT, hour_utc TIMESTAMPTZ, precipitation_mm DOUBLE PRECISION, temperature_c DOUBLE PRECISION,
  wind_kmh DOUBLE PRECISION, weather_code INT, ingested_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (kind, hour_utc));

CREATE TABLE IF NOT EXISTS collision_records (
  collision_id TEXT PRIMARY KEY, event_time TIMESTAMPTZ, geom geometry(Point, 4326), persons_injured INT,
  source_published_at TIMESTAMPTZ, ingested_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS collision_geom_idx ON collision_records USING GIST (geom);

CREATE TABLE IF NOT EXISTS service_request_records (
  unique_key TEXT PRIMARY KEY, created_at TIMESTAMPTZ, complaint_type TEXT, geom geometry(Point, 4326),
  ingested_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS sr_geom_idx ON service_request_records USING GIST (geom);

CREATE TABLE IF NOT EXISTS event_records (
  event_id TEXT PRIMARY KEY, event_name TEXT, event_type TEXT, start_time TIMESTAMPTZ, end_time TIMESTAMPTZ,
  borough TEXT, location_text TEXT, ingested_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE IF NOT EXISTS forecast_runs (
  forecast_id TEXT PRIMARY KEY, run_id TEXT, mode TEXT CHECK (mode IN ('LIVE','REPLAY','SIMULATION')),
  model_version TEXT, graph_hash TEXT, feature_schema_hash TEXT, origin_utc TIMESTAMPTZ, data_as_of TIMESTAMPTZ,
  generated_at TIMESTAMPTZ DEFAULT now(), payload JSONB);
CREATE TABLE IF NOT EXISTS forecast_values (
  forecast_id TEXT REFERENCES forecast_runs(forecast_id), link_id TEXT, horizon_min INT,
  predicted_mph DOUBLE PRECISION, lower_mph DOUBLE PRECISION, upper_mph DOUBLE PRECISION, observed_mph DOUBLE PRECISION,
  PRIMARY KEY (forecast_id, link_id, horizon_min));

CREATE TABLE IF NOT EXISTS explanation_runs (explanation_id TEXT PRIMARY KEY, forecast_id TEXT, payload JSONB, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS retrieval_runs (retrieval_id TEXT PRIMARY KEY, query TEXT, status TEXT, chunk_ids TEXT[], created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS agent_runs (
  run_id TEXT PRIMARY KEY, thread_id TEXT, mode TEXT, decision TEXT, decision_reasons JSONB, state JSONB,
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS advisory_candidates (candidate_id TEXT PRIMARY KEY, run_id TEXT REFERENCES agent_runs(run_id), payload JSONB);
CREATE TABLE IF NOT EXISTS constraint_checks (candidate_id TEXT, run_id TEXT, checks JSONB, passed BOOLEAN, reasons JSONB, PRIMARY KEY (candidate_id, run_id));
CREATE TABLE IF NOT EXISTS simulation_runs (
  sim_run_id TEXT PRIMARY KEY, scenario TEXT, controller TEXT, seed INT, status TEXT, sumo_version TEXT,
  network_hash TEXT, demand_hash TEXT, metrics JSONB, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS human_reviews (
  review_id BIGSERIAL PRIMARY KEY, advisory_id TEXT, reviewer TEXT, decision TEXT
  CHECK (decision IN ('HUMAN_APPROVED_FOR_SIMULATION','HUMAN_REJECTED','REQUEST_REVISION')),
  comment TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, kind TEXT, params JSONB, status TEXT DEFAULT 'QUEUED', created_at TIMESTAMPTZ DEFAULT now(),
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, exit_code INT, stdout TEXT, stderr TEXT, result JSONB);
CREATE TABLE IF NOT EXISTS experiment_registry (run_id TEXT PRIMARY KEY, kind TEXT, model TEXT, artifact_dir TEXT, metrics JSONB, created_at TIMESTAMPTZ DEFAULT now());

INSERT INTO schema_migrations(version) VALUES ('001_init') ON CONFLICT DO NOTHING;
