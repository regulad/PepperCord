import os, pathlib, yaml, json, copy, jsonschema

class extensionManager:
  def __init__(self, bot, extensionBaseDir: str = 'extensions/', loadedExtensions: list = []):
    self.bot = bot
    self.extensionBaseDir = extensionBaseDir
    self.loadedExtensions = loadedExtensions

    def extensionPathChanger(extensionPath: str):
      extensionName = extensionPath.strip('.py').replace('/','.')
      return extensionName

    def loadSingleExtension(extensionPath: str):
      extensionName = extensionPathChanger(extensionPath)
      fullExtensionName = extensionPathChanger(extensionBaseDir + extensionName)
      self.bot.load_extension(fullExtensionName)
      self.loadedExtensions.append(extensionName)

    def unloadSingleExtension(extensionPath: str):
      extensionName = extensionPathChanger(extensionPath)
      fullExtensionName = extensionPathChanger(extensionBaseDir + extensionName)
      self.bot.unload_extension(fullExtensionName)
      self.loadedExtensions.remove(extensionName)

    self.extensionPathChanger = extensionPathChanger
    self.loadSingleExtension = loadSingleExtension
    self.unloadSingleExtension = unloadSingleExtension

  def listExtensions(self):
    if len(self.loadedExtensions) > 0:
      return f'{len(self.loadedExtensions)} extension(s) loaded, including {self.loadedExtensions}'
    else:
      return 'No extensions are loaded.'
  
  def loadExtension(self, extensionPath: str = ''):
    if pathlib.Path(self.extensionBaseDir + extensionPath).is_dir():
      totalE = 0
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        try:
          self.loadSingleExtension(extensionPath + file)
        except Exception as e:
          totalE += 1
          print(f'{e}\nContinuing recursively')
      return f'Finished loading {extensionPath}. {totalE} extensions failed to load.'
    else:
      self.loadSingleExtension(extensionPath)
      return f'Finished loading {extensionPath}'

  def unloadExtension(self, extensionPath: str = ''):
    if pathlib.Path(self.extensionBaseDir + extensionPath).is_dir():
      totalE = 0
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        try:
          self.unloadSingleExtension(extensionPath + file)
        except Exception as e:
          totalE += 1
          print(f'{e}\nContinuing recursively')
      return f'Finished unloading extension directory. {totalE} extensions failed to unload.'
    else:
      self.unloadSingleExtension(extensionPath)
      return f'Finished unloading {extensionPath}'

  def reloadExtension(self, extensionPath: str = ''):
    self.unloadExtension(extensionPath)
    self.loadExtension(extensionPath)
    if pathlib.Path(extensionPath).is_dir():
      return f'Finished reloading {extensionPath}. Individual extensions may have failed to load, check the console.'
    else:
      return f'Finished reloading {extensionPath}'
  
class configManager:
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
