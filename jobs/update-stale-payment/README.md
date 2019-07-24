## Create a build so that it creates an image

Run the script in tools namespace

`
oc process -f update-stale-payment-records-build.json |oc create -f -
`


## Run the Job
Now switch to DEV namepace

`oc project l4ygcl-dev`

Run the cron in DEV namespace

`oc process -f cron-update-stale-payment.yaml | oc create -f -`

## Find the job running

`oc get jobs`

## Delete Jobs if needed

`oc delete cronjob/cron-update-stale-payment`


## How to check logs in Kibana

`kubernetes.pod_name like "cron-update-update-stale-payment" AND kubernetes.namespace_name:"l4ygcl-dev"`