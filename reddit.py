from typing import Optional, Type
import urllib.parse
import random
from mautrix.types import RoomID, ImageInfo
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command

import json
import datetime

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("default_subreddit")
        helper.copy("response_type")

class Post(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    async def post_image(self, room_id: RoomID, link: str, subreddit: str, info: dict) -> None:
        resp = await self.http.get(link)
        if resp.status != 200:
            self.log.warning(f"Unexpected status fetching image {url}: {resp.status}")
            return None
        
        data = await resp.read()
        mime = info['mime'] 
        filename = f"{subreddit}.{mime.split('/')[-1]}" if len(subreddit) > 0 else "reddit." + mime.split('/')[-1]
        uri = await self.client.upload_media(data, mime_type=mime, filename=filename)

        await self.client.send_image(room_id, url=uri, file_name=filename,
                info=ImageInfo(
                        mimetype=info['mime']
                        #width=info['width'],
                        #height=info['height']
                    ))

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @command.new(name="reddit", help="Post a random image from a subreddit")
    @command.argument("subreddit", pass_raw=True, required=False)
    async def handler(self, evt: MessageEvent, subreddit: str) -> None:
        await evt.mark_read()

        if subreddit.lower() == "help":
            await evt.reply("fetch a random image or post from a subreddit.<br /> \
                        for example say <code>!reddit photos</code> to post a random photo from r/photos.", allow_html=True)
            return None

        if not subreddit:
            # If user doesn't supply a subreddit, use the default
            subreddit = self.config["default_subreddit"]

        response_type = self.config["response_type"]
        headers = {
                'User-Agent': 'Maubot-RedditImg-Plugin'
                }
        # Get random image url
        async with self.http.get(
            "https://api.reddit.com/r/{}".format(subreddit), headers=headers
        ) as response:
            data = await response.json()

        # pick a random post until we find one that is not stickied
        stickied = True
        tries = 0
        while stickied == True and tries <= 5:
            tries += 1
            try:
                info = {}
                picked_image = random.choice(data['data']['children'])
                if picked_image['data']['stickied'] == 'true':
                    await evt.respond("found one but it is stickied")
                    continue
                else:
                    stickied = False
                image_link = picked_image['data']['url']
                permalink = "https://reddit.com" + picked_image['data']['permalink']
                mime = image_link.split(".")[-1].lower()
                ## if we can't find a media extension just default to permalink
                if mime not in ["jpg", "jpeg", "png", "gif", "mp4", "mov"]:
                    response_type = "message"
                # pick some arbitrary dimensions so media manager doesn't freak out
                #info['width'] = 480
                #info['height'] = 270
                info['mime'] = 'image/' + mime
            except Exception as e:
                await evt.respond(f"Something went wrong: {e.message}")
                return None

        if tries >= 5:
            await evt.respond("i tried several times, but failed. sorry.")
        else:
            if response_type == "message":
                await evt.respond(permalink, allow_html=True)  # Respond to user
            elif response_type == "reply":
                await evt.reply(permalink, allow_html=True)  # Reply to user
            elif response_type == "upload":
                await self.post_image(evt.room_id, image_link, subreddit, info) # Upload the GIF to the room
            else:
                await evt.respond("something is wrong with my config, be sure to set a response_type")
