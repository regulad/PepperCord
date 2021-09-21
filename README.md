# PepperCord

With the discontinuation of discord.py, I have decided to end this project for the time being. You can still build
something off of this, but I wouldn't advise it.

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
    * Custom Prefix
    * Custom Commands
    * Custom Messages
    * Proxy Messages
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

##### Top.gg

* `PEPPERCORD_TOPGG`: Top.gg Token. If you don't know what it is, don't add the var.

* `PEPPERCORD_TOPGG_WH`: Port to listen for the webhook. Defaults to `5000`.
* `PEPPERCORD_TOPGG_WH_ROUTE`: Route for the webhook. Defaults to `/topgg`.
* `PEPPERCORD_TOPGG_WH_SECRET`: Secret for the webhook. Required.

If any of the required `TOPGG_WH` params are missing, the bot will not start the webserver.

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
* `PEPPERCORD_FOLDERS`: Folders to load extensions from. Default is `core, extensions`.
