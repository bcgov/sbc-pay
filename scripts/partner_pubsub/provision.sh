#!/usr/bin/env bash
#
# Provisioner for partner PubSub topics + IAM).
#
# Usage:
#   ./provision.sh plan    <env>              # dry-run, no writes
#   ./provision.sh apply   <env>              # create/update everything
#   ./provision.sh apply   <env> <partner>    # scope to one partner
#   ./provision.sh destroy <env> <partner> --yes-really
#
# Auth: uses the operator's gcloud login. Run `gcloud auth login` first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/partners.sh"

TOPIC_PREFIX="pay-events"
DLQ_RETENTION="7d"          # ops has a week to inspect failed messages
DLQ_ACK_DEADLINE="60"       # seconds
BQ_LOCATION="northamerica-northeast1"
BQ_DATASET_PREFIX="partner_pubsub"      # one dataset per env: partner_pubsub_<env>

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

# Dry-run wrapper — plan just echoes the command; apply/destroy actually runs it.
run() {
    if [[ "$CMD" == "plan" ]]; then
        echo "  [would run] $*"
    else
        "$@"
    fi
}

# --- topic helpers -------------------------------------------------------- #

topic_exists() {
    gcloud pubsub topics describe "$1" --project="$PROJECT" &>/dev/null
}

sub_exists() {
    gcloud pubsub subscriptions describe "$1" --project="$PROJECT" &>/dev/null
}

ensure_topic() {
    local name="$1" purpose="$2" code="$3"
    if topic_exists "$name"; then
        echo "  [=] topic exists:  $name"
        return
    fi
    echo "  [+] create topic:  $name"
    run gcloud pubsub topics create "$name" \
        --project="$PROJECT" \
        --labels="partner=$code,purpose=$purpose,env=$ENV" \
        --quiet
}

ensure_dlq_pull_sub() {
    local name="$1" topic="$2"
    if sub_exists "$name"; then
        echo "  [=] pull sub exists:  $name"
        return
    fi
    echo "  [+] create pull sub:  $name"
    run gcloud pubsub subscriptions create "$name" \
        --project="$PROJECT" \
        --topic="$topic" \
        --ack-deadline="$DLQ_ACK_DEADLINE" \
        --message-retention-duration="$DLQ_RETENTION" \
        --quiet
}

# gcloud add-iam-policy-binding is natively idempotent — repeats are no-ops.
grant_iam() {
    local topic="$1" role="$2" member="$3"
    echo "  [+] grant $role -> $member on $topic"
    run gcloud pubsub topics add-iam-policy-binding "$topic" \
        --project="$PROJECT" \
        --member="$member" \
        --role="$role" \
        --quiet >/dev/null
}

delete_topic() {
    local name="$1"
    if ! topic_exists "$name"; then
        echo "  [=] topic already absent:  $name"
        return
    fi
    echo "  [-] delete topic:  $name"
    run gcloud pubsub topics delete "$name" --project="$PROJECT" --quiet
}

delete_sub() {
    local name="$1"
    if ! sub_exists "$name"; then
        echo "  [=] pull sub already absent:  $name"
        return
    fi
    echo "  [-] delete pull sub:  $name"
    run gcloud pubsub subscriptions delete "$name" --project="$PROJECT" --quiet
}

# --- BigQuery helpers ----------------------------------------------------- #
#
# Per-partner BQ table so we can grant read access only on a partner's own
# table (segregation), not the whole dataset. Dataset itself is shared per env.

dataset_name() { echo "${BQ_DATASET_PREFIX}_${ENV}"; }
bq_table_name() { echo "pay_events_${1}_${ENV}_dlq"; }
bq_sub_name()   { echo "${TOPIC_PREFIX}-${1}-${ENV}-dlq-bq"; }

bq_dataset_exists() {
    bq --project_id="$PROJECT" show --format=none "$1" &>/dev/null
}

bq_table_exists() {
    bq --project_id="$PROJECT" show --format=none "${1}.${2}" &>/dev/null
}

ensure_dataset() {
    local dataset="$1"
    if bq_dataset_exists "$dataset"; then
        echo "  [=] BQ dataset exists:  $dataset"
        return
    fi
    echo "  [+] create BQ dataset:  $dataset"
    run bq --project_id="$PROJECT" --location="$BQ_LOCATION" mk --dataset "$PROJECT:$dataset"
}

# PubSub metadata schema — matches what a `--write-metadata` BQ subscription
# writes to each row.
BQ_TABLE_SCHEMA="subscription_name:STRING,message_id:STRING,publish_time:TIMESTAMP,data:STRING,attributes:STRING"

ensure_bq_table() {
    local dataset="$1" table="$2"
    if bq_table_exists "$dataset" "$table"; then
        echo "  [=] BQ table exists:    $dataset.$table"
        return
    fi
    echo "  [+] create BQ table:    $dataset.$table"
    run bq --project_id="$PROJECT" mk --table "$PROJECT:$dataset.$table" "$BQ_TABLE_SCHEMA"
}

# The PubSub service agent (auto-provisioned per project) needs
# bigquery.dataEditor on the destination table to write.
grant_pubsub_agent_bq_write() {
    local dataset="$1" table="$2"
    local project_number
    project_number=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null || echo "")
    if [[ -z "$project_number" ]]; then
        echo "  [!] can't resolve project number — skipping PubSub-agent BQ grant"
        return
    fi
    local agent="serviceAccount:service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
    echo "  [+] grant BQ dataEditor -> $agent on $dataset.$table"
    run bq --project_id="$PROJECT" add-iam-policy-binding \
        --member="$agent" --role="roles/bigquery.dataEditor" \
        "$PROJECT:$dataset.$table" >/dev/null
}

