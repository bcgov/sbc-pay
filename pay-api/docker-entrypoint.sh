#!/bin/sh

echo 'starting application'
gunicorn --bind 0.0.0.0:8080 --config /opt/app-root/gunicorn_config.py  wsgi:application
