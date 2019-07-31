## Create a build so that it creates an image

Run the script in tools namespace

`
oc process -f update-stale-payment-records-build.json |oc create -f -
`

## Tag the image for TEST and PROD migration
Run the script in tools namespace

`oc tag update-stale-payment:latest update-stale-payment:test`

`oc tag update-stale-payment:latest update-stale-payment:prod`

## Run the Job
Now switch to DEV namepace

`oc project l4ygcl-dev`

Run the cron in DEV namespace

### DEV
`oc process -f cron-update-stale-payment.yaml -p ENV_TAG=latest -p TAG_NAME=dev | oc create -f -`

### TEST
`oc process -f cron-update-stale-payment.yaml -p ENV_TAG=test -p TAG_NAME=test | oc create -f -`

### PROD
`oc process -f cron-update-stale-payment.yaml -p ENV_TAG=prod -p TAG_NAME=prod | oc create -f -`

## Find the job running

`oc get jobs`

## Delete Jobs if needed

`oc delete cronjob/cron-update-stale-payment`


## How to check logs in Kibana

`kubernetes.pod_name like "cron-update-update-stale-payment" AND kubernetes.namespace_name:"l4ygcl-dev"`