grant_bq_table_iam() {
    local dataset="$1" table="$2" role="$3" member="$4"
    echo "  [+] grant $role -> $member on $dataset.$table"
    run bq --project_id="$PROJECT" add-iam-policy-binding \
        --member="$member" --role="$role" \
        "$PROJECT:$dataset.$table" >/dev/null
}

ensure_bq_subscription() {
    local sub_name="$1" topic="$2" table_path="$3"
    if sub_exists "$sub_name"; then
        echo "  [=] BQ sub exists:      $sub_name"
        return
    fi
    echo "  [+] create BQ sub:      $sub_name -> $table_path"
    run gcloud pubsub subscriptions create "$sub_name" \
        --project="$PROJECT" \
        --topic="$topic" \
        --bigquery-table="$table_path" \
        --write-metadata \
        --quiet
}

delete_bq_subscription() {
    local sub_name="$1"
    if ! sub_exists "$sub_name"; then
        echo "  [=] BQ sub already absent:  $sub_name"
        return
    fi
    echo "  [-] delete BQ sub:  $sub_name"
    run gcloud pubsub subscriptions delete "$sub_name" --project="$PROJECT" --quiet
}

delete_bq_table() {
    local dataset="$1" table="$2"
    if ! bq_table_exists "$dataset" "$table"; then
        echo "  [=] BQ table already absent:  $dataset.$table"
        return
    fi
    echo "  [-] delete BQ table:  $dataset.$table"
    run bq --project_id="$PROJECT" rm -f -t "$PROJECT:$dataset.$table"
}

# --- per-partner actions -------------------------------------------------- #

apply_partner() {
    local code="$1"
    local topic="${TOPIC_PREFIX}-${code}-${ENV}"
    local dlq="${topic}-dlq"
    local pull_sub="${dlq}-pull"
    local dataset bq_table bq_sub
    dataset="$(dataset_name)"
    bq_table="$(bq_table_name "$code")"
    bq_sub="$(bq_sub_name "$code")"

    echo
    echo "== partner=$code env=$ENV project=$PROJECT =="

    ensure_topic "$topic"   "pay-events"     "$code"
    ensure_topic "$dlq"     "pay-events-dlq" "$code"
    ensure_dlq_pull_sub "$pull_sub" "$dlq"

    # BigQuery-backed DLQ — per-partner table so read access can be scoped
    # partner-by-partner. Dataset is shared per env.
    ensure_dataset "$dataset"
    ensure_bq_table "$dataset" "$bq_table"
    grant_pubsub_agent_bq_write "$dataset" "$bq_table"
    ensure_bq_subscription "$bq_sub" "$dlq" "$PROJECT.$dataset.$bq_table"

    # Publisher IAM — sbc-pay's SAs.
    for member in $(publishers_for_env "$ENV"); do
        grant_iam "$topic" "roles/pubsub.publisher" "$member"
    done

    # Subscriber IAM — partner's consumer SAs (subscriber + viewer on topic,
    # dataViewer on their own BQ table only — not the shared dataset).
    for member in $(subscribers_for "$code" "$ENV"); do
        grant_iam "$topic" "roles/pubsub.subscriber" "$member"
        grant_iam "$topic" "roles/pubsub.viewer"     "$member"
        grant_bq_table_iam "$dataset" "$bq_table" "roles/bigquery.dataViewer" "$member"
    done
}

destroy_partner() {
    local code="$1"
    local topic="${TOPIC_PREFIX}-${code}-${ENV}"
    local dlq="${topic}-dlq"
    local pull_sub="${dlq}-pull"
    local dataset bq_table bq_sub
    dataset="$(dataset_name)"
    bq_table="$(bq_table_name "$code")"
    bq_sub="$(bq_sub_name "$code")"

    echo
    echo "== DESTROY partner=$code env=$ENV project=$PROJECT =="

    # Reverse-dependency order. Dataset is NOT deleted — shared with other partners.
    delete_bq_subscription "$bq_sub"
    delete_bq_table "$dataset" "$bq_table"
    delete_sub   "$pull_sub"
    delete_topic "$dlq"
    delete_topic "$topic"
}

# --- dispatch ------------------------------------------------------------- #

# Which partners are in scope for this run?
if [[ -n "$PARTNER_FILTER" ]]; then
    # Verify the filter exists in PARTNERS.
    found=0
    for p in $PARTNERS; do
        [[ "$p" == "$PARTNER_FILTER" ]] && { found=1; break; }
    done
    [[ $found -eq 0 ]] && { echo "error: partner '$PARTNER_FILTER' not in PARTNERS" >&2; exit 1; }
    SCOPE="$PARTNER_FILTER"
else
    SCOPE="$PARTNERS"
fi

case "$CMD" in
    plan)
        echo "[plan — no changes will be made]"
        for p in $SCOPE; do apply_partner "$p"; done
        ;;
    apply)
        for p in $SCOPE; do apply_partner "$p"; done
        ;;
    destroy)
        [[ -z "$PARTNER_FILTER" ]] && { echo "error: destroy requires a partner code" >&2; exit 1; }
        [[ "$FLAG" != "--yes-really" ]] && { echo "error: destroy requires --yes-really" >&2; exit 1; }
        destroy_partner "$PARTNER_FILTER"
        ;;
esac

echo
echo "done."