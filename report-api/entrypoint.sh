#!/bin/sh

echo "starting application ..."

gunicorn -b 0.0.0.0:5000 wsgi:application --timeout 360
