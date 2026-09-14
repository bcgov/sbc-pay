#!/usr/bin/env bash
#
# Provision native Pub/Sub webhook delivery for partners that have a webhook
# configured in partners.sh. This script expects provision.sh to have already
# created the partner event topic and its partner-specific DLQ.
#
# Usage:
#   ./provision-webhooks.sh plan    <env> [partner]
#   ./provision-webhooks.sh apply   <env> [partner]
#   ./provision-webhooks.sh destroy <env> <partner> --yes-really

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/partners.sh"

TOPIC_PREFIX="pay-events"
MAX_DELIVERY_ATTEMPTS="10"
MIN_RETRY_DELAY="10s"
MAX_RETRY_DELAY="600s"

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

[[ $# -lt 2 ]] && usage

CMD="$1"
ENV="$2"
PARTNER_FILTER="${3:-}"
FLAG="${4:-}"

case "$CMD" in
    plan|apply|destroy) ;;
    *) usage ;;
esac

source "$CONFIG"

PROJECT="$(project_id_for_env "$ENV")"
if [[ -z "$PROJECT" || "$PROJECT" == TODO* ]]; then
    echo "error: no project_id configured for env '$ENV' in partners.sh" >&2
    exit 1
fi

PUBSUB_AGENT="serviceAccount:service-$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')@gcp-sa-pubsub.iam.gserviceaccount.com"
WEBHOOK_DELIVERY_SA_NAME="$(webhook_delivery_sa_name_for_env "$ENV")"
WEBHOOK_DELIVERY_SA_EMAIL="${WEBHOOK_DELIVERY_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

run() {
    if [[ "$CMD" == "plan" ]]; then
        echo "  [would run] $*"
    else
        "$@"
    fi
}

topic_exists() {
    gcloud pubsub topics describe "$1" --project="$PROJECT" &>/dev/null
}

sub_exists() {
    gcloud pubsub subscriptions describe "$1" --project="$PROJECT" &>/dev/null
}

ensure_delivery_service_account() {
    if gcloud iam service-accounts describe "$WEBHOOK_DELIVERY_SA_EMAIL" --project="$PROJECT" &>/dev/null; then
        echo "  [=] delivery service account exists: $WEBHOOK_DELIVERY_SA_EMAIL"
    else
        echo "  [+] create delivery service account: $WEBHOOK_DELIVERY_SA_EMAIL"
        run gcloud iam service-accounts create "$WEBHOOK_DELIVERY_SA_NAME" \
            --project="$PROJECT" \
            --display-name="Partner payment-event webhook delivery" \
            --quiet
    fi

    echo "  [+] grant Token Creator -> $PUBSUB_AGENT on $WEBHOOK_DELIVERY_SA_EMAIL"
    run gcloud iam service-accounts add-iam-policy-binding "$WEBHOOK_DELIVERY_SA_EMAIL" \
        --project="$PROJECT" \
        --member="$PUBSUB_AGENT" \
        --role="roles/iam.serviceAccountTokenCreator" \
        --quiet >/dev/null
}

grant_dlq_permissions() {
    local source_sub="$1" dlq_topic="$2"

    echo "  [+] grant Pub/Sub publisher -> $PUBSUB_AGENT on $dlq_topic"
    run gcloud pubsub topics add-iam-policy-binding "$dlq_topic" \
        --project="$PROJECT" \
        --member="$PUBSUB_AGENT" \
        --role="roles/pubsub.publisher" \
        --quiet >/dev/null

    echo "  [+] grant Pub/Sub subscriber -> $PUBSUB_AGENT on $source_sub"
    run gcloud pubsub subscriptions add-iam-policy-binding "$source_sub" \
        --project="$PROJECT" \
        --member="$PUBSUB_AGENT" \
        --role="roles/pubsub.subscriber" \
        --quiet >/dev/null
}

ensure_webhook_subscription() {
    local topic="$1" dlq="$2" endpoint="$3" audience="$4"
    local sub_name="${topic}-webhook-push"

    if sub_exists "$sub_name"; then
        echo "  [=] webhook push subscription exists: $sub_name"
    else
        echo "  [+] create webhook push subscription: $sub_name -> $endpoint"
        run gcloud pubsub subscriptions create "$sub_name" \
            --project="$PROJECT" \
            --topic="$topic" \
            --push-endpoint="$endpoint" \
            --push-auth-service-account="$WEBHOOK_DELIVERY_SA_EMAIL" \
            --push-auth-token-audience="$audience" \
            --push-no-wrapper \
            --push-no-wrapper-write-metadata \
            --dead-letter-topic="$dlq" \
            --max-delivery-attempts="$MAX_DELIVERY_ATTEMPTS" \
            --min-retry-delay="$MIN_RETRY_DELAY" \
            --max-retry-delay="$MAX_RETRY_DELAY" \
            --quiet
    fi

    grant_dlq_permissions "$sub_name" "$dlq"
}

delete_webhook_subscription() {
    local topic="$1" sub_name="${1}-webhook-push"
    if ! sub_exists "$sub_name"; then
        echo "  [=] webhook push subscription already absent: $sub_name"
        return
    fi
    echo "  [-] delete webhook push subscription: $sub_name"
    run gcloud pubsub subscriptions delete "$sub_name" --project="$PROJECT" --quiet
}

apply_partner() {
    local code="$1" topic dlq endpoint audience
    topic="${TOPIC_PREFIX}-${code}-${ENV}"
    dlq="${topic}-dlq"
    endpoint="$(webhook_url_for "$code" "$ENV")"

    if [[ -z "$endpoint" ]]; then
        echo "== partner=$code env=$ENV =="
        echo "  [=] no webhook configured; skipping"
        return
    fi

    audience="$(webhook_audience_for "$code" "$ENV")"
    [[ -z "$audience" ]] && audience="$endpoint"

    if ! topic_exists "$topic" || ! topic_exists "$dlq"; then
        echo "error: expected event topic and DLQ for '$code'. Run provision.sh apply $ENV $code first." >&2
        exit 1
    fi

    echo "== partner=$code env=$ENV project=$PROJECT =="
    ensure_webhook_subscription "$topic" "$dlq" "$endpoint" "$audience"
}

destroy_partner() {
    local code="$1" topic="${TOPIC_PREFIX}-${1}-${ENV}"
    echo "== DESTROY WEBHOOK partner=$code env=$ENV project=$PROJECT =="
    delete_webhook_subscription "$topic"
}

if [[ -n "$PARTNER_FILTER" ]]; then
    found=0
    for partner in $PARTNERS; do
        [[ "$partner" == "$PARTNER_FILTER" ]] && { found=1; break; }
    done
    [[ $found -eq 0 ]] && { echo "error: partner '$PARTNER_FILTER' not in PARTNERS" >&2; exit 1; }
    SCOPE="$PARTNER_FILTER"
else
    SCOPE="$PARTNERS"
fi

case "$CMD" in
    plan|apply)
        ensure_delivery_service_account
        for partner in $SCOPE; do apply_partner "$partner"; done
        ;;
    destroy)
        [[ -z "$PARTNER_FILTER" ]] && { echo "error: destroy requires a partner code" >&2; exit 1; }
        [[ "$FLAG" != "--yes-really" ]] && { echo "error: destroy requires --yes-really" >&2; exit 1; }
        destroy_partner "$PARTNER_FILTER"
        ;;
esac

echo
echo "done."
