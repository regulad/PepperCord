# PepperCord

![PepperCord](https://repository-images.githubusercontent.com/364397477/80156d00-ad0d-11eb-85d6-dcdbcb0e136d)

[![wakatime](https://wakatime.com/badge/github/regulad/PepperCord.svg)](https://wakatime.com/badge/github/regulad/PepperCord)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/regulad/PepperCord/main.svg)](https://results.pre-commit.ci/latest/github/regulad/PepperCord/main)
[![Docker status](https://github.com/regulad/PepperCord/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/regulad/PepperCord/actions/workflows/docker-publish.yml)
[![CI status](https://github.com/regulad/PepperCord/actions/workflows/ci.yml/badge.svg)](https://github.com/regulad/PepperCord/actions/workflows/ci.yml)
![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/regulad/PepperCord?label=Latest%20Stable)

# About

PepperCord was born out of necessity for an open-source alternative to other utility bots.

Have an issue? Think you can make PepperCord better? Join our [support server](https://www.regulad.xyz/discord).

Fully-documented source code is available for those able to make improvements.

# Using

## Public instance

[Primary](https://redirector.regulad.xyz/peppercord) | [Mirror](https://redirector.regulad.xyz/mirror) | [Server](https://www.regulad.xyz/discord)

### Setup

Docker is the best way to run an instance of the bot. See the file `docker-compose.yml` for an example compose file.

If you want to run the bot outside a Docker container, you'll need to install the following dependencies from your
favorite package manager:

```
git
ffmpeg
```

### Configuration

PepperCord uses MongoDB as a datastore, and environment variables for configuration and secrets. (For ease of use in
docker.)

#### Config files:

PepperCord uses a folder named `config/` for everything that isn't stored in configuration files.

* `SERVICE_ACCOUNT.JSON`: Google Cloud Service Account authentication information. Used for Google Cloud Text-To-Speech.
  Not required. If the file is missing, the TextToSpeech extension will not fully load.

#### Environment variables:

##### Secrets

* `PEPPERCORD_URI`: MongoDB connection URI. Default is `mongodb://mongo:27107`.
* `PEPPERCORD_TOKEN`: Discord token.
* `PEPPERCORD_EVB`: EditVideoBot API Token. `https://pigeonburger.xyz/api/`. If you don't know what it is, don't add the
  var.

##### Config

* `PEPPERCORD_SHARDS`: Number of shards to use on Discord. Default is `0`.
* `PEPPERCORD_DB_NAME`: Name of the primary database. Default is `peppercord`.
* `PEPPERCORD_PREFIX`: Command prefix. Default is `?`.
* `PEPPERCORD_WEB`: Website used in some commands. Default is `https://www.regulad.xyz/PepperCord`.
* `PEPPERCORD_WEBHOOK`: Optional. A link to a Discord webhook for logging.
* `PEPPERCORD_DEBUG`: Optional. Enables debug information in the log.
* `PEPPERCORD_TESTGUILDS`: Optional. A comma seperated list of Discord guild ids. The bot will only be enabled in these
  servers. If these are present, global slash commands will not be uploaded.
* `PEPPERCORD_SLASH_COMMANDS`: Optional. If slash commands should be disabled.
* `PEPPERCORD_HOME_SERVER`: Optional. The Discord guild id of the bot's home server. Used for some commands, mainly making emojis.

#### Intents

* `PEPPERCORD_MESSAGE_CONTENT`: Optional.
* `PEPPERCORD_PRESENCES`: Optional.
* `PEPPERCORD_MEMBERS`: Optional.
