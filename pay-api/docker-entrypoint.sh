#!/bin/sh

echo 'starting application'
gunicorn --bind 0.0.0.0:8080 --timeout 60 --workers 2  wsgi:application
