import pandas as pd

def company_tables(company: dict):
    company_data = {}
    company_row = {
        "company_number": company.get("company_number"),
        "company_name": company.get("company_name"),
        "company_status": company.get("company_status"),
        "company_type": company.get("type"),
        "jurisdiction": company.get("jurisdiction"),
        "date_of_creation": company.get("date_of_creation"),

        "can_file": company.get("can_file"),
        "has_been_liquidated": company.get("has_been_liquidated"),
        "has_charges": company.get("has_charges"),
        "has_insolvency_history": company.get("has_insolvency_history"),
        "registered_office_is_in_dispute": company.get(
            "registered_office_is_in_dispute"
        ),
        "undeliverable_registered_office_address": company.get(
            "undeliverable_registered_office_address"
        ),
        "has_super_secure_pscs": company.get("has_super_secure_pscs"),

        "last_full_members_list_date": company.get(
            "last_full_members_list_date"
        ),

        # Accounts
        "accounting_reference_day": (
            company.get("accounts", {})
            .get("accounting_reference_date", {})
            .get("day")
        ),
        "accounting_reference_month": (
            company.get("accounts", {})
            .get("accounting_reference_date", {})
            .get("month")
        ),

        "last_accounts_made_up_to": (
            company.get("accounts", {})
            .get("last_accounts", {})
            .get("made_up_to")
        ),
        "last_accounts_period_start_on": (
            company.get("accounts", {})
            .get("last_accounts", {})
            .get("period_start_on")
        ),
        "last_accounts_period_end_on": (
            company.get("accounts", {})
            .get("last_accounts", {})
            .get("period_end_on")
        ),
        "last_accounts_type": (
            company.get("accounts", {})
            .get("last_accounts", {})
            .get("type")
        ),

        "next_accounts_due_on": (
            company.get("accounts", {})
            .get("next_accounts", {})
            .get("due_on")
        ),
        "next_accounts_period_start_on": (
            company.get("accounts", {})
            .get("next_accounts", {})
            .get("period_start_on")
        ),
        "next_accounts_period_end_on": (
            company.get("accounts", {})
            .get("next_accounts", {})
            .get("period_end_on")
        ),
        "next_accounts_overdue": (
            company.get("accounts", {})
            .get("next_accounts", {})
            .get("overdue")
        ),

        "accounts_next_due": (
            company.get("accounts", {})
            .get("next_due")
        ),
        "accounts_next_made_up_to": (
            company.get("accounts", {})
            .get("next_made_up_to")
        ),
        "accounts_overdue": (
            company.get("accounts", {})
            .get("overdue")
        ),

        # Confirmation statement
        "confirmation_last_made_up_to": (
            company.get("confirmation_statement", {})
            .get("last_made_up_to")
        ),
        "confirmation_next_due": (
            company.get("confirmation_statement", {})
            .get("next_due")
        ),
        "confirmation_next_made_up_to": (
            company.get("confirmation_statement", {})
            .get("next_made_up_to")
        ),
        "confirmation_overdue": (
            company.get("confirmation_statement", {})
            .get("overdue")
        ),

        # Registered office address
        "address_line_1": (
            company.get("registered_office_address", {})
            .get("address_line_1")
        ),
        "address_line_2": (
            company.get("registered_office_address", {})
            .get("address_line_2")
        ),
        "locality": (
            company.get("registered_office_address", {})
            .get("locality")
        ),
        "postal_code": (
            company.get("registered_office_address", {})
            .get("postal_code")
        ),
        "country": (
            company.get("registered_office_address", {})
            .get("country")
        ),

        # API metadata
        "etag": company.get("etag"),

        "link_self": company.get("links", {}).get("self"),
        "link_filing_history": (
            company.get("links", {})
            .get("filing_history")
        ),
        "link_officers": (
            company.get("links", {})
            .get("officers")
        ),
        "link_exemptions": (
            company.get("links", {})
            .get("exemptions")
        ),
    }
    company_data['company']  = pd.DataFrame([company_row])

    previous_names = company.get("previous_company_names", [])
    df_previous_names = pd.DataFrame(previous_names)
    df_previous_names["company_number"] = company["company_number"]
    company_data['previous_company_names'] = df_previous_names

    sic_codes = company.get("sic_codes", [])
    df_sic_codes = pd.DataFrame({"company_number": [company["company_number"]] * len(sic_codes),
                                 "sic_code": sic_codes})
    company_data['sic_code'] = df_sic_codes

    return company_data

