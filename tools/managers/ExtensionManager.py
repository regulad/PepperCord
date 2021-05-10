import pathlib, os, copy

class ExtensionManager:
  def __init__(self, bot, extensionBaseDir: str = 'extensions/', loadedExtensions: list = []):
    self.bot = bot
    self.extensionBaseDir = extensionBaseDir
    self.loadedExtensions = loadedExtensions

  def extensionPathChanger(self, extensionPath: str):
    extensionName = extensionPath.strip('.py').replace('/','.')
    return extensionName

  def listExtensions(self):
    if len(self.loadedExtensions) > 0:
      return f'{len(self.loadedExtensions)} extension(s) loaded, including {self.loadedExtensions}'
    else:
      return 'No extensions are loaded.'
  
  def loadExtension(self, extensionPath: str = ''):
    def loadSingleExtension(extensionPath: str):
      extensionName = self.extensionPathChanger(extensionPath)
      fullExtensionName = self.extensionPathChanger(self.extensionBaseDir + extensionName)
      self.bot.load_extension(fullExtensionName)
      self.loadedExtensions.append(extensionName)
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathlib.Path(self.extensionBaseDir + extensionPath).is_dir():
      totalE = []
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        if file.endswith('.py'):
          try:
            loadSingleExtension(extensionPath + file)
          except Exception as e:
            totalE.append(file)
            print(f'{e}\nContinuing recursively')
      if len(totalE) > 0:
        return totalE
    else:
      loadSingleExtension(extensionPath)

  def unloadExtension(self, extensionPath: str = ''):
    def unloadSingleExtension(extensionPath: str):
      extensionName = self.extensionPathChanger(extensionPath)
      fullExtensionName = self.extensionPathChanger(self.extensionBaseDir + extensionName)
      self.bot.unload_extension(fullExtensionName)
      self.loadedExtensions.remove(extensionName)
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathValidator:
      totalE = []
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        if file.endswith('.py'):
          try:
            unloadSingleExtension(extensionPath + file)
          except Exception as e:
            totalE.append(file)
            print(f'{e}\nContinuing recursively')
      if len(totalE) > 0:
        return totalE
    else:
      unloadSingleExtension(extensionPath)

  def reloadExtension(self, extensionPath: str = ''):
    def reloadSingleExtension(extensionPath: str):
      extensionName = self.extensionPathChanger(extensionPath)
      fullExtensionName = self.extensionPathChanger(self.extensionBaseDir + extensionName)
      self.bot.reload_extension(fullExtensionName)
    pathValidator = pathlib.Path(self.extensionBaseDir + extensionPath).is_dir()
    if pathValidator:
      totalE = []
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        if file.endswith('.py'):
          try:
            reloadSingleExtension(extensionPath + file)
          except Exception as e:
            totalE.append(file)
            print(f'{e}\nContinuing recursively')
      if len(totalE) > 0:
        return totalE
    else:
      reloadSingleExtension(extensionPath)
