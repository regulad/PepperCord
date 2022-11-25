"""
Utilities for working with self bots.
"""
from datetime import datetime, timedelta
from typing import Union, Any, Tuple, List, Optional, Mapping, Sequence, cast, AsyncIterator, Collection

from discord import Guild, GroupChannel, VerificationLevel, NotificationLevel, ContentFilter, Emoji, GuildSticker, \
    Locale, NSFWLevel, MFALevel, Thread, VoiceChannel, StageChannel, Member, VoiceProtocol, GuildSettings, TextChannel, \
    CategoryChannel, SystemChannelFlags, Role, StageInstance, ScheduledEvent, Asset, Status, \
    PermissionOverwrite, NotFound, MemberProfile, User, Template, Webhook, Invite, File, EntityType, PrivacyLevel, \
    Permissions, Colour, PartialEmoji, AuditLogAction, AuditLogEntry, Widget, WelcomeScreen, WelcomeChannel, ClientUser, \
    VoiceState, RoleTags
from discord.abc import Snowflake
from discord.activity import ActivityTypes
from discord.channel import VocalGuildChannel
from discord.utils import find, MISSING


class _WrappedMember(Member):
    def __init__(self, user: User | ClientUser, guild: "WrappedGroupChannel"):
        try:
            super().__init__(data={}, state=user._state, guild=guild)  # type: ignore
        except Exception:
            pass
        self._user: User = user

        self.guild: "WrappedGroupChannel" = guild
        self.joined_at: Optional[datetime] = None
        self.premium_since: Optional[datetime] = None
        self.nick: Optional[str] = None  # maybe with the friend nick?
        self.pending: bool = False
        self.timed_out_until: Optional[datetime] = None

    def __repr__(self) -> str:
        return (
            f'<_WrappedMember id={self._user.id} name={self._user.name!r} discriminator={self._user.discriminator!r}'
            f' bot={self._user.bot} nick={self.nick!r} guild={self.guild!r}>'
        )

    @property
    def status(self) -> Status:
        return None  # type: ignore
        # fixme

    @property
    def raw_status(self) -> str:
        return ""  # fixme

    @property
    def mobile_status(self) -> Status:
        return None  # type: ignore
        # fixme

    @property
    def desktop_status(self) -> Status:
        return None  # type: ignore
        # fixme

    @property
    def web_status(self) -> Status:
        return None  # type: ignore
        # fixme

    def is_on_mobile(self) -> bool:
        return False  # fixme

    @property
    def roles(self) -> List[Role]:
        return [self.guild.default_role]

    @property
    def guild_avatar(self) -> Optional[Asset]:
        return None

    @property
    def activities(self) -> Tuple[ActivityTypes, ...]:
        return tuple()

    @property
    def top_role(self) -> Role:
        return self.guild.default_role

    @property
    def voice(self) -> Optional[VoiceState]:
        return None

    async def edit(self, **fields: Any) -> None:
        raise RuntimeError

    async def request_to_speak(self) -> None:
        raise RuntimeError

    async def move_to(self, channel: Optional[VocalGuildChannel], *, reason: Optional[str] = None) -> None:
        raise RuntimeError

    async def timeout(
            self, until: Optional[Union[timedelta, datetime]], /, *, reason: Optional[str] = None
    ) -> None:
        raise RuntimeError

    async def add_roles(self, *roles: Snowflake, reason: Optional[str] = None, atomic: bool = True) -> None:
        raise RuntimeError

    async def remove_roles(self, *roles: Snowflake, reason: Optional[str] = None, atomic: bool = True) -> None:
        raise RuntimeError

    def get_role(self, role_id: int, /) -> Optional[Role]:
        return self.guild.get_role(role_id)

    def is_timed_out(self) -> bool:
        return False


