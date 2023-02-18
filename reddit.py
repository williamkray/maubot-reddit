from typing import Optional, Type
import urllib.parse
import random
from mautrix.types import RoomID, ImageInfo, TextMessageEventContent, ContentURI
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

class RedditPost(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    async def fetch_from_reddit(self, subreddit) -> dict:
        headers = {
                'User-Agent': 'Maubot-RedditImg-Plugin'
                }
        # Get random image url
        response = await self.http.get("https://api.reddit.com/{}".format(subreddit), headers=headers)
        status = response.status
        data = await response.json()

        if status != 200:
            #await evt.reply("i got a bad response, are you sure that's an actual subreddit?")
            raise ValueError("Response from reddit was not successful, possible subreddit mismatch.")
        else:
            return data


    async def fetch_and_upload_image(self, info: dict, subreddit_name: str) -> dict:
        self.log.debug(f"DEBUG: attempting download of {info['image_link']}")
        media_info = {}
        resp = await self.http.get(info['image_link'])
        if resp.status != 200:
            raise ValueError("Response from reddit was not successful, file could not be downloaded.")
            return None
        
        filedata = await resp.read()
        if Image is not None:
            self.log.debug(f"DEBUG: using Image library to fetch image dimensions")
            try:
                image = Image.open(BytesIO(filedata))
                width, height = image.size
                # hopefully media_info is created before we call this
                media_info['width'] = width
                media_info['height'] = height
                media_info['mimetype'] = info['mime']
                self.log.debug(f"DEBUG: image is {media_info['width']} by {media_info['height']}")
            except Exception as e:
                self.log.warning(f"Something went wrong while getting dimensions: {e}")

        self.log.debug(f"DEBUG: attempting upload of image to matrix")
        mxc_uri = await self.client.upload_media(filedata, mime_type=info['mime'],
                                             filename=subreddit_name + info['ext'])
        media_info['url'] = mxc_uri

        self.log.debug(f"DEBUG: uploaded image has mxc uri {media_info['url']}")
        return media_info

    async def pick_a_post(self, data, response_type: str) -> dict:
        # pick a random post until we find one that is not stickied
        tries = 0
        info = {}
        nsfw = False
        postable = False
        while tries <= self.config['retries'] and postable == False:
            tries += 1
            self.log.debug(f"DEBUG: number of tries = {tries}")
            picked_image = random.choice(data['data']['children'])
            permalink = "https://www.reddit.com" + picked_image['data']['permalink']
            image_link = picked_image['data']['url']
            ext = image_link.split(".")[-1].lower()
            if picked_image['data']['stickied'] == 'true' or picked_image['data']['pinned'] == 'true':
                #debug
                self.log.debug(f"DEBUG: skipping {permalink} because stickied")
                continue
            if picked_image['data']['over_18'] == True:
                #debug
                self.log.debug(f"DEBUG: setting nsfw True")
                nsfw = True
            ## if we can't find a media extension and we're supposed to upload, skip this one
            if response_type == "upload" and ext in ["jpg", "jpeg", "png", "gif", "webp"]:
                #debug
                self.log.debug(f"DEBUG: choosing {permalink} because extension is {ext}")
                self.log.debug(f"DEBUG: setting msgtype to image now...")
                msgtype = 'image'
                info['msgtype'] = msgtype
                self.log.debug(f"DEBUG: post info is {info}")
                info['mime'] = '/'.join([msgtype, ext])
                self.log.debug(f"DEBUG: post info is {info}")
                info['ext'] = ext
                self.log.debug(f"DEBUG: post info is {info}")
                info['permalink'] = permalink
                self.log.debug(f"DEBUG: post info is {info}")
                info['image_link'] = image_link
                self.log.debug(f"DEBUG: post info is {info}")
                self.log.debug(f"DEBUG: setting postable to True, this should stop the loop")
                postable = True
            elif response_type in ["message", "reply"]:
                #debug
                self.log.debug(f"DEBUG: choosing {permalink} because response_type is {response_type}")
                info['permalink'] = permalink
                info['msgtype'] = 'image'
                self.log.debug(f"DEBUG: setting postable to True, this should stop the loop")
                postable = True
            else:
                #debug
                self.log.debug(f"DEBUG: skipping {picked_image['data']['permalink']} because response type is upload and cannot find ext:{ext} in list, postable is {postable}")
                self.log.debug(f"DEBUG: postable remains False, the loop continues")
                continue

        if tries >= self.config['retries']:
            self.log.debug(f"DEBUG: number of tries has reached {tries}")
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
        response_type = self.config["response_type"]

        mtype = "picture"
        if response_type in ["message", "reply"]:
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

        # get json response from reddit api
        data = await self.fetch_from_reddit(subreddit)

        self.log.debug(f"Response type is: {response_type}")
        # pass api response to picking logic
        try:
            post = await self.pick_a_post(data, response_type)
            self.log.debug(f"Post has been picked: {post['permalink']}")
        except Exception as exception1:
            if self.config['fallback'] != 'none':
                response_type = self.config['fallback']
                # try again with our fallback option
                try:
                    post = await self.pick_a_post(data, response_type)
                    # overwrite msgtype in the dict
                    post['msgtype'] = 'text'
                    self.log.debug(f"Post has been picked: {post['permalink']}")
                except Exception as exception2:
                    await evt.respond(f"Something went wrong: {exception2}")
                    return None

            else:
                await evt.reply(f"Sorry, I couldn't find anything to post")
                return None

        # now we send a message with the post contents
        content = TextMessageEventContent(
                    msgtype=f"m.{post['msgtype']}",
                    body=subreddit,
                    external_url=post['permalink']
                )

        if response_type == "message":
            await evt.respond(content=post['permalink'], allow_html=True)  # Respond to user
        elif response_type == "reply":
            await evt.reply(content=post['permalink'], allow_html=True)  # Reply to user
        elif response_type == "upload":
            if not post['msgtype'] == "image" or not post:
                await evt.respond("i can't upload the response because it's not an image.")
                return None
            try:
                # try to download and upload the image
                media_info = await self.fetch_and_upload_image(post, subreddit)
                content["url"] = media_info['url']
                # overwrite the body to include file extension
                content['body'] = '.'.join([subreddit, post['ext']])
                content['info'] = {}
                content['info']['mimetype'] = media_info['mimetype']
                content['info']['h'] = media_info['height']
                content['info']['w'] = media_info['width']

                await evt.respond(content=content)
            except Exception as e:
                await evt.respond(f"something went wrong: {e}")

        else:
            await evt.respond("something is wrong with my config, be sure to set a response_type")

