import json
import pathlib
import shutil

import jsonschema
import motor.motor_asyncio
import yaml

if not pathlib.Path("config/config.yml").exists():
    shutil.copyfile("resources/config.example.yml", "config/config.yml")

config_instance = yaml.load(open("config/config.yml"), Loader=yaml.FullLoader)
schema_instance = json.load(open("resources/config.json"))

jsonschema.validate(
    instance=config_instance,
    schema=schema_instance,
)

active_database_client = motor.motor_asyncio.AsyncIOMotorClient(config_instance["db"]["uri"])
active_database = active_database_client[config_instance["db"]["name"]]
user_collection = active_database[config_instance["db"]["collections"]["user"]]
guild_collection = active_database[config_instance["db"]["collections"]["guild"]]
bot_collection = active_database[config_instance["db"]["collections"]["bot"]]