def officers_tables(company_data: dict):
    officers = company_data['officers']
    officers_rows = []

    for officer in officers:
        officer_row = {
            "company_number": company_data["company"]["company_number"],

            "person_number": officer.get("person_number"),
            "name": officer.get("name"),
            "officer_role": officer.get("officer_role"),

            "appointed_on": officer.get("appointed_on"),
            "resigned_on": officer.get("resigned_on"),

            "nationality": officer.get("nationality"),
            "country_of_residence": officer.get("country_of_residence"),

            "is_pre_1992_appointment": officer.get("is_pre_1992_appointment"),

            "birth_month": officer.get("date_of_birth", {}).get("month"),
            "birth_year": officer.get("date_of_birth", {}).get("year"),

            "address_premises": officer.get("address", {}).get("premises"),
            "address_line_1": officer.get("address", {}).get("address_line_1"),
            "address_line_2": officer.get("address", {}).get("address_line_2"),
            "address_locality": officer.get("address", {}).get("locality"),
            "address_region": officer.get("address", {}).get("region"),
            "address_postal_code": officer.get("address", {}).get("postal_code"),
            "address_country": officer.get("address", {}).get("country"),

            "link_self": officer.get("links", {}).get("self"),
            "link_appointment": officer.get("links", {}).get("appointment"),

            "verification_start_on": officer.get("identity_verification_details", {}).get("appointment_verification_start_on"),
            "verification_end_on": officer.get("identity_verification_details", {}).get("appointment_verification_end_on"),

            "etag": officer.get("etag"),
        }
        officers_rows.append(officer_row)

    return pd.DataFrame(officers_rows)

def filings_tables(company_data: dict):
    filling_rows =[]

    for filing in company_data['filings']:

        description_values = filing.get("description_values", {})

        filling_rows.append({
            "company_number": company_data["company"]["company_number"],

            "transaction_id": filing.get("transaction_id"),
            "barcode": filing.get("barcode"),
            "type": filing.get("type"),
            "date": filing.get("date"),
            "category": filing.get("category"),
            "subcategory": filing.get("subcategory"),
            "description": filing.get("description"),
            "pages": filing.get("pages"),
            "paper_filed": filing.get("paper_filed"),
            "action_date": filing.get("action_date"),

            "description_value": description_values.get("description"),
            "change_date": description_values.get("change_date"),
            "officer_name": description_values.get("officer_name"),
            "appointment_date": description_values.get("appointment_date"),
            "new_date": description_values.get("new_date"),
            "date_value": description_values.get("date_value"),
            "old_address": description_values.get("old_address"),
            "new_address": description_values.get("new_address"),
            "termination_date": description_values.get("termination_date"),
            "made_up_date": description_values.get("made_up_date"),

            "link_self": filing.get("links", {}).get("self"),
            "document_metadata": (filing.get("links", {}).get("document_metadata")),
        })

    df_filings = pd.DataFrame(filling_rows)

    capital_rows = []

    for filing in company_data['filings']:
        description_values = filing.get("description_values", {})

        for capital in description_values.get("capital", []):
            capital_rows.append({
                "transaction_id": filing.get("transaction_id"),
                "currency": capital.get("currency"),
                "figure": capital.get("figure"),
            })

    df_filing_capital = pd.DataFrame(capital_rows)

    filings_data = [df_filings, df_filing_capital]
    return filings_data

def psc_tables(company_data: dict):
    psc_list = company_data['persons_with_significant_control']

    psc_rows = []

    for psc in psc_list:
        psc_rows.append({
            "company_number": company_data["company"]["company_number"],

            "etag": psc.get("etag"),
            "name": psc.get("name"),
            "kind": psc.get("kind"),

            "notified_on": psc.get("notified_on"),
            "ceased": psc.get("ceased"),
            "ceased_on": psc.get("ceased_on"),

            "nationality": psc.get("nationality"),
            "country_of_residence": psc.get("country_of_residence"),

            "birth_year": psc.get("date_of_birth", {}).get("year"),

            "title": psc.get('name_elements', {}).get("title"),
            "forename": psc.get("name_elements", {}).get("forename"),
            "surname": psc.get("name_elements", {}).get("surname"),

            "legal_form": psc.get("identification", {}).get("legal_form"),
            "legal_authority": psc.get("identification", {}).get("legal_authority"),
            "country_registered": psc.get("identification", {}).get("country_registered"),
            "place_registered": psc.get("identification", {}).get("place_registered"),
            "registration_number": psc.get("identification", {}).get("registration_number"),

            "address_premises": (
                psc.get("address", {})
                .get("premises")
            ),
            "address_line_1": (
                psc.get("address", {})
                .get("address_line_1")
            ),
            "address_line_2": (
                psc.get("address", {})
                .get("address_line_2")
            ),
            "address_locality": (
                psc.get("address", {})
                .get("locality")
            ),
            "address_region": (
                psc.get("address", {})
                .get("region")
            ),
            "address_postal_code": (
                psc.get("address", {})
                .get("postal_code")
            ),
            "address_country": (
                psc.get("address", {})
                .get("country")
            ),


            "link_self": (
                psc.get("links", {})
                .get("self")
            )
        })

    df_psc = pd.DataFrame(psc_rows)

    nature_rows = []

    for psc in psc_list:
        psc_id = psc.get("links", {}).get('self')

        for nature in psc.get("natures_of_control", []):
            nature_rows.append({
                "psc_id": psc_id,
                "nature_of_control": nature
            })

    df_psc_natures_of_control = pd.DataFrame(nature_rows)

    psc_dfs = [df_psc, df_psc_natures_of_control]
    return psc_dfs
