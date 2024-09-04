#! /bin/sh
cd /opt/app-root
echo 'starting upgrade'
poetry run flask db upgrade