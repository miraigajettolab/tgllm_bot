#!/bin/sh
docker stop tgllm_bot
docker rm tgllm_bot
docker image rm tgllm_bot
docker build -t tgllm_bot .
docker run --env-file .secret --name tgllm_bot -d -v $(pwd):/bot tgllm_bot
