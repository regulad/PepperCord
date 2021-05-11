import typing

import discord
import pymongo

permissionLevel = typing.NewType("permissionLevel", int)


class PermissionManager:
    def __init__(self, guild: discord.Guild, collection: pymongo.collection.Collection):
        self.guild = guild
        self.collection = collection

        self.guildDict = collection.find_one({"_id": guild.id})

    # Takes in discord.Role and returns permission level.
    def checkRole(self, role: discord.Role):
        pass

    # Takes in discord.Member and returns permission level.
    def checkUser(self, user: discord.Member):
        pass

    # Writes a permission level to a role.
    def writeRole(self, role: discord.Role, level: permissionLevel):
        pass

    # Writes user permission level override.
    def writeUser(self, user: discord.User, level: permissionLevel):
        pass
