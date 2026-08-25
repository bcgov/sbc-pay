# Partner PubSub provisioning

Bash script that provisions per-partner PubSub topics, a DLQ (topic + pull sub
+ BigQuery-backed table), and IAM. Ops-run, idempotent.

## Setup

```
gcloud auth login
```

Operator needs `pubsub.admin` + `bigquery.admin` on the target project. No
packages to install — script uses `gcloud` + `bq` only.

## Usage

```
./provision.sh plan    <env>                    # dry-run everything
./provision.sh apply   <env>                    # provision all partners
./provision.sh apply   <env> <partner>          # scope to one partner
./provision.sh destroy <env> <partner> --yes-really
```

## Onboarding a partner

1. In `partners.sh`: append the partner's code to `PARTNERS`. If the partner
   has a consumer SA, add a `<code>_<env>) echo "serviceAccount:..." ;;` case
   in `subscribers_for()`.
2. `./provision.sh apply <env> <code>`.
3. On the sbc-pay side: add `<CODE>_PAY_TOPIC` to `vaults.gcp.env` (mapped to
   a 1Password field holding `pay-events-<code>-<env>`), set
   `is_express_checkout_enabled=true` on the corp_types row, redeploy.

## What gets provisioned per partner

- Events topic — `pay-events-<code>-<env>`
- DLQ topic — `pay-events-<code>-<env>-dlq`
- DLQ pull sub — `pay-events-<code>-<env>-dlq-pull` (7-day retention)
- DLQ BQ sub — `pay-events-<code>-<env>-dlq-bq`, writing to a partner-scoped
  BQ table (`partner_pubsub_<env>.pay_events_<code>_<env>_dlq`)
- Publisher IAM on the events topic for sbc-pay's SAs
- Subscriber + BQ-viewer IAM on the events topic / partner's table for any
  configured subscriber members

Per env, a shared dataset `partner_pubsub_<env>` (region
`northamerica-northeast1`) — created once, reused across partners. Per-partner
tables inside it are how access is segregated.
