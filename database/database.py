import motor.motor_asyncio
from typing import Any, Optional
from config import DB_URI, DB_NAME


class SidDataBase:
    def __init__(self, DB_URI, DB_NAME):
        self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.database = self.dbclient[DB_NAME]

        self.user_data = self.database['users']
        self.channel_data = self.database['channels']
        self.admins_data = self.database['admins']
        self.banned_user_data = self.database['banned_user']
        self.autho_user_data = self.database['autho_user']

        self.auto_delete_data = self.database['auto_delete']
        self.hide_caption_data = self.database['hide_caption']
        self.protect_content_data = self.database['protect_content']
        self.channel_button_data = self.database['channel_button']

        self.del_timer_data = self.database['del_timer']
        self.channel_button_link_data = self.database['channelButton_link']

        self.rqst_fsub_data = self.database['request_forcesub']
        self.rqst_fsub_Channel_data = self.database['request_forcesub_channel']
        self.store_reqLink_data = self.database['store_reqLink']

        # Variable storage collection
        self.variables_data = self.database['variables']


    # ==================== VARIABLE STORAGE ====================

    async def set_variable(self, key: str, value: Any) -> None:
        """
        Store or update a variable in the database.

        Args:
            key: Variable name/key
            value: Variable value (any type)
        """
        await self.variables_data.update_one(
            {'_id': key},
            {'$set': {'value': value}},
            upsert=True
        )

    async def get_variable(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a variable from the database.

        Args:
            key: Variable name/key
            default: Default value if key doesn't exist

        Returns:
            Variable value or default
        """
        data = await self.variables_data.find_one({'_id': key})
        if data:
            return data.get('value', default)
        return default

    async def delete_variable(self, key: str) -> bool:
        """
        Delete a variable from the database.

        Args:
            key: Variable name/key

        Returns:
            True if deleted, False if key didn't exist
        """
        result = await self.variables_data.delete_one({'_id': key})
        return result.deleted_count > 0

    async def variable_exists(self, key: str) -> bool:
        """
        Check if a variable exists in the database.

        Args:
            key: Variable name/key

        Returns:
            True if exists, False otherwise
        """
        found = await self.variables_data.find_one({'_id': key})
        return bool(found)

    async def get_all_variables(self) -> dict:
        """
        Get all variables as a dictionary.

        Returns:
            Dictionary of all variables
        """
        docs = await self.variables_data.find().to_list(length=None)
        return {doc['_id']: doc.get('value') for doc in docs}

    async def clear_all_variables(self) -> int:
        """
        Clear all variables from the database.

        Returns:
            Number of variables deleted
        """
        result = await self.variables_data.delete_many({})
        return result.deleted_count


    # ==================== CHANNEL BUTTON SETTINGS ====================

    async def set_channel_button_link(self, button_name: str, button_link: str):
        await self.channel_button_link_data.delete_many({})
        await self.channel_button_link_data.insert_one({
            'button_name': button_name,
            'button_link': button_link
        })

    async def get_channel_button_link(self):
        data = await self.channel_button_link_data.find_one({})
        if data:
            return data.get('button_name'), data.get('button_link')
        return 'Join Channel', 'https://t.me/btth480p'


    # ==================== DELETE TIMER SETTINGS ====================

    async def set_del_timer(self, value: int):
        await self.del_timer_data.update_one(
            {},
            {'$set': {'value': value}},
            upsert=True
        )

    async def get_del_timer(self):
        data = await self.del_timer_data.find_one({})
        return data.get('value', 600) if data else 600


    # ==================== BOOLEAN SETTINGS ====================

    async def _set_boolean_value(self, collection, value: bool):
        """Helper method to set boolean values"""
        await collection.update_one(
            {},
            {'$set': {'value': value}},
            upsert=True
        )

    async def _get_boolean_value(self, collection, default: bool = False):
        """Helper method to get boolean values"""
        data = await collection.find_one({})
        return data.get('value', default) if data else default

    async def set_auto_delete(self, value: bool):
        await self._set_boolean_value(self.auto_delete_data, value)

    async def set_hide_caption(self, value: bool):
        await self._set_boolean_value(self.hide_caption_data, value)

    async def set_protect_content(self, value: bool):
        await self._set_boolean_value(self.protect_content_data, value)

    async def set_channel_button(self, value: bool):
        await self._set_boolean_value(self.channel_button_data, value)

    async def set_request_forcesub(self, value: bool):
        await self._set_boolean_value(self.rqst_fsub_data, value)

    async def get_auto_delete(self):
        return await self._get_boolean_value(self.auto_delete_data)

    async def get_hide_caption(self):
        return await self._get_boolean_value(self.hide_caption_data)

    async def get_protect_content(self):
        return await self._get_boolean_value(self.protect_content_data)

    async def get_channel_button(self):
        return await self._get_boolean_value(self.channel_button_data)

    async def get_request_forcesub(self):
        return await self._get_boolean_value(self.rqst_fsub_data)


    # ==================== USER MANAGEMENT ====================

    async def present_user(self, user_id: int):
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})

    async def full_userbase(self):
        user_docs = await self.user_data.find().to_list(length=None)
        return [doc['_id'] for doc in user_docs]

    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})


    # ==================== CHANNEL MANAGEMENT ====================

    async def channel_exist(self, channel_id: int):
        found = await self.channel_data.find_one({'_id': channel_id})
        return bool(found)

    async def add_channel(self, channel_id: int):
        if not await self.channel_exist(channel_id):
            await self.channel_data.insert_one({'_id': channel_id})

    async def del_channel(self, channel_id: int):
        if await self.channel_exist(channel_id):
            await self.channel_data.delete_one({'_id': channel_id})

    async def get_all_channels(self):
        channel_docs = await self.channel_data.find().to_list(length=None)
        return [doc['_id'] for doc in channel_docs]


    # ==================== ADMIN MANAGEMENT ====================

    async def admin_exist(self, admin_id: int):
        found = await self.admins_data.find_one({'_id': admin_id})
        return bool(found)

    async def add_admin(self, admin_id: int):
        if not await self.admin_exist(admin_id):
            await self.admins_data.insert_one({'_id': admin_id})

    async def del_admin(self, admin_id: int):
        if await self.admin_exist(admin_id):
            await self.admins_data.delete_one({'_id': admin_id})

    async def get_all_admins(self):
        users_docs = await self.admins_data.find().to_list(length=None)
        return [doc['_id'] for doc in users_docs]


    # ==================== BAN USER MANAGEMENT ====================

    async def ban_user_exist(self, user_id: int):
        found = await self.banned_user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_ban_user(self, user_id: int):
        if not await self.ban_user_exist(user_id):
            await self.banned_user_data.insert_one({'_id': user_id})

    async def del_ban_user(self, user_id: int):
        if await self.ban_user_exist(user_id):
            await self.banned_user_data.delete_one({'_id': user_id})

    async def get_ban_users(self):
        users_docs = await self.banned_user_data.find().to_list(length=None)
        return [doc['_id'] for doc in users_docs]


    # ==================== REQUEST FORCE-SUB MANAGEMENT ====================

    async def add_reqChannel(self, channel_id: int):
        """Initialize a channel with an empty user_ids array"""
        await self.rqst_fsub_Channel_data.update_one(
            {'_id': channel_id},
            {'$setOnInsert': {'user_ids': []}},
            upsert=True
        )

    async def reqSent_user(self, channel_id: int, user_id: int):
        """Add user to the channel's user set"""
        await self.rqst_fsub_Channel_data.update_one(
            {'_id': channel_id},
            {'$addToSet': {'user_ids': user_id}},
            upsert=True
        )

    async def del_reqSent_user(self, channel_id: int, user_id: int):
        """Remove a user from the channel's user set"""
        await self.rqst_fsub_Channel_data.update_one(
            {'_id': channel_id},
            {'$pull': {'user_ids': user_id}}
        )

    async def clear_reqSent_user(self, channel_id: int):
        """Clear all users from a channel's set"""
        if await self.reqChannel_exist(channel_id):
            await self.rqst_fsub_Channel_data.update_one(
                {'_id': channel_id},
                {'$set': {'user_ids': []}}
            )

    async def reqSent_user_exist(self, channel_id: int, user_id: int):
        """Check if a user exists in the channel's user set"""
        found = await self.rqst_fsub_Channel_data.find_one(
            {'_id': channel_id, 'user_ids': user_id}
        )
        return bool(found)

    async def del_reqChannel(self, channel_id: int):
        """Remove a channel and its user set"""
        await self.rqst_fsub_Channel_data.delete_one({'_id': channel_id})

    async def reqChannel_exist(self, channel_id: int):
        """Check if a channel exists"""
        found = await self.rqst_fsub_Channel_data.find_one({'_id': channel_id})
        return bool(found)

    async def get_reqSent_user(self, channel_id: int):
        """Get all users from a channel's set"""
        data = await self.rqst_fsub_Channel_data.find_one({'_id': channel_id})
        return data.get('user_ids', []) if data else []

    async def get_reqChannel(self):
        """Get all available channel IDs"""
        channel_docs = await self.rqst_fsub_Channel_data.find().to_list(length=None)
        return [doc['_id'] for doc in channel_docs]


    # ==================== REQUEST LINK STORAGE ====================

    async def get_reqLink_channels(self):
        """Get all channel IDs with stored request links"""
        channel_docs = await self.store_reqLink_data.find().to_list(length=None)
        return [doc['_id'] for doc in channel_docs]

    async def get_stored_reqLink(self, channel_id: int):
        """Get the stored link for a specific channel"""
        data = await self.store_reqLink_data.find_one({'_id': channel_id})
        return data.get('link') if data else None

    async def store_reqLink(self, channel_id: int, link: str):
        """Store or update the request link for a channel"""
        await self.store_reqLink_data.update_one(
            {'_id': channel_id},
            {'$set': {'link': link}},
            upsert=True
        )

    async def del_stored_reqLink(self, channel_id: int):
        """Delete the stored request link for a channel"""
        await self.store_reqLink_data.delete_one({'_id': channel_id})


# Initialize database instance
kingdb = SidDataBase(DB_URI, DB_NAME)


# Helper functions for backward compatibility
async def get_variable(key: str, default: Any = None) -> Any:
    """Get a variable from the database"""
    return await kingdb.get_variable(key, default)


async def set_variable(key: str, value: Any) -> None:
    """Set a variable in the database"""
    await kingdb.set_variable(key, value)