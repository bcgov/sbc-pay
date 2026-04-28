function ensure_runtime_user() {
  local uid gid runtime_user runtime_shell
  uid="$(id -u)"
  gid="$(id -g)"
  runtime_user="app"
  runtime_shell="/bin/sh"

  # On OpenShift the container may run with a random UID that is not present in
  # the image's passwd database. Some binaries, including go-crond, resolve the
  # current user during startup and can fail if that lookup does not succeed.
  if getent passwd "${uid}" >/dev/null 2>&1; then
    return
  fi

  # Add the smallest possible passwd entry for the current runtime identity.
  # Use the actual uid/gid, avoid root-group membership, and provide a minimal
  # shell path so user lookup succeeds before go-crond starts.
  if [ ! -w /etc/passwd ]; then
    echo "Unable to add runtime user entry: /etc/passwd is not writable" >&2
    exit 1
  fi

  echo "${runtime_user}:x:${uid}:${gid}:${runtime_user}:${HOME}:${runtime_shell}" >> /etc/passwd
  echo "Added runtime passwd entry for UID ${uid}"
}

function start_cron_jobs() {
  echo "Starting go-crond as a background task ..."
  CRON_CMD="go-crond -v --allow-unprivileged --include=cron/"
  exec ${CRON_CMD}
}

ensure_runtime_user
start_cron_jobs
