# PepperCord
"Whatever goes" bot. Has a ton of worthless garbage commands, and some cool things. Use it if you dare. Spaghetti monsters beyond.

## Config
PepperCord uses MongoDB as a database, and YAML for configuration.

| YAML Key | Reccomended/Default | Example | Use |
| --- | --- | --- | --- |
| `discord.api.token` | **Required** | `123456123456.abcdefabcdef` | Needed for authentication with Discord. |
| `discord.prefix` | `?` | `.` | Prefix for using commands. |
| `db.uri` | **Required** | `mongodb://localhost:27017` | Connection string to the MongoDB database. |
