this is a simple plugin for maubot that fetches a random link or image from a subreddit, and posts it to matrix for you.

install it like any other maubot plugin, and swing on over to the config file. there you can set a few options like:

  - default subreddit to use if no subreddit is supplied in the argument
  - the trigger word to use (default is reddit)
  - whether to allow NSFW content
  - how to submit the message (reply, respond, or just upload an image if available)

to use it, run your bot and use your trigger. so using default configs, it would look like this:

`!reddit funny`

to fetch a random post from the r/funny subreddit.

use a different trigger and default subreddit config for multiple instances to have shortcuts to subreddits you frequent
without getting duplicate responses in the same room!

if you choose to upload images directly with the bot, it will still fall back to using the reddit permalink to the post
if it can't recognize the link as a media file (so it does this for external links, reddit albums, etc that don't end
specifically in .png or .jpg etc)
