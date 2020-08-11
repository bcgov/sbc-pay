function start_cron_jobs() {
  echo "Starting go-crond as a background task ..."
  CRON_CMD="go-crond -v --allow-unprivileged crontab"
  exec ${CRON_CMD}
}

start_cron_jobs
