# Partner PubSub provisioning

Bash scripts that provision per-partner Pub/Sub topics, DLQs, IAM, and optional
native Pub/Sub webhook delivery.

## Setup

```bash
gcloud auth login
```

The operator needs `pubsub.admin` + `bigquery.admin` on the target project.
Webhook provisioning also needs `iam.serviceAccountAdmin` (to create the delivery
SA and grant `roles/iam.serviceAccountTokenCreator`).
No packages to install — the scripts use `gcloud` and `bq` only.

---

## Adding a new partner

All partner configuration lives in **`partners.sh`**. Edit that file, then run
the provision scripts. Nothing else needs to change.

### Step 1 — Edit `partners.sh`

**1a. Register the partner code**

Add the code to the `PARTNERS` variable (space-separated, lowercase):

```bash
PARTNERS="sites corp"   # was: PARTNERS="sites"
```

The code drives all resource names: `pay-events-<code>-<env>`.

**1b. Add subscriber IAM** (the partner's SA that will subscribe to the topic)

If the partner will pull events directly from the topic, add their service account.
Leave empty if they receive events via webhook instead (step 2 below).

```bash
subscribers_for() {
    case "${1}_${2}" in
        ...
        corp_dev)   echo "serviceAccount:sa-consumer@corp-dev.iam.gserviceaccount.com" ;;
        corp_test)  echo "serviceAccount:sa-consumer@corp-test.iam.gserviceaccount.com" ;;
        corp_prod)  echo "serviceAccount:sa-consumer@corp-prod.iam.gserviceaccount.com" ;;
        *)          echo "" ;;
    esac
}
```

**1c. Add a webhook URL** (only if the partner wants push delivery)

Leave empty to skip webhook provisioning for that env.

```bash
webhook_url_for() {
    case "${1}_${2}" in
        ...
        corp_dev)   echo "https://corp-dev.example.com/pay-events" ;;
        corp_test)  echo "https://corp-test.example.com/pay-events" ;;
        corp_prod)  echo "https://corp.example.com/pay-events" ;;
        *)          echo "" ;;
    esac
}
```

**1d. Add an audience override** (optional — only if different from the webhook URL)

Pub/Sub mints an OIDC JWT for every push request. The audience in that JWT
defaults to the webhook URL. Override it here only if the partner's receiver
validates a different audience value.

```bash
webhook_audience_for() {
    case "${1}_${2}" in
        ...
        corp_dev)   echo "" ;;   # empty = use webhook URL as audience
        corp_test)  echo "" ;;
        corp_prod)  echo "" ;;
        *)          echo "" ;;
    esac
}
```

### Step 2 — Provision topics and IAM

```bash
# Dry-run first to see what will be created:
./provision.sh plan dev corp

# Apply:
./provision.sh apply dev corp
```

This creates:
- Topic: `pay-events-corp-dev`
- DLQ topic: `pay-events-corp-dev-dlq`
- DLQ pull subscription (7-day retention)
- DLQ BigQuery subscription → `partner_pubsub_dev.pay_events_corp_dev_dlq`
- Publisher IAM on the topic for sbc-pay's service accounts
- Subscriber IAM for any SA configured in `subscribers_for()` above

### Step 3 — Provision webhook delivery (if you set a URL in step 1c)

```bash
# Dry-run first:
./provision-webhooks.sh plan dev corp

# Apply:
./provision-webhooks.sh apply dev corp
```

This creates a push subscription `pay-events-corp-dev-webhook-push` that:
- Delivers to the partner's URL with an OIDC JWT in the `Authorization: Bearer` header
- Retries with exponential backoff (10 s → 10 min, up to 10 attempts)
- Forwards exhausted deliveries to `pay-events-corp-dev-dlq`

### Step 4 — Wire up sbc-pay

Add `<CODE>_PAY_TOPIC` to `vaults.gcp.env`, mapped to the 1Password field
holding `pay-events-<code>-<env>`:

```
CORP_PAY_TOPIC = op://vault/item/pay-events-corp-dev
```

### Step 5 — Share details with the partner

If webhook delivery is enabled, give the partner:

| What | Value |
|---|---|
| Endpoint path | `POST /pay-events` (or whatever URL was configured) |
| OIDC audience | The webhook URL (or the override set in `webhook_audience_for()`) |
| Pub/Sub service account | `pay-events-webhook-delivery@<project>.iam.gserviceaccount.com` |

Their receiver must validate the OIDC JWT on every request and return a `2xx`
only after accepting the event. Any non-`2xx` triggers a retry.
See `pay-ui/examples/payment-event-receiver/` for ready-to-use receiver examples
in Python, Node.js, and Java.

---

## Usage reference

```bash
./provision.sh plan    <env>                         # dry-run all partners
./provision.sh apply   <env>                         # provision all partners
./provision.sh apply   <env> <partner>               # scope to one partner
./provision.sh destroy <env> <partner> --yes-really

./provision-webhooks.sh plan    <env> [partner]
./provision-webhooks.sh apply   <env> [partner]
./provision-webhooks.sh destroy <env> <partner> --yes-really
```

`<env>` is one of `dev`, `test`, `prod`.

---

## What gets provisioned per partner

| Resource | Name |
|---|---|
| Events topic | `pay-events-<code>-<env>` |
| DLQ topic | `pay-events-<code>-<env>-dlq` |
| DLQ pull subscription | `pay-events-<code>-<env>-dlq-pull` |
| DLQ BigQuery subscription | `pay-events-<code>-<env>-dlq-bq` |
| BQ table | `partner_pubsub_<env>.pay_events_<code>_<env>_dlq` |
| Webhook push subscription *(optional)* | `pay-events-<code>-<env>-webhook-push` |

The shared BQ dataset `partner_pubsub_<env>` (region `northamerica-northeast1`)
is created once and reused across all partners. Each partner gets their own table
so read access can be scoped per-partner.
