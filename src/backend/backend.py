# Copyright Mirage authors & contributors <https://github.com/mirukana/mirage>
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import certifi
import logging as log
import os
import re
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiohttp
import nio
import plyer
from appdirs import AppDirs

from . import __app_name__
from .errors import MatrixError, MatrixInvalidAccessToken
from .matrix_client import MatrixClient
from .media_cache import MediaCache
from .models import SyncId
from .models.filters import FieldStringFilter
from .models.items import Account, Event, Homeserver, PingStatus
from .models.model import Model
from .models.model_store import ModelStore
from .presence import Presence
from .sso_server import SSOServer
from .user_files import Accounts, History, NewTheme, Settings, Theme, UIState

# Logging configuration
log.getLogger().setLevel(log.INFO)
nio.logger_group.level = nio.log.logbook.ERROR
nio.log.logbook.StreamHandler(sys.stderr).push_application()


class Backend:
    """Manage matrix clients and provide other useful general methods.

    Attributes:
        saved_accounts: User config file for saved matrix account.

        settings: User config file for general UI and backend settings.

        ui_state: User data file for saving/restoring QML UI state.

        history: User data file for saving/restoring text typed into QML
            components.

        models: A mapping containing our data models that are
            synchronized between the Python backend and the QML UI.
            The models should only ever be modified from the backend.

            If a non-existent key is accessed, it is created and an
            associated `Model` and returned.

            The mapping keys are the `Model`'s synchronization ID,
            which a strings or tuple of strings.

            Currently used sync ID throughout the code are:

            - `"accounts"`: logged-in accounts;

            - `("<user_id>", "rooms")`: rooms our account `user_id` is part of;

            - `("<user_id>", "uploads")`: ongoing or failed file uploads for
              our account `user_id`;

            - `("<user_id>", "<room_id>", "members")`: members in the room
              `room_id` that our account `user_id` is part of;

            - `("<user_id>", "<room_id>", "events")`: state events and messages
              in the room `room_id` that our account `user_id` is part of.

            Special models:

            - `"all_rooms"`: See `models.special_models.AllRooms` docstring

            - `"matching_accounts"`
              See `models.special_models.MatchingAccounts` docstring

            - `("<user_id>", "<room_id>", "filtered_members")`:
              See `models.special_models.FilteredMembers` docstring

            - `("filtered_homeservers")`:
              See `models.special_models.FilteredHomeservers` docstring

        clients: A `{user_id: MatrixClient}` dict for the logged-in clients
            we managed. Every client is logged to one matrix account.

        media_cache: A matrix media cache for downloaded files.

        presences: A `{user_id: Presence}` dict for storing presence info about
            matrix users registered on Mirage.

        mxc_events: A dict storing media `Event` model items for any account
            that have the same mxc URI
    """

    def __init__(self) -> None:
        self.appdirs = AppDirs(appname=__app_name__, roaming=True)

        self.models = ModelStore()

        self.saved_accounts = Accounts(self)
        self.settings       = Settings(self)
        self.ui_state       = UIState(self)
        self.history        = History(self)
        self.theme          = Theme(self, self.settings.General.theme)
        # self.new_theme      = NewTheme(self, self.settings.General.new_theme)
        self.new_theme      = NewTheme(self, ".new.py")  # TODO

        self.clients: Dict[str, MatrixClient] = {}

        self._sso_server:      Optional[SSOServer]      = None
        self._sso_server_task: Optional[asyncio.Future] = None

        self.profile_cache: Dict[str, nio.ProfileGetResponse] = {}
        self.get_profile_locks: DefaultDict[str, asyncio.Lock] = \
            DefaultDict(asyncio.Lock)  # {user_id: lock}

        self.send_locks: DefaultDict[str, asyncio.Lock] = \
            DefaultDict(asyncio.Lock)  # {room_id: lock}

        cache_dir = Path(
            os.environ.get("MIRAGE_CACHE_DIR") or self.appdirs.user_cache_dir,
        )

        self.media_cache: MediaCache = MediaCache(self, cache_dir)

        self.presences: Dict[str, Presence] = {}

        self.concurrent_get_presence_limit = asyncio.BoundedSemaphore(8)

        self.mxc_events: DefaultDict[str, List[Event]] = DefaultDict(list)

        self.notification_avatar_cache: Dict[str, Path] = {}     # {mxc: path}


    def __repr__(self) -> str:
        return f"{type(self).__name__}(clients={self.clients!r})"


    # Clients management

    async def server_info(self, homeserver: str) -> Tuple[str, List[str]]:
        """Return server's real URL and supported login flows.

        Retrieving the real URL uses the `.well-known` API.
        Possible login methods include `m.login.password` or `m.login.sso`.
        """

        if not re.match(r"https?://", homeserver):
            homeserver = f"http://{homeserver}"

        client   = MatrixClient(self, homeserver=homeserver)
        http_re  = re.compile("^http://")
        is_local = urlparse(client.homeserver).netloc.split(":")[0] in (
            "localhost", "127.0.0.1", "::1",
        )

        try:
            client.homeserver = (await client.discovery_info()).homeserver_url
        except MatrixError:
            # This is either already the real URL, or an invalid URL.
            pass

        try:
            try:
                login_response = await client.login_info()
            except (asyncio.TimeoutError, MatrixError):
                # Maybe we still have a http URL and server only supports https
                client.homeserver = http_re.sub("https://", client.homeserver)
                login_response    = await client.login_info()

            # If we still have a http URL and server redirected to https
            if login_response.transport_response.real_url.scheme == "https":
                client.homeserver = http_re.sub("https://", client.homeserver)

            # If we still have a http URL and server accept both http and https
            if http_re.match(client.homeserver) and not is_local:
                original          = client.homeserver
                client.homeserver = http_re.sub("https://", client.homeserver)

                try:
                    await asyncio.wait_for(client.login_info(), timeout=6)
                except (asyncio.TimeoutError, MatrixError):
                    client.homeserver = original

            return (client.homeserver, login_response.flows)
        finally:
            await client.close()


    async def password_auth(
        self, user: str, password: str, homeserver: str,
    ) -> str:
        """Create & register a `MatrixClient`, login using the password
        and return the user ID we get.
        """

        client = MatrixClient(self, user=user, homeserver=homeserver)
        return await self._do_login(client, password=password)


    async def start_sso_auth(self, homeserver: str) -> str:
        """Start SSO server and return URL to open in the user's browser.

        See the `sso_server.SSOServer` class documentation.
        Once the returned URL has been opened in the user's browser
        (done from QML), `MatrixClient.continue_sso_auth()` should be called.
        """

        server                = SSOServer(homeserver)
        self._sso_server      = server
        self._sso_server_task = asyncio.ensure_future(server.wait_for_token())
        return server.url_to_open


    async def continue_sso_auth(self) -> str:
        """Wait for the started SSO server to get a token, then login.

        `MatrixClient.start_sso_auth()` must be called first.
        Creates and register a `MatrixClient` for logging in.
        Returns the user ID we get from logging in.
        """

        if not self._sso_server or not self._sso_server_task:
            raise RuntimeError("Must call Backend.start_sso_auth() first")

        await self._sso_server_task
        homeserver            = self._sso_server.for_homeserver
        token                 = self._sso_server_task.result()
        self._sso_server_task = None
        self._sso_server      = None

        client = MatrixClient(self, homeserver=homeserver)
        return await self._do_login(client, token=token)


    async def _do_login(self, client: MatrixClient, **login_kwargs) -> str:
        """Login on a client. If successful, register it and return user ID."""

        try:
            await client.login(**login_kwargs)
        except MatrixError:
            await client.close()
            raise

        if client.user_id in self.clients:
            await client.logout()
            return client.user_id

        self.clients[client.user_id] = client
        return client.user_id


    async def resume_client(
        self,
        user_id:    str,
        token:      str,
        device_id:  str,
        homeserver: str,
        state:      str = "online",
        status_msg: str = "",
    ) -> None:
        """Create and register a `MatrixClient` with known account details."""

        client = MatrixClient(
            self, user=user_id, homeserver=homeserver, device_id=device_id,
        )

        self.clients[user_id] = client

        await client.resume(user_id, token, device_id, state, status_msg)


    async def load_saved_accounts(self) -> List[str]:
        """Call `resume_client` for all saved accounts in user config."""

        async def resume(user_id: str, info: Dict[str, Any]) -> str:
            # Get or create account model
            self.models["accounts"].setdefault(
                user_id, Account(user_id, info.get("order", -1)),
            )

            await self.resume_client(
                user_id    = user_id,
                token      = info["token"],
                device_id  = info["device_id"],
                homeserver = info["homeserver"],
                state      = info.get("presence", "online"),
                status_msg = info.get("status_msg", ""),
            )

            return user_id

        return await asyncio.gather(*(
            resume(user_id, info)
            for user_id, info in self.saved_accounts.items()
            if info.get("enabled", True)
        ))


    async def logout_client(self, user_id: str) -> None:
        """Log a `MatrixClient` out and unregister it from our models."""

        client = self.clients.pop(user_id, None)

        if client:
            try:
                await client.logout()
            except MatrixInvalidAccessToken:
                pass

            self.models["accounts"].pop(user_id, None)
            self.models["matching_accounts"].pop(user_id, None)
            self.models[user_id, "uploads"].clear()

            for room_id in self.models[user_id, "rooms"]:
                self.models["all_rooms"].pop(room_id, None)
                self.models[user_id, room_id, "members"].clear()
                self.models[user_id, room_id, "events"].clear()
                self.models[user_id, room_id, "filtered_members"].clear()

            self.models[user_id, "rooms"].clear()

        await self.saved_accounts.forget(user_id)


    async def terminate_clients(self) -> None:
        """Call every `MatrixClient`'s `terminate()` method."""
        log.info("Setting clients offline...")
        tasks = [client.terminate() for client in self.clients.values()]
        await asyncio.gather(*tasks)


    async def get_client(self, user_id: str, _debug_info=None) -> MatrixClient:
        """Wait until a `MatrixClient` is registered in model and return it."""

        failures = 0

        while True:
            if user_id in self.clients:
                return self.clients[user_id]

            if failures and failures % 100 == 0:  # every 10s except first time
                log.warning(
                    "Client %r not found after %ds, _debug_info:\n%r",
                    user_id, failures / 10, _debug_info,
                )

            await asyncio.sleep(0.1)
            failures += 1


    # Multi-client Matrix functions

    async def update_room_read_marker(
        self, room_id: str, event_id: str,
    ) -> None:
        """Update room's read marker to an event for all accounts part of it.
        """

        async def update(client: MatrixClient) -> None:
            room    = self.models[client.user_id, "rooms"].get(room_id)
            account = self.models["accounts"][client.user_id]

            if room:
                room.set_fields(
                    unreads          = 0,
                    highlights       = 0,
                    local_unreads    = False,
                    local_highlights = False,
                )
                await client.update_account_unread_counts()

                # Only update server markers if the account is not invisible
                if account.presence != Presence.State.invisible:
                    await client.update_receipt_marker(room_id, event_id)

        await asyncio.gather(*[update(c) for c in self.clients.values()])


    async def verify_device(
        self, user_id: str, device_id: str, ed25519_key: str,
    ) -> None:
        """Mark a device as verified on all our accounts."""

        for client in self.clients.values():
            try:
                device = client.device_store[user_id][device_id]
            except KeyError:
                continue

            if device.ed25519 == ed25519_key:
                client.verify_device(device)


    async def blacklist_device(
        self, user_id: str, device_id: str, ed25519_key: str,
    ) -> None:
        """Mark a device as blacklisted on all our accounts."""

        for client in self.clients.values():
            try:
                # This won't include the client's current device, as expected
                device = client.device_store[user_id][device_id]
            except KeyError:
                continue

            if device.ed25519 == ed25519_key:
                client.blacklist_device(device)


    # General functions

    async def get_config_dir(self) -> str:
        return Path(self.appdirs.user_config_dir).as_uri()


    async def get_theme_dir(self) -> str:
        path = Path(self.appdirs.user_data_dir) / "themes"
        path.mkdir(parents=True, exist_ok=True)
        return path.as_uri()


    async def get_settings(self) -> Tuple[dict, UIState, History, str, dict]:
        """Return parsed user config files for QML."""
        return (
            self.settings.qml_data,
            self.ui_state.qml_data,
            self.history.qml_data,
            self.theme.qml_data,
            self.new_theme.qml_data,
        )


    async def set_string_filter(
        self, model_id: Union[SyncId, List[str]], value: str,
    ) -> None:
        """Set a FieldStringFilter (or derived class) model's filter property.

        This should only be called from QML.
        """

        if isinstance(model_id, list):  # QML can't pass tuples
            model_id = tuple(model_id)

        model = Model.proxies[model_id]

        if not isinstance(model, FieldStringFilter):
            raise TypeError("model_id must point to a FieldStringFilter")

        model.filter = value


    async def set_account_collapse(self, user_id: str, collapse: bool) -> None:
        """Call `set_account_collapse()` on the `all_rooms` model.

        This should only be called from QML.
        """
        self.models["all_rooms"].set_account_collapse(user_id, collapse)


    async def _ping_homeserver(
        self, session: aiohttp.ClientSession, homeserver_url: str,
    ) -> None:
        """Ping a homeserver present in our model and set its `ping` field."""

        item    = self.models["homeservers"][homeserver_url]
        times   = []
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

        for i in range(16):
            start = time.time()

            try:
                await session.get(
                    f"{homeserver_url}/_matrix/client/versions",
                    ssl=ssl_ctx,
                )
            except aiohttp.ClientError as err:
                log.warning("Failed pinging %s: %r", homeserver_url, err)
                item.status = PingStatus.Failed
                return

            times.append(round((time.time() - start) * 1000))

            if i == 7 or i == 15:
                item.set_fields(
                    ping=sum(times) // len(times), status=PingStatus.Done,
                )


    def _get_homeserver_stability(self, logs: List[Dict[str, Any]]) -> float:
        stability = 100.0

        for period in logs:
            started_at     = datetime.fromtimestamp(period["datetime"])
            time_since_now = datetime.now() - started_at

            if time_since_now.days > 30 or period["type"] != 1:  # 1 = downtime
                continue

            lasted_minutes = period["duration"] / 60

            stability -= (
                (lasted_minutes * stability / 1000) /
                max(1, time_since_now.days / 3)
            )

        return stability


    async def fetch_homeservers(self) -> None:
        """Retrieve a list of public homeservers and add them to our model."""

        api_list = "https://publiclist.anchel.nl/publiclist.json"
        tmout    = aiohttp.ClientTimeout(total=20)
        session  = aiohttp.ClientSession(raise_for_status=True, timeout=tmout)
        ssl_ctx  = ssl.create_default_context(cafile=certifi.where())
        response = await session.get(api_list, ssl=ssl_ctx)
        coros    = []

        for server in (await response.json()):
            homeserver_url = server["homeserver"]

            if homeserver_url.startswith("http://"):  # insecure server
                continue

            if not re.match(r"^https?://.+", homeserver_url):
                homeserver_url = f"https://{homeserver_url}"

            if server["country"] == "USA":
                server["country"] = "United States"

            self.models["homeservers"][homeserver_url] = Homeserver(
                id        = homeserver_url,
                name      = server["name"],
                site_url  = server["url"],
                country   = server["country"],
                stability =
                    self._get_homeserver_stability(server["monitor"]["logs"]),
            )

            coros.append(self._ping_homeserver(session, homeserver_url))

        await asyncio.gather(*coros)
        await session.close()


    async def desktop_notify(
        self, title: str, body: str = "", image: Union[Path, str] = "",
    ) -> None:
        # XXX: images on windows must be .ICO
        plyer.notification.notify(
            title    = title,
            message  = body,
            app_name = __app_name__,
            app_icon = str(image),
            timeout  = 10,
            toast    = False,
        )
