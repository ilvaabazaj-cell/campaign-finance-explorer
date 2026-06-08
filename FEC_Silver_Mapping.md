# FEC Bulk Data — Silver Layer Field Mapping

Mapping dictionary between the FEC bulk data files, the OpenFEC API endpoints, and the canonical Silver Layer field names of a medallion architecture.

> An Excel version of this mapping (`FEC_Silver_Mapping.xlsx`) is available in the repository for offline use.

## Sheets and corresponding FEC files

| Sheet | FEC bulk file | Description |
|---|---|---|
| [Committee master](#committee-master) | `cm##.zip` | Committee master file. One record per committee registered with the FEC. |
| [Candidate master](#candidate-master) | `cn##.zip` | Candidate master file. One record per registered candidate or candidate appearing on a state ballot. |
| [Contributions by individuals](#contributions-by-individuals) | `indiv##.zip` | Each contribution from an individual to a federal committee. |
| [Candidate-committee linkages](#candidate-committee-linkages) | `ccl##.zip` | One record per candidate-to-committee linkage. |
| [Inter-committee transactions](#inter-committee-transactions) | `oth##.zip` | Any transaction (contribution, transfer, etc.) between federal committees. |
| [Cmte contrib to candidates](#cmte-contrib-to-candidates) | `pas2##.zip` | Contributions from committees to candidates and independent expenditures. |
| [PAC summary](#pac-summary) | `webk##.zip` | Overall receipts and disbursements for each PAC and party committee. Fixed-width file (column positions in Notes). |

## Mapping columns

| Column | Meaning |
|---|---|
| `BULK_DOWNLOAD` | Exact field name in the FEC bulk file (fixed-width or pipe-delimited) |
| `FIELD_DESCRIPTION` | Official field description per FEC documentation |
| `API_ENDPOINT` | Equivalent endpoint/parameter in the OpenFEC API (api.open.fec.gov) |
| `COMMON_MAP` | Canonical Silver Layer name — identical for the same concept across all sheets |
| `NOTES` | Foreign keys, API limitations, source-file column positions |

## COMMON_MAP conventions

| Prefix | Attributes |
|---|---|
| `com_*` | Committee: com_id, com_name, com_city, com_state, com_zip, com_type, com_design, com_party |
| `cand_*` | Candidate: cand_id, cand_name, cand_party, cand_el_yr, cand_off, cand_off_state |
| `contrib_*` | Contributor/entity within a transaction: contrib_name, contrib_city, contrib_state, contrib_zip, contrib_emp, contrib_occ |
| `trans_*` | Transaction data: trans_date, trans_amt, trans_type |
| `total_*` | PAC summary aggregates: total_receipts, total_disbursements, total_indv_contrib, total_pac_contrib |
| `entity_*` | Generic entity in committee-to-committee transactions: entity_name, entity_tp |

**Architecture note** — `com_id` and `com_name` are already mapped from *Committee master*. The *PAC summary* (`webk`) file attaches the financial totals to `com_id`; do not duplicate identity fields in the Silver table.

## Committee master

**Source file:** `cm##.zip` — Committee master file. One record per committee registered with the FEC.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Committee ID | /committees/committee_id | `com_id` |  |
| `CMTE_NM` | Committee name | /committees/name | `com_name` |  |
| `CMTE_CITY` | City or town | N/A — not exposed in /committees/ endpoint | `com_city` | Available in bulk file only |
| `CMTE_ST` | State | /committees/designated_agent_state | `com_state` |  |
| `CMTE_ZIP` | ZIP code | /committees/designated_agent_zip | `com_zip` |  |
| `CMTE_DSGN` | Committee designation: A=Authorized by candidate; B=Lobbyist/Registrant PAC; D=Leadership PAC; J=Joint fundraiser; P=Principal campaign committee; U=Unauthorized | /committees/designation, /committees/designation_full | `com_design` |  |
| `CMTE_TP` | Committee type | /committees/committee_type, /committees/committee_type_full | `com_type` | Code list: fec.gov/campaign-finance-data/committee-type-code-descriptions/ |
| `CMTE_PTY_AFFILIATION` | Committee party | /committees/party, /committees/party_full | `com_party` |  |
| `CAND_ID` | Candidate identification: populated when committee type = H, S or P | /committees/candidate_ids | `cand_id` | FK → Candidate master |

## Candidate master

**Source file:** `cn##.zip` — Candidate master file. One record per registered candidate or candidate appearing on a state ballot.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CAND_ID` | Candidate ID | /candidates/candidate_id | `cand_id` |  |
| `CAND_NAME` | Candidate name | /candidates/name | `cand_name` |  |
| `CAND_PTY_AFFILIATION` | Party affiliation | /candidates/party, /candidates/party_full | `cand_party` |  |
| `CAND_ELECTION_YR` | Year of election | /candidates/election_years | `cand_el_yr` |  |
| `CAND_OFFICE_ST` | Candidate state: H=state of race; P=US; S=state of race | /candidates/state | `cand_off_state` |  |
| `CAND_OFFICE` | Candidate office: H=House; P=President; S=Senate | /candidates/office, /candidates/office_full | `cand_off` |  |
| `CAND_PCC` | Principal campaign committee: FEC ID of the candidate's principal campaign committee for a given election cycle | /committees/committee_id | `com_id` | FK → Committee master |

## Contributions by individuals

**Source file:** `indiv##.zip` — Each contribution from an individual to a federal committee.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | /schedules/schedule_a/committee_id | `com_id` |  |
| `TRANSACTION_PGI` | Primary-general indicator: EYYYY; P=Primary; G=General; O=Other; C=Convention; R=Runoff; S=Special; E=Recount | /schedules/schedule_a/election_type, /schedules/schedule_a/election_type_full | `election_type` |  |
| `NAME` | Contributor/Lender/Transfer name | /schedules/schedule_a/contributor_name | `contrib_name` |  |
| `CITY` | City | /schedules/schedule_a/contributor_city | `contrib_city` |  |
| `STATE` | State | /schedules/schedule_a/contributor_state | `contrib_state` |  |
| `ZIP_CODE` | ZIP code | /schedules/schedule_a/contributor_zip | `contrib_zip` |  |
| `EMPLOYER` | Employer | /schedules/schedule_a/contributor_employer | `contrib_emp` |  |
| `OCCUPATION` | Occupation | /schedules/schedule_a/contributor_occupation | `contrib_occ` |  |
| `TRANSACTION_DT` | Transaction date (MMDDYYYY in bulk file; YYYY-MM-DD via API) | /schedules/schedule_a/contribution_receipt_date | `trans_date` |  |
| `TRANSACTION_AMT` | Transaction amount ($) | /schedules/schedule_a/contribution_receipt_amount | `trans_amt` |  |
| `OTHER_ID` | Other identification number: null for individual contributions; FEC ID when contributor is a candidate or committee | — | `other_com_id` | Null for individuals |

## Candidate-committee linkages

**Source file:** `ccl##.zip` — One record per candidate-to-committee linkage.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CAND_ID` | Candidate identification | /candidates/candidate_id, /committees/candidate_ids | `cand_id` |  |
| `CAND_ELECTION_YR` | Candidate election year | /candidates/election_year | `cand_el_yr` |  |
| `FEC_ELECTION_YR` | FEC election year | /committees/cycles, /candidates/cycles | `fec_el_yr` |  |
| `CMTE_ID` | Committee identification | /committees/committee_id | `com_id` | FK → Committee master |
| `CMTE_TP` | Committee type | /committees/committee_type, /committees/committee_type_full | `com_type` | Code list: fec.gov/campaign-finance-data/committee-type-code-descriptions/ |
| `CMTE_DSGN` | Committee designation: A=Authorized by candidate; B=Lobbyist/Registrant PAC; D=Leadership PAC; J=Joint fundraiser; P=Principal campaign committee; U=Unauthorized | /committees/designation, /committees/designation_full | `com_design` |  |

## Inter-committee transactions

**Source file:** `oth##.zip` — Any transaction (contribution, transfer, etc.) between federal committees.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | /schedules/schedule_a/committee_id, /schedules/schedule_b/committee_id | `com_id` |  |
| `TRANSACTION_PGI` | Primary-general indicator | /schedules/schedule_a/election_type | `election_type` |  |
| `TRANSACTION_TP` | Transaction type | /schedules/schedule_a/transaction_type | `trans_type` |  |
| `ENTITY_TP` | Entity type | /schedules/schedule_a/entity_type | `entity_tp` |  |
| `NAME` | Contributor name | /schedules/schedule_a/contributor_name | `entity_name` |  |
| `CITY` | City | /schedules/schedule_a/contributor_city | `contrib_city` |  |
| `STATE` | State | /schedules/schedule_a/contributor_state | `contrib_state` |  |
| `ZIP_CODE` | ZIP code | /schedules/schedule_a/contributor_zip | `contrib_zip` |  |
| `TRANSACTION_DT` | Transaction date (MMDDYYYY in bulk file; YYYY-MM-DD via API) | /schedules/schedule_a/contribution_receipt_date | `trans_date` |  |
| `TRANSACTION_AMT` | Transaction amount ($) | /schedules/schedule_a/contribution_receipt_amount | `trans_amt` |  |
| `OTHER_ID` | Other identification number: committee that receives the funds | /schedules/schedule_a/contributor_id | `other_com_id` | FK → Committee master |
| `SUB_ID` | FEC record number (transaction ID) | /schedules/schedule_a/transaction_id | `sub_id` |  |

## Cmte contrib to candidates

**Source file:** `pas2##.zip` — Contributions from committees to candidates and independent expenditures.

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | /schedules/schedule_b/committee_id | `com_id` |  |
| `CAND_ID` | Candidate ID | /schedules/schedule_b/candidate_id | `cand_id` | FK → Candidate master |
| `TRANSACTION_PGI` | Primary-general indicator | /schedules/schedule_b/election_type | `election_type` |  |
| `TRANSACTION_TP` | Transaction type | /schedules/schedule_b/transaction_type | `trans_type` |  |
| `ENTITY_TP` | Entity type | /schedules/schedule_b/entity_type | `entity_tp` |  |
| `NAME` | Contributor name (disbursement recipient) | /schedules/schedule_b/recipient_name | `entity_name` |  |
| `CITY` | City | /schedules/schedule_b/recipient_city | `contrib_city` |  |
| `STATE` | State | /schedules/schedule_b/recipient_state | `contrib_state` |  |
| `ZIP_CODE` | ZIP code | /schedules/schedule_b/recipient_zip | `contrib_zip` |  |
| `TRANSACTION_DT` | Transaction date (MMDDYYYY in bulk file; YYYY-MM-DD via API) | /schedules/schedule_b/disbursement_date | `trans_date` |  |
| `TRANSACTION_AMT` | Transaction amount ($) | /schedules/schedule_b/disbursement_amount | `trans_amt` |  |
| `OTHER_ID` | Other identification number: committee that receives the funds | /schedules/schedule_b/recipient_committee_id | `other_com_id` | FK → Committee master |
| `SUB_ID` | FEC record number (transaction ID) | /schedules/schedule_b/transaction_id | `sub_id` |  |

## PAC summary

**Source file:** `webk##.zip` — Overall receipts and disbursements for each PAC and party committee. Fixed-width file (column positions in Notes).

| BULK_DOWNLOAD | FIELD_DESCRIPTION | API_ENDPOINT | COMMON_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | /totals/pac-party/committee_id | `com_id` | Column 1 |
| `CMTE_NM` | Committee name | N/A — not exposed in /totals/ endpoint | `com_name` | Column 2; retrieved from Committee master via com_id |
| `TTL_RECEIPTS` | Total receipts | /totals/pac-party/receipts | `total_receipts` | Column 6 |
| `INDV_CONTRIB` | Contributions from individuals | /totals/pac-party/individual_itemized_contributions | `total_indv_contrib` | Column 8 |
| `OTHER_POL_CMTE_CONTRIB` | Contributions from other PACs | /totals/pac-party/other_political_committee_contributions | `total_pac_contrib` | Column 9 |
| `TTL_DISB` | Total disbursements | /totals/pac-party/disbursements | `total_disbursements` | Column 13 |
| `COH_COP` | Cash on hand, close of period | /totals/pac-party/cash_on_hand_end_period | `cash_on_hand` | Column 20 |
| `IND_EXP` | Independent expenditures | /totals/pac-party/independent_expenditures | `independent_exp` | Column 24 |
| `NET_CONTRIB` | Net contributions (net of refunds) | /totals/pac-party/net_contributions | `net_contrib` | Column 26 |
| `CVG_END_DT` | Coverage end date | /totals/pac-party/coverage_end_date | `coverage_end_date` | Column 27 |

## Sources

- Bulk data: <https://www.fec.gov/data/browse-data/?tab=bulk-data>
- OpenFEC API: <https://api.open.fec.gov/developers/>
