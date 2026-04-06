"""Canonical province labels and reporting references."""

PROVINCE_LABELS = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NT": "Northwest Territories",
    "NS": "Nova Scotia",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
    "Alberta": "Alberta",
    "BritishColumbia": "British Columbia",
    "Manitoba": "Manitoba",
    "NewBrunswick": "New Brunswick",
    "NewfoundlandandLabrador": "Newfoundland and Labrador",
    "NovaScotia": "Nova Scotia",
    "Ontario": "Ontario",
    "PrinceEdwardIsland": "Prince Edward Island",
    "Quebec": "Quebec",
    "Saskatchewan": "Saskatchewan",
}

PROVINCE_REPORTING_RESOURCES = {
    "Alberta": [
        {
            "label": "Alberta RCMP Missing Persons",
            "url": "https://www.rcmp-grc.gc.ca/en/missing-persons",
            "category": "official-reporting",
            "authority_type": "RCMP",
        },
        {
            "label": "Alberta Child and Family Services",
            "url": "https://www.alberta.ca/child-intervention",
            "category": "support",
            "authority_type": "provincial",
        },
    ],
    "British Columbia": [
        {
            "label": "BC RCMP Missing Persons",
            "url": "https://www.rcmp-grc.gc.ca/en/missing-persons",
            "category": "official-reporting",
            "authority_type": "RCMP",
        },
        {
            "label": "VictimLinkBC",
            "url": "https://www2.gov.bc.ca/gov/content/justice/criminal-justice/victims-of-crime/victimlinkbc",
            "category": "support",
            "authority_type": "provincial",
        },
    ],
    "Ontario": [
        {
            "label": "Ontario Provincial Police Missing Persons",
            "url": "https://www.opp.ca/index.php?id=132",
            "category": "official-reporting",
            "authority_type": "police",
        },
        {
            "label": "Ontario 211 Community Supports",
            "url": "https://211ontario.ca/",
            "category": "support",
            "authority_type": "provincial",
        },
    ],
    "Quebec": [
        {
            "label": "Surete du Quebec Missing Persons",
            "url": "https://www.sq.gouv.qc.ca/en/report-an-event/missing-persons/",
            "category": "official-reporting",
            "authority_type": "police",
        }
    ],
}
