# 4. Personal data stops at the door

Status: accepted

Analysts and dashboards need client positions, not names. Client ids become HMAC keys when files land;
remittance text is redacted to the call reference and key; names, contact details and IBANs live in the
`pii` vault, which no analyst role can read. Seeing who a client is goes through a security-definer function
that checks the role, needs a reason and logs the attempt either way. A dbt test fails any build in which a
mart contains a personal column. The key is fingerprinted in the database, so loading with another key fails
instead of giving clients a second identity. Erasure deletes a prospect's data; an investor's is kept for the
retention period the law requires, and the decision is recorded.
