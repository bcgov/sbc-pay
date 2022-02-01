#!/bin/sh

echo 'starting application'
gunicorn --bind 0.0.0.0:8080 --timeout 60 --workers 3  wsgi:application
