# buildconfig
oc process -f openshift/templates/bc.yaml -o yaml | oc apply -f - -n 78c88a-tools
# cronjob
oc process -f openshift/templates/cronjob.yaml -o yaml | oc apply -f - -n 78c88a-dev
oc process -f openshift/templates/cronjob.yaml -p TAG=test -o yaml | oc apply -f - -n 78c88a-test
oc process -f openshift/templates/cronjob.yaml -p TAG=prod -o yaml | oc apply -f - -n 78c88a-prod

