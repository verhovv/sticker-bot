#!/bin/bash
sudo docker compose -f .docker/docker-compose.prod.yaml --env-file=.env "$@"
