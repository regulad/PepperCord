import pathlib, os, copy

class ExtensionManager:
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
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathlib.Path(self.extensionBaseDir + extensionPath).is_dir():
      totalE = []
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        if file.endswith('.py'):
          try:
            self.loadSingleExtension(extensionPath + file)
          except Exception as e:
            totalE.append(file)
            print(f'{e}\nContinuing recursively')
      if len(totalE) > 0:
        return totalE
    else:
      self.loadSingleExtension(extensionPath)

  def unloadExtension(self, extensionPath: str = ''):
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathValidator:
      totalE = []
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        if file.endswith('.py'):
          try:
            self.unloadSingleExtension(extensionPath + file)
          except Exception as e:
            totalE.append(file)
            print(f'{e}\nContinuing recursively')
      if len(totalE) > 0:
        return totalE
    else:
      self.unloadSingleExtension(extensionPath)

  def reloadExtension(self, extensionPath: str = ''):
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathValidator:
      totalE = []
      unloadExtension = copy.deepcopy(self.unloadExtension(extensionPath))
      loadExtension = copy.deepcopy(self.loadExtension(extensionPath))
      if len(unloadExtension) > 0:
        totalE.append(unloadExtension)
      if len(loadExtension) > 0:
        totalE.append(loadExtension)
      if len(totalE) > 0:
        return totalE
    else:
      self.unloadExtension(extensionPath)
      self.loadExtension(extensionPath)