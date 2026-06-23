# FEC Bulk Data — Silver Layer Field Mapping

> **Purpose:** Mapping dictionary between the FEC bulk data files, the OpenFEC API endpoints, and the canonical Silver Layer field names of a medallion architecture.

---

## Table of Contents

- [Sheet Index](#sheet-index)
- [Mapping Columns](#mapping-columns)
- [COMMON\_MAP Conventions](#common_map-conventions)
- [Committee Master](#1-committee-master)
- [Candidate Master](#2-candidate-master)
- [Contributions by Individuals](#3-contributions-by-individuals)
- [Inter-Committee Transactions](#4-inter-committee-transactions)
- [Committee Contributions to Candidates](#5-committee-contributions-to-candidates)
- [Sources](#sources)

---

## Sheet Index

| Excel Sheet | FEC Bulk File (`bulk-downloads/YYYY/`) |
|---|---|
| Committee master | `cm##.zip` — committee master file |
| Candidate master | `cn##.zip` — candidate master file |
| Contributions by individuals | `indiv##.zip` — individual contributions |
| Inter-committee transactions | `oth##.zip` — any transaction committee-to-committee |
| Cmte contrib to candidates | `pas2##.zip` — contributions from committees to candidates & independent expenditures |

---

## Mapping Columns

| Column | Description |
|---|---|
| `BULK_DOWNLOAD` | Exact field name in the FEC bulk file (fixed-width or pipe-delimited) |
| `FIELD_DESCRIPTION` | Official field description per FEC documentation |
| `API_ENDPOINT` | Equivalent endpoint/parameter in the OpenFEC API (`api.open.fec.gov`) |
| `COMMON_MAP` | Canonical Silver Layer name — identical for the same concept across all sheets |
| `NOTES` | Foreign keys, API limitations, source-file column positions |

---

## COMMON\_MAP Conventions

| Prefix | Fields |
|---|---|
| `com_*` | Committee attributes: `com_id`, `com_name`, `com_city`, `com_state`, `com_zip`, `com_type`, `com_design`, `com_party` |
| `cand_*` | Candidate attributes: `cand_id`, `cand_name`, `cand_party`, `cand_el_yr`, `cand_off`, `cand_off_state` |
| `contrib_*` | Contributor/entity attributes within a transaction: `contrib_name`, `contrib_city`, `contrib_state`, `contrib_zip`, `contrib_emp`, `contrib_occ` |
| `trans_*` | Transaction data: `trans_date`, `trans_amt`, `trans_type` |
| `entity_*` | Generic entity in committee-to-committee transactions: `entity_name`, `entity_tp` |

---

## 1. Committee Master

**FEC bulk file:** `cm##.zip`

| BULK\_DOWNLOAD | FIELD\_DESCRIPTION | API\_ENDPOINT | COMMON\_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Committee ID | `/committees/committee_id` | `com_id` | |
| `CMTE_NM` | Committee name | `/committees/name` | `com_name` | |
| `CMTE_CITY` | City or town | N/A — not exposed in `/committees/` endpoint | `com_city` | Available in bulk file only |
| `CMTE_ST` | State | `/committees/designated_agent_state` | `com_state` | |
| `CMTE_ZIP` | ZIP code | `/committees/designated_agent_zip` | `com_zip` | |
| `CMTE_DSGN` | Committee designation: `A`=Authorized by candidate; `B`=Lobbyist/Registrant PAC; `D`=Leadership PAC; `J`=Joint fundraiser; `P`=Principal campaign committee; `U`=Unauthorized | `/committees/designation`, `/committees/designation_full` | `com_design` | |
| `CMTE_TP` | Committee type | `/committees/committee_type`, `/committees/committee_type_full` | `com_type` | Code list: [fec.gov/campaign-finance-data/committee-type-code-descriptions/](https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/) |
| `CMTE_PTY_AFFILIATION` | Committee party | `/committees/party`, `/committees/party_full` | `com_party` | |
| `CAND_ID` | Candidate identification: populated when committee type = `H`, `S` or `P` | `/committees/candidate_ids` | `cand_id` | FK → Candidate master |

---

## 2. Candidate Master

**FEC bulk file:** `cn##.zip`

| BULK\_DOWNLOAD | FIELD\_DESCRIPTION | API\_ENDPOINT | COMMON\_MAP | NOTES |
|---|---|---|---|---|
| `CAND_ID` | Candidate ID | `/candidates/candidate_id` | `cand_id` | |
| `CAND_NAME` | Candidate name | `/candidates/name` | `cand_name` | |
| `CAND_PTY_AFFILIATION` | Party affiliation | `/candidates/party`, `/candidates/party_full` | `cand_party` | |
| `CAND_ELECTION_YR` | Year of election | `/candidates/election_years` | `cand_el_yr` | |
| `CAND_OFFICE_ST` | Candidate state: `H`=state of race; `P`=US; `S`=state of race | `/candidates/state` | `cand_off_state` | |
| `CAND_OFFICE` | Candidate office: `H`=House; `P`=President; `S`=Senate | `/candidates/office`, `/candidates/office_full` | `cand_off` | |
| `CAND_PCC` | Principal campaign committee: FEC ID of the candidate's principal campaign committee for a given election cycle | `/committees/committee_id` | `com_id` | FK → Committee master |

---

## 3. Contributions by Individuals

**FEC bulk file:** `indiv##.zip`

| BULK\_DOWNLOAD | FIELD\_DESCRIPTION | API\_ENDPOINT | COMMON\_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | `/schedules/schedule_a/committee_id` | `com_id` | |
| `TRANSACTION_PGI` | Primary-general indicator: `EYYYY`; `P`=Primary; `G`=General; `O`=Other; `C`=Convention; `R`=Runoff; `S`=Special; `E`=Recount | `/schedules/schedule_a/election_type`, `/schedules/schedule_a/election_type_full` | `election_type` | |
| `NAME` | Contributor/Lender/Transfer name | `/schedules/schedule_a/contributor_name` | `contrib_name` | |
| `CITY` | City | `/schedules/schedule_a/contributor_city` | `contrib_city` | |
| `STATE` | State | `/schedules/schedule_a/contributor_state` | `contrib_state` | |
| `ZIP_CODE` | ZIP code | `/schedules/schedule_a/contributor_zip` | `contrib_zip` | |
| `EMPLOYER` | Employer | `/schedules/schedule_a/contributor_employer` | `contrib_emp` | |
| `OCCUPATION` | Occupation | `/schedules/schedule_a/contributor_occupation` | `contrib_occ` | |
| `TRANSACTION_DT` | Transaction date (`MMDDYYYY` in bulk file; `YYYY-MM-DD` via API) | `/schedules/schedule_a/contribution_receipt_date` | `trans_date` | |
| `TRANSACTION_AMT` | Transaction amount ($) | `/schedules/schedule_a/contribution_receipt_amount` | `trans_amt` | |
| `OTHER_ID` | Other identification number: null for individual contributions; FEC ID when contributor is a candidate or committee | | `other_com_id` | Null for individuals |

---

## 4. Inter-Committee Transactions

**FEC bulk file:** `oth##.zip`

| BULK\_DOWNLOAD | FIELD\_DESCRIPTION | API\_ENDPOINT | COMMON\_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | `/schedules/schedule_a/committee_id`, `/schedules/schedule_b/committee_id` | `com_id` | |
| `TRANSACTION_PGI` | Primary-general indicator | `/schedules/schedule_a/election_type` | `election_type` | |
| `TRANSACTION_TP` | Transaction type | `/schedules/schedule_a/transaction_type` | `trans_type` | |
| `ENTITY_TP` | Entity type | `/schedules/schedule_a/entity_type` | `entity_tp` | |
| `NAME` | Contributor name | `/schedules/schedule_a/contributor_name` | `entity_name` | |
| `CITY` | City | `/schedules/schedule_a/contributor_city` | `contrib_city` | |
| `STATE` | State | `/schedules/schedule_a/contributor_state` | `contrib_state` | |
| `ZIP_CODE` | ZIP code | `/schedules/schedule_a/contributor_zip` | `contrib_zip` | |
| `TRANSACTION_DT` | Transaction date (`MMDDYYYY` in bulk file; `YYYY-MM-DD` via API) | `/schedules/schedule_a/contribution_receipt_date` | `trans_date` | |
| `TRANSACTION_AMT` | Transaction amount ($) | `/schedules/schedule_a/contribution_receipt_amount` | `trans_amt` | |
| `OTHER_ID` | Other identification number: committee that receives the funds | `/schedules/schedule_a/contributor_id` | `other_com_id` | FK → Committee master |
| `SUB_ID` | FEC record number (transaction ID) | `/schedules/schedule_a/transaction_id` | `sub_id` | |

---

## 5. Committee Contributions to Candidates

**FEC bulk file:** `pas2##.zip`

| BULK\_DOWNLOAD | FIELD\_DESCRIPTION | API\_ENDPOINT | COMMON\_MAP | NOTES |
|---|---|---|---|---|
| `CMTE_ID` | Filer identification number | `/schedules/schedule_b/committee_id` | `com_id` | |
| `CAND_ID` | Candidate ID | `/schedules/schedule_b/candidate_id` | `cand_id` | FK → Candidate master |
| `TRANSACTION_PGI` | Primary-general indicator | `/schedules/schedule_b/election_type` | `election_type` | |
| `TRANSACTION_TP` | Transaction type | `/schedules/schedule_b/transaction_type` | `trans_type` | |
| `ENTITY_TP` | Entity type | `/schedules/schedule_b/entity_type` | `entity_tp` | |
| `NAME` | Contributor name (disbursement recipient) | `/schedules/schedule_b/recipient_name` | `entity_name` | |
| `CITY` | City | `/schedules/schedule_b/recipient_city` | `contrib_city` | |
| `STATE` | State | `/schedules/schedule_b/recipient_state` | `contrib_state` | |
| `ZIP_CODE` | ZIP code | `/schedules/schedule_b/recipient_zip` | `contrib_zip` | |
| `TRANSACTION_DT` | Transaction date (`MMDDYYYY` in bulk file; `YYYY-MM-DD` via API) | `/schedules/schedule_b/disbursement_date` | `trans_date` | |
| `TRANSACTION_AMT` | Transaction amount ($) | `/schedules/schedule_b/disbursement_amount` | `trans_amt` | |
| `OTHER_ID` | Other identification number: committee that receives the funds | `/schedules/schedule_b/recipient_committee_id` | `other_com_id` | FK → Committee master |
| `SUB_ID` | FEC record number (transaction ID) | `/schedules/schedule_b/transaction_id` | `sub_id` | |

---

## Sources

| Resource | Link |
|---|---|
| FEC Bulk Data | [fec.gov/data/browse-data/?tab=bulk-data](https://www.fec.gov/data/browse-data/?tab=bulk-data) |
| OpenFEC API | [api.open.fec.gov/developers/](https://api.open.fec.gov/developers/) |
