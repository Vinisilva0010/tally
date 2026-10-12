-- Tally database schema.
-- One row per project; the yearly blocks of the source spreadsheet are
-- unpivoted into a long table so that vintage comparisons are plain SQL.
--
-- Credit amounts are stored as INTEGER thousandths of a credit ("milli").
-- The Isometric registry reports carbon removals to three decimal places,
-- and summing those as floating point gives a different grand total
-- depending on where rounding happens. An audit tool that publishes a
-- total on-chain and invites recomputation cannot have more than one
-- correct answer, so every amount is exact integer arithmetic and is
-- divided by 1000 only for display.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_file (
    id              INTEGER PRIMARY KEY,
    filename        TEXT    NOT NULL,
    sha256          TEXT    NOT NULL UNIQUE,
    dataset_version TEXT    NOT NULL,
    size_bytes      INTEGER NOT NULL,
    sheet_rows      INTEGER NOT NULL,
    ingested_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS project (
    project_id                TEXT PRIMARY KEY,
    registry                  TEXT    NOT NULL,
    name                      TEXT    NOT NULL,
    name_norm                 TEXT    NOT NULL,
    status                    TEXT,
    scope                     TEXT,
    type                      TEXT,
    reduction_removal         TEXT,
    methodology               TEXT,
    methodology_version       TEXT,
    region                    TEXT,
    country                   TEXT    NOT NULL,
    state                     TEXT,
    site_location             TEXT,
    developer                 TEXT,
    owner                     TEXT,
    first_vintage             INTEGER,
    total_issued_milli        INTEGER NOT NULL DEFAULT 0,
    total_retired_milli       INTEGER NOT NULL DEFAULT 0,
    total_remaining_milli     INTEGER NOT NULL DEFAULT 0,
    buffer_deposits_milli     INTEGER NOT NULL DEFAULT 0,
    reversals_covered_milli   INTEGER NOT NULL DEFAULT 0,
    reversals_uncovered_milli INTEGER NOT NULL DEFAULT 0,
    buffer_released_milli     INTEGER NOT NULL DEFAULT 0,
    pers_milli                INTEGER NOT NULL DEFAULT 0,
    registry_arb_wa           TEXT,
    arb_wa_project            TEXT,
    arb_wa_status             TEXT,
    arb_wa_id                 TEXT,
    poa_id                    TEXT,
    poa_status                TEXT,
    -- Links back to the issuing registry's own record. A verification
    -- tool must be able to point at its sources, so every finding can
    -- carry the two registry pages a reader needs to check it.
    registry_documents        TEXT,
    project_website           TEXT,
    source_file_id            INTEGER NOT NULL REFERENCES source_file (id)
);

CREATE INDEX IF NOT EXISTS idx_project_name_norm ON project (name_norm);
CREATE INDEX IF NOT EXISTS idx_project_registry  ON project (registry);
CREATE INDEX IF NOT EXISTS idx_project_country   ON project (country);

-- Yearly series. `kind` keeps the four blocks in one shape:
--   issued_vintage    credits issued, by the year the reduction occurred
--   retired_year      credits retired or cancelled, by year of retirement
--   remaining_vintage credits still outstanding, by vintage
--   issued_issue_year credits issued, by the year the registry issued them
CREATE TABLE IF NOT EXISTS credit_year (
    project_id    TEXT    NOT NULL REFERENCES project (project_id),
    kind          TEXT    NOT NULL,
    year          INTEGER NOT NULL,
    credits_milli INTEGER NOT NULL,
    PRIMARY KEY (project_id, kind, year)
);

CREATE INDEX IF NOT EXISTS idx_credit_year_lookup
    ON credit_year (kind, year, credits_milli);
