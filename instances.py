import managers, pymongo

activeConfigManager = managers.ConfigManager()
activeDatabaseClient = pymongo.MongoClient(activeConfigManager.readKey('db.uri'))
activeDatabase = activeDatabaseClient['peppercord']
