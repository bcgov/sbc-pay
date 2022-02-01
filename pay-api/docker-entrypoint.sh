#!/bin/sh

echo 'starting application'
gunicorn --bind 0.0.0.0:8080 --config /opt/app/gunicorn_config.py wsgi:application
