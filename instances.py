import pathlib
import shutil

import jsonschema
import pymongo
import yaml

if not pathlib.Path("config/config.yml").exists():
    shutil.copyfile("resources/config.example.yml", "config/config.yml")

config_instance = yaml.load(open("config/config.yml"), Loader=yaml.FullLoader)
schema_instance = yaml.load(open("resources/configSchema.yml"), Loader=yaml.FullLoader)

jsonschema.validate(
    instance=config_instance,
    schema=schema_instance,
)

activeDatabaseClient = pymongo.MongoClient(config_instance["db"]["uri"])
activeDatabase = activeDatabaseClient["peppercord"]
