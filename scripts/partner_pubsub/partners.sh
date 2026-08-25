# Adding a partner:
#   1. Append the partner's code to PARTNERS
#   2. Add a `<code>_<env>) echo "..."` case to subscribers_for()
#      (space-separated IAM members; empty is fine)

# Which GCP project hosts partner topics per env.
project_id_for_env() {
    case "$1" in
        dev)  echo "mvnjri-dev" ;;
        test) echo "TODO" ;;
        prod) echo "TODO" ;;
        *)    echo "" ;;
    esac
}

# sbc-pay's service accounts that publish to partner topics (cross-project grant).
# Space-separated list of fully-qualified IAM members.
publishers_for_env() {
    case "$1" in
        dev)
            echo "serviceAccount:sa-api@gtksf3-dev.iam.gserviceaccount.com \
                  serviceAccount:sa-job@gtksf3-dev.iam.gserviceaccount.com \
                  serviceAccount:sa-pubsub@gtksf3-dev.iam.gserviceaccount.com"
            ;;
        test)
            echo "serviceAccount:sa-api@gtksf3-test.iam.gserviceaccount.com \
                  serviceAccount:sa-job@gtksf3-test.iam.gserviceaccount.com \
                  serviceAccount:sa-pubsub@gtksf3-test.iam.gserviceaccount.com"
            ;;
        prod)
            echo "serviceAccount:sa-api@gtksf3-prod.iam.gserviceaccount.com \
                  serviceAccount:sa-job@gtksf3-prod.iam.gserviceaccount.com \
                  serviceAccount:sa-pubsub@gtksf3-prod.iam.gserviceaccount.com"
            ;;
        *) echo "" ;;
    esac
}

# Partner codes (lowercase). Drives topic naming: pay-events-<code>-<env>.
PARTNERS="sites"

# Partner subscriber IAM members. Space-separated per <code>_<env>.
# Empty = only sbc-pay publishes; nobody consumes yet.
subscribers_for() {
    case "${1}_${2}" in
        sites_dev)  echo "" ;;
        sites_test) echo "" ;;
        sites_prod) echo "" ;;
        *)          echo "" ;;
    esac
}
