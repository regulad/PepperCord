import json
import pathlib
import shutil

import jsonschema
import yaml


# Lets you get information from a validated config file using yaml-style keys.
class ConfigManager:
    def __init__(
        self,
        configFile: str = "config/config.yml",
        configSchemaFile: str = "resources/configSchema.json",
    ):
        if not pathlib.Path(configFile).exists():
            shutil.copyfile("resources/config.example.yml", configFile)

        jsonschema.validate(
            instance=yaml.load(open(configFile), Loader=yaml.FullLoader),
            schema=json.load(open(configSchemaFile)),
        )

        self.configFile = configFile
        self.configSchemaFile = configSchemaFile

    def keyToObject(self, configObject: dict, yamlKey: str):
        objectPath = list(yamlKey.split("."))
        for key in objectPath:
            configObject = configObject[key]
        return configObject

    def readKey(self, yamlKey: str):
        configObject = yaml.load(open(self.configFile), Loader=yaml.FullLoader)
        objectToRead = self.keyToObject(configObject, yamlKey)
        return objectToRead
