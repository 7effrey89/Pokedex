-- User database schema v1. Kept separate from the catalog so catalog rebuilds
-- and restores can never overwrite user-owned data.

CREATE TABLE app_user (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE COLLATE NOCASE,
    avatar_path TEXT,
    active_member_id INTEGER,
    password_hash TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE account_member (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    avatar_path TEXT,
    face_encoding TEXT,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE user_card (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    card_id TEXT NOT NULL,
    owned_count INTEGER NOT NULL DEFAULT 0 CHECK (owned_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, card_id)
);

CREATE TABLE user_preference (
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    preference_key TEXT NOT NULL,
    preference_value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, preference_key)
);

CREATE INDEX idx_account_member_user ON account_member(user_id);
CREATE INDEX idx_user_card_card ON user_card(card_id, user_id);

PRAGMA user_version = 1;
