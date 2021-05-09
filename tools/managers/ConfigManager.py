import yaml, json, copy, jsonschema
  
class ConfigManager:
  def __init__(self, configFile: str = 'config/config.yml', configSchemaFile: str = 'resources/configSchema.json'):
    configSchemaData = json.load(open(configSchemaFile))
    configData = yaml.load(open(configFile), Loader=yaml.FullLoader)

    def validateSchema(configData: dict, configSchemaData):
      jsonschema.validate(instance=configData, schema=configSchemaData)

    def keyToObject(configObject: dict, yamlKey: str):
      objectPath = list(yamlKey.split('.'))
      for key in objectPath:
        configObject = configObject[key]
      return configObject

    validateSchema(configData, configSchemaData)

    self.keyToObject = keyToObject
    self.validateSchema = validateSchema
    
    self.configData = configData
    self.configSchemaData = configSchemaData

  def readKey(self, yamlKey: str = ''):
    configObject = copy.deepcopy(self.configData)
    if yamlKey == '':
      return configObject
    else: 
      objectToRead = self.keyToObject(configObject, yamlKey)
      return objectToRead
