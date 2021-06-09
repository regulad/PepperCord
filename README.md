# PepperCord
![PepperCord](https://repository-images.githubusercontent.com/364397477/80156d00-ad0d-11eb-85d6-dcdbcb0e136d)

[![wakatime](https://wakatime.com/badge/github/regulad/PepperCord.svg)](https://wakatime.com/badge/github/regulad/PepperCord)

![Python Status](https://img.shields.io/github/workflow/status/regulad/PepperCord/Python?label=Python)
![Docker Status](https://img.shields.io/github/workflow/status/regulad/PepperCord/Docker?label=Docker)

![Issues](https://img.shields.io/github/issues/regulad/PepperCord)
![Forks](https://img.shields.io/github/issues-pr/regulad/PepperCord)

# About

PepperCord was born out of necessity for a simpler alternative to other utility bots.

Features include:
* Utility
  * Reaction Roles
  * Moderation
  * Starboard
  * Messages/Logging
* Fun
  * Levels
  * Image commands
  * ASCII Art
  * Minecraft

If you have any ideas on how to improve the bot, please make a fork and submit your pull request [here](https://github.com/regulad/PepperCord/pulls).

# Using

## Public instance

[Invite](https://discord.com/api/oauth2/authorize?client_id=839264035756310589&permissions=3157650678&scope=bot%20applications.commands) | [Server](https://www.regulad.xyz/discord)

## Self-host

If you want to host an instance of the bot yourself, feel free to do so! 

### Setup

The optimal way to setup PepperCord is in a controlled Docker container. Below is a `docker-compose.yml` that you can use to deploy to a Docker instance or swarm.

```yaml
version: '3'
services:
  peppercord:
    image: docker.pkg.github.com/regulad/peppercord/peppercord:latest
    volumes:
      - 'config:/app/config'
  mongo:
    image: mongo
volumes:
  config:
```

You'll still need to configure networking, but this will be different on every Docker environment.

If you want to run the bot outside a Docker container, you'll need to install the following dependencies from your favorite package manager:

```
git
ffmpeg
```

### Configuration

PepperCord uses MongoDB as a datastore, and environment variables for configuration and secrets. (For ease of use in docker.)

Environment variables:

#### Secrets

* `PEPPERCORD_URI`: MongoDB connection URI. Default is `mongodb://localhost:27107`.
* `PEPPERCORD_TOKEN`: Discord token.
* `PEPPERCORD_EVB`: EditVideoBot API Token. `https://pigeonburger.xyz/api/`. If you don't know what it is, don't add the var.

#### Config

* `PEPPERCORD_SHARDS`: Number of shards to use on Discord. Default is `0`.
* `PEPPERCORD_DB_NAME`: Name of the primary database. Default is `peppercord`.
* `PEPPERCORD_PREFIX`: Command prefix. Default is `?`.
* `PEPPERCORD_WEB`: Website used in some commands. Default is `https://www.regulad.xyz/PepperCord`.
