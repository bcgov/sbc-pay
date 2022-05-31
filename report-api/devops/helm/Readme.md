helm repo list

helm repo update

helm search repo

## Report API
helm install report-api bcregistry/bcregistry-api -f values.dev.yaml --namespace d893f6-dev

helm install report-api bcregistry/bcregistry-api -f values.test.yaml --namespace d893f6-test

helm install report-api bcregistry/bcregistry-api -f values.prod.yaml --namespace d893f6-prod

helm upgrade report-api bcregistry/bcregistry-api -f values.dev.yaml --namespace d893f6-dev

helm upgrade report-api bcregistry/bcregistry-api -f values.test.yaml --namespace d893f6-test

helm upgrade report-api bcregistry/bcregistry-api -f values.prod.yaml --namespace d893f6-prod

## PPR Report API
helm install ppr-report-api bcregistry/bcregistry-api -f values.dev.yaml --namespace 1dfe78-dev --set image.namespace=1dfe78-tools

helm install ppr-report-api bcregistry/bcregistry-api -f values.test.yaml --namespace 1dfe78-test --set image.namespace=1dfe78-tools

helm install ppr-report-api bcregistry/bcregistry-api -f values.prod.yaml --namespace 1dfe78-prod --set image.namespace=1dfe78-tools

helm upgrade ppr-report-api bcregistry/bcregistry-api -f values.dev.yaml --namespace 1dfe78-dev --set image.namespace=1dfe78-tools

helm upgrade ppr-report-api bcregistry/bcregistry-api -f values.test.yaml --namespace 1dfe78-test --set image.namespace=1dfe78-tools

helm upgrade ppr-report-api bcregistry/bcregistry-api -f values.prod.yaml --namespace 1dfe78-prod --set image.namespace=1dfe78-tools