# FoodPod Telegram Bot

[![Container Build](https://github.com/Procsiab/foodpod/actions/workflows/build-container-publish-dockerhub.yaml/badge.svg)](https://github.com/Procsiab/foodpod/actions/workflows/build-container-publish-dockerhub.yaml)

![Docker Image Version (latest by date)](https://img.shields.io/docker/v/procsiab/foodpod?label=Latest%20tag%20pushed%20on%20Docker%20Hub)


#### Description

This repository contains the code for a docker-compose deployable Telegram bot, which uses the [Python Telegram API](https://github.com/python-telegram-bot/python-telegram-bot) and the [Redis](https://github.com/redis/redis) NoSQL DBMS; the bot will work as a "food cupboard assistant", helping the user to keep track of what food and how many they have, where is it stored and when will it will go bad.

Also, the container Images for `armv7`, `aarch64` and `amd64` platforms are automatically built from this repository, and available from [Docker Hub](https://hub.docker.com/r/procsiab/foodhub)

#### Security concerns

This application does not encrypt data at rest, nor in transit: it's a project I developed for personal needs, and thus security wasn't on my roadmap at this stage. Maybe I'll look into that if the feature set and user base grows a lot more.

## Building with Containerfile

The Containerfile is written to allow cross-architecture builds, using QEMU's user-static package: to build the image on x86 for another platform do the following:

- be sure to install `qemu-user-static` if you need to run the container on a different architecture from the local one;
- run the build process with `podman build -t myregistry/foodpod:latest -f Containerfile.amd64 .`.

If you want to use a target architecture different from ARM 64 bit, just select the Containerfile according to the target architecture

*NOTE*: If you are using Podman, just run the `build` command from above after replacing `docker` with `podman`.

## Installing secrets

The Python code assumes the existence of the folder `.secret` in the repository's root directory; inside it, two file should be placed, as in the following structure example:

```
.secrets
├── AUTH_USER.secret
└── TOKEN.secret
```

Those files should contain the following data:
- AUTH\_USER.secret: a Telegram user ID or a group ID to post the updates into;
- TOKEN.secret: a Telegram bot token, which can be obtained from BotFather.

*NOTE*: the code provided in this repository will not work without such files!

## Running with Podman Compose

You may first choose the correct image for the host CPU architecture; change the `image:` definition inside the compose file.

Open the repository's root directory in a terminal and run the following command:

```bash
podman-compose up -d
```

### Timezone

The bot uses the `TZ` environment variable to offset the internal job timers; the variable is defined inside the `container-compose.yaml` file, under the `env` section.

## Running on the host with venv

Open the repository's root directory in a terminal and run the following commands:
```bash
python3 -m venv app/.venv
source app/.venv/bin/activate
pip3 install -U pip
pip3 install -U -r app/requirements.txt
python3 app/main.py
```

The bot should start logging some info.

**NOTE**: At this point, you will still need to have a Redis database, reachable from the host you launched the Python program; remember to export the required environment variable, if the DB needs different parameters from the default ones.

## The DB backend

*WARNING*: The bot will need to connect to a Redis DB instance; the easiest way to provide this functionality for local testing, is to run a Redis container. After creating a `.redis` folder in the repo's root directory, run the following command from teh same location:

```bash
podman run --rm -d --name foodpod-db -v .redis:/data:Z -p 6379:6379 docker.io/library/redis:6.2.6-alpine --appendonly yes
```

You may choose a different location for the Redis container persistent volume, since it could also be running on another host. To do so, be sure to change the volume path inside the command above, or inside the docker-compose file.

To enable the connection to the DB, you need to export the following variables, providing the Redis instance's host, port, database name and password:

```bash
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_DB="0"
export REDIS_PASS=""
export TZ="Europe/Rome"
```
**NOTE**: The `TZ` variable is needed to set the timezone for the bot to schedule correctly the daily notification. By default, the notification time is hardcoded at 8 a.m.

These default values are used inside the compose file, and loaded if nothing is provided.
