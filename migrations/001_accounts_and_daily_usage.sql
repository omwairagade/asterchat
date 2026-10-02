CREATE TABLE IF NOT EXISTS aster_schema_migrations (
    version VARCHAR(32) NOT NULL PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aster_accounts (
    account_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aster_daily_usage (
    account_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    usage_day DATE NOT NULL,
    messages_used SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_key, usage_day),
    CONSTRAINT fk_aster_usage_account
        FOREIGN KEY (account_key) REFERENCES aster_accounts (account_key)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
