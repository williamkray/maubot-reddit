this is a simple plugin for maubot that fetches a random link or image from a subreddit, and posts it to matrix for you.

install it like any other maubot plugin, and swing on over to the config file. there you can set a few options like:

  - default subreddit to use if no subreddit is supplied in the argument
  - the trigger word to use (default is reddit)
  - whether to allow NSFW content
  - how to submit the message (reply, respond, or just upload an image if available)
  - what to fall back to if you are using "upload" as your default behavior

to use it, run your bot and use your trigger. so using default configs, it would look like this:

`!reddit funny`

to fetch a random post from the r/funny subreddit.

use a different trigger and default subreddit config for multiple instances to have shortcuts to subreddits you frequent
without getting duplicate responses in the same room!

if you choose to upload images directly with the bot, it will fail to recognize media links that don't end in a common
media file extension (png, gif, jpg, etc). this means that on subreddits with primarily text-based posts, or posts that
are links out to third-party sites like gfycat which don't include file extensions, the bot will try and most likely
fail to find something to upload. use the message or reply response type for these kinds of subreddits, or set your
fallback settings to do so automagically.

