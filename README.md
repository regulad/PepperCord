# PepperCord

![PepperCord](https://repository-images.githubusercontent.com/364397477/80156d00-ad0d-11eb-85d6-dcdbcb0e136d)

[![wakatime](https://wakatime.com/badge/github/regulad/PepperCord.svg)](https://wakatime.com/badge/github/regulad/PepperCord)

# About

PepperCord was born out of necessity for a simpler alternative to other utility bots.

PepperCord gives you all the features you need to enrich your server.

* Utility
    * Admin Tools
    * Mod Tools
    * Privilege System
* Server personality
    * Custom Commands
    * Custom Messages
* Fun
    * Levels
    * Reaction Roles
    * Starboard
* Music
    * Playlist load/save
    * Text-To-Speech
    * Group music control
* APIs
    * Video Editing
    * Things to do
    * Cryptocurrencies
* Gaming
    * Minecraft
        * Player status
        * Server status

Have an issue? Think you can make PepperCord better? Join our [support server](https://www.regulad.xyz/discord).

Fully-documented source code is available for those able to make improvements.

# Using

## Public instance

[Invite](https://discord.com/api/oauth2/authorize?client_id=839264035756310589&permissions=3157650678&scope=bot%20applications.commands)
| [Server](https://www.regulad.xyz/discord)

## Self-host

If you want to host an instance of the bot yourself, feel free to do so!

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

# Extending

If you want to extend PepperCord as a contribution to the main project or to make it your own, there are a couple of
things you should know.

1. Extensions are split into different folders.
    1. Each subfolder is fairly self-explanatory.
        1. `core` is for extensions that are critical to the bot's functioning.
        2. `external` is for interactions with external APIs
        3. `features` is for self-contained features added to the bot.
        4. You can make a new folder if you do not fit into any of the categories.
