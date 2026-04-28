function configure_nss_wrapper() {
  local uid gid
  uid="$(id -u)"
  gid="$(id -g)"

  # On OpenShift the container may run with a random UID that is not present in
  # the image's passwd database. Some binaries, including go-crond, resolve the
  # current user during startup and can fail if that lookup does not succeed.
  if getent passwd "${uid}" >/dev/null 2>&1; then
    return
  fi

  # nss_wrapper lets us provide a temporary passwd view for the current process
  # without modifying the real /etc/passwd inside the container.
  export NSS_WRAPPER_PASSWD
  export NSS_WRAPPER_GROUP=/etc/group
  NSS_WRAPPER_PASSWD="$(mktemp)"
  cp /etc/passwd "${NSS_WRAPPER_PASSWD}"
  echo "default:x:${uid}:${gid}:OpenShift User:${HOME}:/sbin/nologin" >> "${NSS_WRAPPER_PASSWD}"

  export LD_PRELOAD
  LD_PRELOAD="$(ldconfig -p | awk '/libnss_wrapper.so/ {print $NF; exit}')"

  if [ -z "${LD_PRELOAD}" ]; then
    echo "Unable to locate libnss_wrapper.so" >&2
    exit 1
  fi

  echo "Configured nss_wrapper for arbitrary UID ${uid}"
}

function start_cron_jobs() {
  echo "Starting go-crond as a background task ..."
  CRON_CMD="go-crond -v --allow-unprivileged --include=cron/"
  exec ${CRON_CMD}
}

configure_nss_wrapper
start_cron_jobs
