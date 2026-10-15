CREATE TABLE IF NOT EXISTS staging.sic_code (
    company_number INT NOT NULL,
    sic_code INT,
    PRIMARY KEY (company_number, sic_code)
);