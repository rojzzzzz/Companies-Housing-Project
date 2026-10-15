CREATE TABLE IF NOT EXISTS staging.capital (
    company_number INT NOT NULL,
    transaction_id TEXT NOT NULL,
    currency VARCHAR(10) NOT NULL,
    figure TEXT NOT NULL,
    PRIMARY KEY (company_number, transaction_id)
);