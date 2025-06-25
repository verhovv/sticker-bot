#!/bin/bash
sudo docker compose -f .docker/docker-compose.dev.yaml --env-file=.env "$@"
