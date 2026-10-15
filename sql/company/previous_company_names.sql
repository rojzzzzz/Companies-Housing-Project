CREATE TABLE IF NOT EXISTS staging.previous_company_names (
    ceased_on DATE NOT NULL,
    effective_from DATE,
    name TEXT NOT NULL,
    company_number INT NOT NULL,
    PRIMARY KEY (name, company_number)
);