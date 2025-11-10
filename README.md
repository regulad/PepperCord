# PepperCord X

![PepperCord](https://repository-images.githubusercontent.com/364397477/80156d00-ad0d-11eb-85d6-dcdbcb0e136d)

[![wakatime](https://wakatime.com/badge/github/regulad/PepperCord.svg)](https://wakatime.com/badge/github/regulad/PepperCord)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/regulad/PepperCord/main.svg)](https://results.pre-commit.ci/latest/github/regulad/PepperCord/main)
[![Docker status](https://github.com/regulad/PepperCord/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/regulad/PepperCord/actions/workflows/docker-publish.yml)
[![CI status](https://github.com/regulad/PepperCord/actions/workflows/ci.yml/badge.svg)](https://github.com/regulad/PepperCord/actions/workflows/ci.yml)
![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/regulad/PepperCord?label=Latest%20Stable)

# About

PepperCord was born out of necessity for an open-source alternative to other utility bots.

Have an issue? Think you can make PepperCord better? Join our [support server](https://discord.gg/xwH2Bw7P5b).

Fully-documented source code is available for those able to make improvements.

# Using

## Public instance

[Primary](https://discord.com/oauth2/authorize?client_id=839264035756310589) | [Mirror](https://discord.com/oauth2/authorize?client_id=890394048228122715) | [Server](https://discord.gg/xwH2Bw7P5b)

### Setup

Docker is the best way to run an instance of the bot. See the file `docker-compose.yml` for an example compose file.

### Configuration

PepperCord uses MongoDB as a datastore, and environment variables for configuration and secrets. (For ease of use in docker.)

#### Environment variables:

See `.env.example`. Before running `docker compose up`, copy `.env.example` to `.env` and fill out the variables.
