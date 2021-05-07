from bot import bot
import os, pathlib

class extensionManager:
  def __init__(self, extensionBaseDir: str, loadedExtensions: list = []):
    self.extensionBaseDir = extensionBaseDir
    self.loadedExtensions = loadedExtensions

    def extensionPathChanger(extensionPath: str):
      extensionName = extensionPath.strip('.py').replace('/','.')
      return extensionName

    def loadSingleExtension(extensionPath: str):
      extensionName = extensionPathChanger(extensionPath)
      bot.load_extension(extensionPathChanger(self.extensionBaseDir) + extensionName)
      self.loadedExtensions.append(extensionName)

    def unloadSingleExtension(extensionPath: str):
      extensionName = extensionPathChanger(extensionPath)
      bot.unload_extension(extensionPathChanger(self.extensionBaseDir) + extensionName)
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
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        totalE = 0
        try:
          self.loadSingleExtension(extensionPath + file)
        except Exception as e:
          totalE = totalE + 1
          print(f'{e}\nContinuing recursively')
      return f'Finished loading {extensionPath}. {totalE} extensions failed to load.'
    else:
      self.loadSingleExtension(extensionPath)
      return f'Finished loading {extensionPath}'

  def unloadExtension(self, extensionPath: str = ''):
    if pathlib.Path(self.extensionBaseDir + extensionPath).is_dir():
      for file in os.listdir(self.extensionBaseDir + extensionPath):
        totalE = 0
        try:
          self.unloadSingleExtension(extensionPath + file)
        except Exception as e:
          totalE = totalE + 1
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