class _DummyDefaultGroupChannelRole(Role):
    def __init__(self, guild: "WrappedGroupChannel"):
        try:
            super().__init__(data={}, state=None, guild=guild)  # type: ignore
        except Exception:
            pass

    def __repr__(self) -> str:
        return f'<_DummyDefaultGroupChannelRole id={self.id} name={self.name!r}>'

    @property
    def id(self) -> int:
        return self.guild.id

    @property
    def name(self) -> str:
        return "@everyone"

    @property
    def position(self) -> int:
        return 0

    @property
    def hoist(self) -> bool:
        return False

    @property
    def unicode_emoji(self) -> Optional[str]:
        return None

    @property
    def managed(self) -> bool:
        return False

    @property
    def tags(self) -> Optional[RoleTags]:
        return None

    @property
    def permissions(self) -> Permissions:
        return Permissions.general()

    @property
    def colour(self) -> Colour:
        return Colour.default()

    @property
    def icon(self) -> Optional[Asset]:
        return None

    @property
    def members(self) -> List[Member]:
        return self.guild.members

    async def fetch_members(self, *, subscribe: bool = False) -> List[Member]:
        return self.members

    async def add_members(self, *members: Snowflake, reason: Optional[str] = None) -> List[Member]:
        raise RuntimeError

    async def remove_roles(self, *members: Snowflake, reason: Optional[str] = None) -> None:
        raise RuntimeError

    async def edit(
            self,
            *,
            name: str = MISSING,
            permissions: Permissions = MISSING,
            colour: Union[Colour, int] = MISSING,
            color: Union[Colour, int] = MISSING,
            hoist: bool = MISSING,
            display_icon: Optional[Union[bytes, str]] = MISSING,
            icon: Optional[bytes] = MISSING,
            unicode_emoji: Optional[str] = MISSING,
            mentionable: bool = MISSING,
            position: int = MISSING,
            reason: Optional[str] = MISSING,
    ) -> Optional[Role]:
        raise RuntimeError

    async def delete(self, *, reason: Optional[str] = None) -> None:
        raise RuntimeError


