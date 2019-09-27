
# Generate a secret key

    docker-compose run --rm sentry config generate-secret-key

Then replace the value in .env file

# Init DB

    docker-compose run --rm sentry upgrade
# Start the app
Visit http://localhost:9000 to view sentry app
 

