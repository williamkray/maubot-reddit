from typing import Optional, Type
import urllib.parse
import random
from mautrix.types import RoomID, ImageInfo
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from io import BytesIO

import json
import datetime

try:
    from PIL import Image
except ImportError:
    Image = None

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("trigger")
        helper.copy("default_subreddit")
        helper.copy("response_type")
        helper.copy("retries")
        helper.copy("allow_nsfw")

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
        ext = info['ext']
        filename = f"{subreddit}.{ext}" if len(subreddit) > 0 else "reddit." + ext
        if Image is not None:
            try:
                image = Image.open(BytesIO(data))
                width, height = image.size
                info['width'] = width
                info['height'] = height
            except Exception as e:
                await evt.respond(f"Something went wrong while getting dimensions: {e.message}")

        uri = await self.client.upload_media(data, mime_type=mime, filename=filename)

        await self.client.send_image(room_id, url=uri, file_name=filename,
                info=ImageInfo(
                        mimetype=info['mime'],
                        width=info['width'],
                        height=info['height']
                    ))

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @command.new(name=lambda self: self.config["trigger"], help=f"Fetch a random post from a subreddit")
    @command.argument("subreddit", pass_raw=True, required=False)
    async def handler(self, evt: MessageEvent, subreddit: str) -> None:
        await evt.mark_read()

        mtype = "picture"
        if self.config['response_type'] in ["message", "reply"]:
            mtype = "link"

        if subreddit.lower() == "help":
            await evt.reply(f"fetch a random {mtype} from a subreddit.<br /> \
                        for example say <code>!{self.config['trigger']} photos</code> to post a random {mtype} from r/photos.", allow_html=True)
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
            status = response.status
            data = await response.json()

        if status != 200:
            await evt.reply("i got a bad response, are you sure that's an actual subreddit?")
            return None

        # pick a random post until we find one that is not stickied
        tries = 0
        info = {}
        nsfw = False
        postable = False
        while tries <= self.config['retries'] and postable == False:
            tries += 1
            #debug
            #await evt.reply(f"DEBUG: try number {tries} of {self.config['retries']}, postable:{postable}" )
            picked_image = random.choice(data['data']['children'])
            if picked_image['data']['stickied'] == 'true' or picked_image['data']['pinned'] == 'true':
                #debug
                #await evt.reply(f"DEBUG: skipping because stickied")
                continue
            if picked_image['data']['over_18'] == True:
                #debug
                #await evt.reply(f"DEBUG: setting nsfw True")
                nsfw = True
            image_link = picked_image['data']['url']
            permalink = "https://www.reddit.com" + picked_image['data']['permalink']
            ext = image_link.split(".")[-1].lower()
            ## if we can't find a media extension and we're supposed to upload, skip this one
            if response_type == "upload" and ext in ["jpg", "jpeg", "png", "gif", "mp4", "mov"]:
                #debug
                #await evt.reply(f"DEBUG: setting postable, with ext:{ext}")
                postable = True
                info['mime'] = 'image/' + ext
                info['ext'] = ext
            elif response_type in ["message", "reply"]:
                #debug
                #await evt.reply(f"DEBUG: setting postable because respond/reply type chosen")
                postable = True
            else:
                #debug
                #await evt.reply(f"DEBUG: skipping because response type is upload and cannot find ext:{ext} in list, \
                #        postable is {postable}")
                continue
            #debug
            #await evt.reply(f"DEBUG: info set to mime:{info['mime']} and ext:{info['ext']}")


        if tries >= self.config['retries']:
            message = [f"i tried to find something {self.config['retries']} times, but none of them met my criteria."]
            if response_type == "upload":
                message.append("it's probably because i'm set to upload images, but i wasn't able to find any.<br /> \
                        change my settings to allow links, and i'll be less particular.")
            await evt.respond("<br />".join(message), allow_html=True)
        elif nsfw and (self.config['allow_nsfw'] != True):
            await evt.respond("i found something, but it is marked NSFW.")
        elif postable == False:
            await evt.respond("not sure how i got here, i haven't found a postable response yet")
        else:
            if response_type == "message":
                await evt.respond(permalink, allow_html=True)  # Respond to user
            elif response_type == "reply":
                await evt.reply(permalink, allow_html=True)  # Reply to user
            elif response_type == "upload":
                #debug
                #await evt.reply(f"trying to upload {print(info)}")
                await self.post_image(evt.room_id, image_link, subreddit, info) # Upload the GIF to the room
            else:
                await evt.respond("something is wrong with my config, be sure to set a response_type")