class WrappedGroupChannel(Guild):
    """
    A fake guild based on the information of a group chat.
    """

    # Very hacky. I'm not sure if this is the best way to do this.

    def _from_data(self, guild: Any | None) -> None:
        pass

    def __init__(self, group_channel: GroupChannel) -> None:
        self._group_channel: GroupChannel = group_channel
        try:
            super().__init__(data=None, state=self._group_channel._state)  # type: ignore
        except Exception:
            pass

    # from data

    def __repr__(self) -> str:
        attrs = (
            ('id', self.id),
            ('name', self.name),
            ('chunked', self.chunked),
            ('member_count', self._member_count),
        )
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f'<WrappedGroupChannel {inner}>'

    @property
    def id(self) -> int:
        return self._group_channel.id

    @property
    def name(self) -> str:
        return self._group_channel.name

    @property
    def verification_level(self) -> VerificationLevel:
        return VerificationLevel.none

    @property
    def default_notifications(self) -> NotificationLevel:
        return NotificationLevel.all_messages

    @property
    def explicit_content_filter(self) -> ContentFilter:
        return ContentFilter.disabled

    @property
    def afk_timeout(self) -> int:
        return 0

    @property
    def unavailable(self) -> bool:
        return False

    @property
    def emojis(self) -> Tuple[Emoji, ...]:
        return tuple()

    @property
    def stickers(self) -> Tuple[GuildSticker, ...]:
        return tuple()

    @property
    def features(self) -> List[str]:
        return []

    @property
    def keywords(self) -> List[str]:
        return []

    @property
    def description(self) -> Optional[str]:
        return None

    @property
    def max_presences(self) -> Optional[int]:
        return None

    @property
    def max_members(self) -> Optional[int]:
        return 10

    @property
    def max_video_channel_users(self) -> Optional[int]:
        return None

    @property
    def premium_tier(self) -> int:
        return 0

    @property
    def premium_subscription_count(self) -> int:
        return 0

    @property
    def vanity_url_code(self) -> Optional[str]:
        return None

    @property
    def preferred_locale(self) -> Locale:
        return Locale.american_english

    @property
    def nsfw_level(self) -> NSFWLevel:
        return NSFWLevel.explicit  # maybe?

    @property
    def mfa_level(self) -> MFALevel:
        return MFALevel.disabled

    @property
    def approximate_presence_count(self) -> Optional[int]:
        return 0

    @property
    def approximate_member_count(self) -> Optional[int]:
        return 0

    @property
    def owner_id(self) -> Optional[int]:
        return self._group_channel.owner.id

    @property
    def owner_application_id(self) -> Optional[int]:
        return None

    @property
    def premium_progress_bar_enabled(self) -> bool:
        return False

    @property
    def application_command_count(self) -> int:
        return 0

    @property
    def primary_category_id(self) -> Optional[int]:
        return None

    # start real properties

    @property
    def channels(self) -> List[Any]:
        return [self._group_channel]  # type: ignore

    @property
    def threads(self) -> List[Thread]:
        return []

    @property
    def large(self) -> bool:
        return False

    @property
    def voice_channels(self) -> List[VoiceChannel]:
        return [self._group_channel]  # type: ignore

    @property
    def stage_channels(self) -> List[StageChannel]:
        return []

    @property
    def me(self) -> Member:
        return _WrappedMember(self._group_channel.me, self)

    def is_joined(self) -> bool:
        return True

    @property
    def joined_at(self) -> Optional[datetime]:
        return None

    @property
    def voice_client(self) -> Optional[VoiceProtocol]:
        return None  # fixme

    @property
    def notification_settings(self) -> GuildSettings:
        return None  # type: ignore
        # fixme

    @property
    def text_channels(self) -> List[TextChannel]:
        return [self._group_channel]  # type: ignore

    @property
    def categories(self) -> List[CategoryChannel]:
        return []

    # end real properties

    def by_category(self) -> List[Any]:
        return []

    def get_channel_or_thread(self, channel_id: int, /) -> Optional[Union[Thread, Any]]:
        return self._group_channel if channel_id == self._group_channel.id else None

    def get_channel(self, channel_id: int, /) -> Optional[Any]:
        return self._group_channel if channel_id == self._group_channel.id else None

    def get_thread(self, thread_id: int, /) -> Optional[Thread]:
        return None

    # resume real propeties??

    @property
    def system_channel(self) -> Optional[TextChannel]:
        return None

    @property
    def system_channel_flags(self) -> SystemChannelFlags:
        return None  # type: ignore
        # fixme

    @property
    def rules_channel(self) -> Optional[TextChannel]:
        return None

    @property
    def public_updates_channel(self) -> Optional[TextChannel]:
        return None

    @property
    def afk_channel(self) -> Optional[Any]:
        return None

    @property
    def widget_channel(self) -> Optional[Any]:
        return None

    @property
    def emoji_limit(self) -> int:
        return 0

    @property
    def sticker_limit(self) -> int:
        return 0

    @property
    def bitrate_limit(self) -> float:
        return 0.0

    @property
    def filesize_limit(self) -> int:
        return 8 * (10 ^ 6)

    @property
    def members(self) -> List[Member]:
        return [_WrappedMember(recipient, self) for recipient in self._group_channel.recipients]

    def get_member(self, user_id: int, /) -> Optional[Member]:
        return find(lambda m: m.id == user_id, self.members)

    @property
    def premium_subscribers(self) -> List[Member]:
        return []

    @property
    def roles(self) -> List[Role]:
        return [self.default_role]

    def get_role(self, role_id: int, /) -> Optional[Role]:
        return find(lambda r: r.id == role_id, self.roles)

    @property
    def default_role(self) -> Role:
        return _DummyDefaultGroupChannelRole(self)

    @property
    def premium_subscriber_role(self) -> Optional[Role]:
        return None

    @property
    def stage_instances(self) -> List[StageInstance]:
        return []

    def get_stage_instance(self, stage_instance_id: int, /) -> Optional[StageInstance]:
        return None

    @property
    def scheduled_events(self) -> List[ScheduledEvent]:
        return []

    def get_scheduled_event(self, scheduled_event_id: int, /) -> Optional[ScheduledEvent]:
        return None

    @property
    def owner(self) -> Optional[Member]:
        return self.get_member(self.owner_id)

    @property
    def icon(self) -> Optional[Asset]:
        return self._group_channel.icon

    @property
    def banner(self) -> Optional[Asset]:
        return None

    @property
    def splash(self) -> Optional[Asset]:
        return None

    @property
    def discovery_splash(self) -> Optional[Asset]:
        return None

    @property
    def member_count(self) -> Optional[int]:
        return len(self.members)

    @property
    def online_count(self) -> Optional[int]:
        return len(list(filter(lambda m: m.status is Status.online, self.members)))

    @property
    def presence_count(self) -> Optional[int]:
        return self.online_count

    @property
    def chunked(self) -> bool:
        return False

    @property
    def created_at(self) -> datetime:
        return self._group_channel.created_at

    # get_member_named

    async def create_text_channel(
            self,
            name: str,
            *,
            reason: Optional[str] = None,
            category: Optional[CategoryChannel] = None,
            position: int = MISSING,
            topic: str = MISSING,
            slowmode_delay: int = MISSING,
            nsfw: bool = MISSING,
            overwrites: Mapping[Union[Role, Member], PermissionOverwrite] = MISSING,
    ) -> TextChannel:
        raise RuntimeError

    async def create_voice_channel(
            self,
            name: str,
            *,
            reason: Optional[str] = None,
            category: Optional[CategoryChannel] = None,
            position: int = MISSING,
            bitrate: int = MISSING,
            user_limit: int = MISSING,
            rtc_region: Optional[str] = MISSING,
            video_quality_mode: Any = MISSING,
            overwrites: Mapping[Union[Role, Member], PermissionOverwrite] = MISSING,
    ) -> VoiceChannel:
        raise RuntimeError

    async def create_stage_channel(
            self,
            name: str,
            *,
            topic: str,
            position: int = MISSING,
            overwrites: Mapping[Union[Role, Member], PermissionOverwrite] = MISSING,
            category: Optional[CategoryChannel] = None,
            reason: Optional[str] = None,
    ) -> StageChannel:
        raise RuntimeError

    async def create_category(
            self,
            name: str,
            *,
            overwrites: Mapping[Union[Role, Member], PermissionOverwrite] = MISSING,
            reason: Optional[str] = None,
            position: int = MISSING,
    ) -> CategoryChannel:
        raise RuntimeError

    async def leave(self) -> None:
        await self._group_channel.leave()

    async def delete(self) -> None:
        await self._group_channel.close(silent=True)

    async def edit(
            self,
            *,
            reason: Optional[str] = MISSING,
            name: str = MISSING,
            description: Optional[str] = MISSING,
            icon: Optional[bytes] = MISSING,
            banner: Optional[bytes] = MISSING,
            splash: Optional[bytes] = MISSING,
            discovery_splash: Optional[bytes] = MISSING,
            community: bool = MISSING,
            afk_channel: Optional[VoiceChannel] = MISSING,
            owner: Snowflake = MISSING,
            afk_timeout: int = MISSING,
            default_notifications: NotificationLevel = MISSING,
            verification_level: VerificationLevel = MISSING,
            explicit_content_filter: ContentFilter = MISSING,
            vanity_code: str = MISSING,
            system_channel: Optional[TextChannel] = MISSING,
            system_channel_flags: SystemChannelFlags = MISSING,
            preferred_locale: Locale = MISSING,
            rules_channel: Optional[TextChannel] = MISSING,
            public_updates_channel: Optional[TextChannel] = MISSING,
            premium_progress_bar_enabled: bool = MISSING,
    ) -> Guild:
        new_gc: GroupChannel = await self._group_channel.edit(
            name=name,
            icon=icon,
            owner=owner,
        )
        return self.__class__(new_gc)

    async def fetch_channels(self) -> Sequence[Any]:
        return self.channels

    async def fetch_member(self, member_id: int, /) -> Member:
        maybe_member: Optional[Member] = self.get_member(member_id)
        if maybe_member is None:
            raise NotFound
        else:
            return maybe_member

    async def fetch_member_profile(
            self, member_id: int, /, *, with_mutuals: bool = True, fetch_note: bool = True
    ) -> MemberProfile:
        maybe_member: Optional[Member] = await self.fetch_member(member_id)
        assert maybe_member is not None
        user: User = cast(User, maybe_member)
        return await user.profile(with_mutuals=with_mutuals, fetch_note=fetch_note)  # type: ignore

    async def fetch_ban(self, user: Snowflake) -> Any:
        raise NotFound

    async def fetch_channel(self, channel_id: int, /) -> Union[Any, Thread]:
        maybe_channel: Optional[Any] = self.get_channel(channel_id)
        if maybe_channel is None:
            raise NotFound
        else:
            return maybe_channel

    async def bans(
            self,
            *,
            limit: Optional[int] = 1000,
            before: Snowflake = MISSING,
            after: Snowflake = MISSING,
    ) -> AsyncIterator[Any]:
        yield  # maybe?

    async def prune_members(
            self,
            *,
            days: int,
            compute_prune_count: bool = True,
            roles: Collection[Snowflake] = MISSING,
            reason: Optional[str] = None,
    ) -> Optional[int]:
        raise RuntimeError

    async def templates(self) -> List[Template]:
        return []

    async def webhooks(self) -> List[Webhook]:
        return []

    async def estimate_pruned_members(self, *, days: int, roles: Collection[Snowflake] = MISSING) -> Optional[int]:
        raise RuntimeError

    async def invites(self) -> List[Invite]:
        return []

    async def create_Any(self, *, type: Any, id: int) -> None:
        raise RuntimeError

    async def Anys(self, *, with_applications=True) -> List[Any]:
        raise []

    async def fetch_stickers(self) -> List[GuildSticker]:
        return []

    async def fetch_sticker(self, sticker_id: int, /) -> GuildSticker:
        raise NotFound

    async def create_sticker(
            self,
            *,
            name: str,
            description: str,
            emoji: str,
            file: File,
            reason: Optional[str] = None,
    ) -> GuildSticker:
        raise RuntimeError

    async def delete_sticker(self, sticker: Snowflake, /, *, reason: Optional[str] = None) -> None:
        raise RuntimeError

    async def fetch_scheduled_events(self, *, with_counts: bool = True) -> List[ScheduledEvent]:
        return []

    async def fetch_scheduled_event(self, scheduled_event_id: int, /, *, with_counts: bool = True) -> ScheduledEvent:
        raise NotFound

    async def create_scheduled_event(
            self,
            *,
            name: str,
            start_time: datetime,
            entity_type: EntityType,
            privacy_level: PrivacyLevel = MISSING,
            channel: Optional[Snowflake] = MISSING,
            location: str = MISSING,
            end_time: datetime = MISSING,
            description: str = MISSING,
            image: bytes = MISSING,
            reason: Optional[str] = None,
    ) -> ScheduledEvent:
        raise RuntimeError

    async def fetch_emojis(self) -> List[Emoji]:
        return []

    async def fetch_emoji(self, emoji_id: int, /) -> Emoji:
        raise NotFound

    async def create_custom_emoji(
            self,
            *,
            name: str,
            image: bytes,
            roles: Collection[Role] = MISSING,
            reason: Optional[str] = None,
    ) -> Emoji:
        raise RuntimeError

    async def delete_emoji(self, emoji: Snowflake, /, *, reason: Optional[str] = None) -> None:
        raise RuntimeError

    async def fetch_roles(self) -> List[Role]:
        return self.roles

    async def create_role(
            self,
            *,
            name: str = MISSING,
            permissions: Permissions = MISSING,
            color: Union[Colour, int] = MISSING,
            colour: Union[Colour, int] = MISSING,
            hoist: bool = MISSING,
            display_icon: Union[bytes, str] = MISSING,
            mentionable: bool = MISSING,
            icon: Optional[bytes] = MISSING,
            emoji: Optional[PartialEmoji] = MISSING,
            reason: Optional[str] = None,
    ) -> Role:
        raise RuntimeError

    async def edit_role_positions(self, positions: Mapping[Snowflake, int], *, reason: Optional[str] = None) -> List[
        Role]:
        raise RuntimeError

    async def kick(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        await self._group_channel.remove_recipients(user)

    async def ban(
            self,
            user: Snowflake,
            *,
            reason: Optional[str] = None,
            delete_message_days: int = 1,
    ) -> None:
        await self.kick(user, reason=reason)

    async def unban(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        raise RuntimeError

    @property
    def vanity_url(self) -> Optional[str]:
        return None

    async def vanity_invite(self) -> Optional[Invite]:
        return None

    async def audit_logs(
            self,
            *,
            limit: Optional[int] = 100,
            before: Any = MISSING,
            after: Any = MISSING,
            oldest_first: bool = MISSING,
            user: Snowflake = MISSING,
            action: AuditLogAction = MISSING,
    ) -> AsyncIterator[AuditLogEntry]:
        yield

    async def ack(self) -> None:
        return await self._group_channel.ack()

    async def widget(self) -> Widget:
        raise RuntimeError

    async def edit_widget(
            self,
            *,
            enabled: bool = MISSING,
            channel: Optional[Snowflake] = MISSING,
            reason: Optional[str] = None,
    ) -> None:
        raise RuntimeError

    async def welcome_screen(self) -> WelcomeScreen:
        raise RuntimeError

    async def edit_welcome_screen(
            self,
            *,
            description: str = MISSING,
            welcome_channels: Sequence[WelcomeChannel] = MISSING,
            enabled: bool = MISSING,
    ):
        raise RuntimeError

    async def chunk(self, channel: Snowflake = MISSING) -> List[Member]:
        return self.members

    async def fetch_members(
            self,
            channels: List[Snowflake] = MISSING,
            *,
            cache: bool = True,
            force_scraping: bool = False,
            delay: Union[int, float] = 1,
    ) -> List[Member]:
        return self.members

    async def query_members(
            self,
            query: Optional[str] = None,
            *,
            limit: int = 5,
            user_ids: Optional[List[int]] = None,
            presences: bool = True,
            cache: bool = True,
            subscribe: bool = False,
    ) -> List[Member]:
        return [member for member in self.members if member.name.startswith(query)]

    async def change_voice_state(
            self,
            *,
            channel: Optional[Snowflake],
            self_mute: bool = False,
            self_deaf: bool = False,
            self_video: bool = False,
            preferred_region: Optional[str] = MISSING,
    ) -> None:
        raise RuntimeError  # fixme

    async def request(self, **kwargs):  # Purposefully left undocumented...
        raise RuntimeError


__all__: tuple[str] = ("WrappedGroupChannel",)
