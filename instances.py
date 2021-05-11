import pymongo

import utils.managers

activeConfigManager = utils.managers.ConfigManager()
activeDatabaseClient = pymongo.MongoClient(activeConfigManager.readKey("db.uri"))
activeDatabase = activeDatabaseClient["peppercord"]
