from typing import Optional, Type
import urllib.parse
import random
from mautrix.types import RoomID, ImageInfo, BaseMessageEventContent, ContentURI
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
        helper.copy("fallback")
        helper.copy("retries")
        helper.copy("allow_nsfw")

class Post(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    async def fetch_from_reddit(self, subreddit) -> dict:
        headers = {
                'User-Agent': 'Maubot-RedditImg-Plugin'
                }
        # Get random image url
        with self.http.get(
            "https://api.reddit.com/{}".format(subreddit), headers=headers
        ) as response:
            status = response.status
            data = await response.json()

        if status != 200:
            #await evt.reply("i got a bad response, are you sure that's an actual subreddit?")
            raise ValueError("Response from reddit was not successful, possible subreddit mismatch.")
        else:
            return data


    async def fetch_and_upload_image(self, info: dict) -> ContentURI:
        resp = await self.http.get(info['permalink')
        if resp.status != 200:
            raise ValueError("Response from reddit was not successful, file could not be downloaded.")
            return None
        
        filedata = await resp.read()
        if Image is not None:
            try:
                image = Image.open(BytesIO(filedata))
                width, height = image.size
                info['width'] = width
                info['height'] = height
            except Exception as e:
                await evt.respond(f"Something went wrong while getting dimensions: {e.message}")

        uri = await self.client.upload_media(filedata, mime_type=info['mime'],
                                             filename=info['filename'])

        return uri

    async def pick_a_post(self, data) -> dict:
        # pick a random post until we find one that is not stickied
        tries = 0
        info = {}
        nsfw = False
        postable = False
        while tries <= self.config['retries'] and postable == False:
            tries += 1
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
            if response_type == "upload" and ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                #debug
                #await evt.reply(f"DEBUG: setting postable, with ext:{ext}")
                postable = True
                msgtype = 'image'
                info['msgtype'] = msgtype
                info['mime'] = [msgtype, ext].join('/')
                info['ext'] = ext
            elif response_type in ["message", "reply"]:
                #debug
                #await evt.reply(f"DEBUG: setting postable because respond/reply type chosen")
                info['permalink'] = permalink
                postable = True
            else:
                #debug
                #await evt.reply(f"DEBUG: skipping because response type is upload and cannot find ext:{ext} in list, \
                #        postable is {postable}")
                continue
            #debug
            #await evt.reply(f"DEBUG: info set to mime:{info['mime']} and ext:{info['ext']}")

        if tries >= self.config['retries']:
            raise IndexError("No postable options in list.")
        elif nsfw and (self.config['allow_nsfw'] != True):
            raise AttributeError("Non-allowed content found.")
        elif postable == False:
            raise SystemError("not sure how i got here, i haven't found a postable response yet")
        else:
            return info

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

        if len(subreddit) >= 1:
            if not subreddit.startswith('r/'):
                subreddit = 'r/' + subreddit

        response_type = self.config["response_type"]

        # get json response from reddit api
        data = await self.fetch_from_reddit(subreddit)

        # pass api response to picking logic
        try:
            post = await self.pick_a_post(data)
        except AttributeError as e:
            if self.config['fallback'] != 'none':
                response_type = self.config['fallback']
                # try again with our fallback option
                try:
                    post = await self.pick_a_post(data)
                except Exception as e:
                    await evt.respond(f"Something went wrong: {e}")
                    return None
        except Exception as e:
            await evt.respond(f"Something went wrong: {e}")
            return None

        # now we send a message with the post contents
        content = BaseMessageEventContent(
                    msgtype=f"m.{post['msgtype']}",
                    body=subreddit+post['ext'],
                    external_url=post['permalink']
                )

        if response_type == "message":
            await evt.respond(content=post['permalink'], allow_html=True)  # Respond to user
        elif response_type == "reply":
            await evt.reply(content=post['permalink'], allow_html=True)  # Reply to user
        elif response_type == "upload":
            try:
                # try to download and upload the image
                mxc_url = await self.fetch_and_upload_image(post)
                content["url"] = mxc_url
                await evt.respond(content=content)
            except Exception as e:
                await evt.respond(f"something went wrong: {e}")

        else:
            await evt.respond("something is wrong with my config, be sure to set a response_type")

