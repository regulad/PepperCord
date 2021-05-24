# PepperCord
![PepperCord](https://repository-images.githubusercontent.com/364397477/80156d00-ad0d-11eb-85d6-dcdbcb0e136d)

![Python Status](https://img.shields.io/github/workflow/status/regulad/PepperCord/Python?label=Python)
![Docker Status](https://img.shields.io/github/workflow/status/regulad/PepperCord/Docker?label=Docker)

![Issues](https://img.shields.io/github/issues/regulad/PepperCord)
![Forks](https://img.shields.io/github/issues-pr/regulad/PepperCord)

# About

PepperCord was born out of necessity for a simpler alternative to other utility bots.

Always evolving, new updates are pushed frequently.

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

If you have any ideas on how to improve the bot, please make a fork and submit your pull request [here](https://github.com/regulad/PepperCord/pulls].

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

Under Docker, you should place your config file in `config/config.yml` rather than `config.yml`.

### Configuration

PepperCord uses MongoDB as a data store and YAML for configuration, so you'll need to but your bot's info into `config.yml`. 

Here is an example:

```yaml
db:
  uri: mongodb://localhost # Connection URI to your MongoDB server
  name: peppercord # Name of the DB on your PepperCord server
discord:
  api:
    token: UghqQolQCODamh1fS7B7DKkE.tJEE4u.TnJJbmoBbyscPFViH4OSOCX2Fyf # Token for your bot. Selfbots don't work.
  commands:
    prefix: '~' # Prefix for all commands: can be changed per-server by the user
    cooldown:
      rate: 6 # Amount of commands that can be executed...
      per: 10 # ...per this amount of time in seconds
web:
  base: https://www.regulad.xyz/PepperCord # Base domain for donate button and more
  github: https://github.com/regulad/PepperCord # GitHub Repo
```

No more configuration must be performed on behalf of the hoster.
