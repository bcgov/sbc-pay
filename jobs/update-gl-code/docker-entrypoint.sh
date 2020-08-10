
function start_cron_jobs() {
  echo "Starting go-crond as a background task ..."
  CRON_CMD="go-crond -v --allow-unprivileged crontab"
  exec ${CRON_CMD}
}

export CRON_FOLDER=${CRON_FOLDER:-"crontab"}

echo "Starting cron ..."
start_cron_jobs

echo "Started cron ..."