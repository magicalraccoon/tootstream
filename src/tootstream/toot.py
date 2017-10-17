import os.path
import click
import getpass
import sys
import re
import configparser
import random
import readline
import bisect
from tootstream.toot_parser import TootParser
from mastodon import Mastodon, StreamListener
from collections import OrderedDict
from colored import fg, bg, attr, stylize


#Looks best with black background.
#TODO: Set color list in config file
COLORS = list(range(19,231))
GLYPHS = {
    # general icons, keys don't match any Mastodon dict keys
    'fave':          '♥',
    'boost':         '♺',
    'pineapple':     '\U0001f34d', # pineapple
    'toots':         '\U0001f4ea', # mailbox (for toot counts)
    # next key matches key in user dict
    'locked':        '\U0001f512', # lock (masto web uses U+F023 from FontAwesome)
    # next 2 keys match keys in toot dict indicating user has already faved/boosted
    'favourited':    '\U00002605', # star '\U0001f31f' '\U00002b50' '\U00002605'
    'reblogged':     '\U0001f1e7', # reginal-B '\U0001f1e7' (or reuse ♺?)
    # next 4 keys match possible values for toot['visibility']
    'public':        '\U0001f30e', # globe
    'unlisted':      '\U0001f47b', # ghost '\U0001f47b' ... mute '\U0001f507' ??
    'private':       '\U0001f512', # lock
    'direct':        '\U0001f4e7', # envelopes: '\U0001f4e7' '\U0001f4e9' '\U0001f48c' '\U00002709'
    # next 5 keys match keys in relationship{}
    'followed_by':   '\U0001f43e', # pawprints '\U0001f43e'
    'following':     '\U0001f463', # footprints '\U0001f463'
    'blocking':      '\U0000274c', # thumbsdown '\U0001f44e', big X '\U0000274c', stopsign '\U0001f6d1'
    'muting':        '\U0001f6ab', # mute-spkr '\U0001f507', mute-bell '\U0001f515', prohibited '\U0001f6ab'
    'requested':     '\U00002753', # hourglass '\U0000231b', question '\U00002753'
    # catchall
    'unknown':       '\U0001f34d' }

# reserved config sections (disallowed as profile names)
RESERVED = ( "theme", "global" )


class IdDict:
    """Represents a mapping of local (tootstream) ID's to global
    (mastodon) IDs."""
    def __init__(self):
        self._map = []

    def to_local(self, global_id):
        """Returns the local ID for a global ID"""
        try:
            global_id = int(global_id) # In case a string gets passed
            return self._map.index(global_id)
        except ValueError:
            self._map.append(global_id)
            return len(self._map) - 1

    def to_global(self, local_id):
        """Returns the global ID for a local ID, or None if ID is invalid.
        Also prints an error message"""
        try:
            local_id = int(local_id)
            return self._map[local_id]
        except:
            cprint('Invalid ID.', fg('red'))
            return None

class TootListener(StreamListener):
    def on_update(self, status):
        printToot(status)

IDS = IdDict();

toot_parser = TootParser(indent='  ')

toot_listener = TootListener()

#####################################
######## UTILITY FUNCTIONS   ########
#####################################
def get_content(toot):
    html = toot['content']
    toot_parser.reset()
    toot_parser.feed(html)
    toot_parser.close()
    return toot_parser.get_text()


def get_userid(mastodon, rest):
    # we got some user input.  we need a userid (int).
    # returns userid as int, -1 on error, or list of users if ambiguous.
    if not rest:
        return -1

    # maybe it's already an int
    try:
        return int(rest)
    except ValueError:
        pass

    # not an int
    users = mastodon.account_search(rest)
    if not users:
        return -1
    elif len(users) > 1:
        # Mastodon's search is fuzzier than we want; check for exact match

        query = (rest[1:] if rest.startswith('@') else rest)
        (quser, _, qinstance) = query.partition('@')
        localinstance = mastodon.instance()

        # on uptodate servers, exact match should be first in list
        for user in users:
            # match user@remoteinstance, localuser
            if query == user['acct']:
                return user['id']
            # match user@localinstance
            elif quser == user['acct'] and qinstance == localinstance['uri']:
                return user['id']

        # no exact match; return list
        return users
    else:
        return users[0]['id']


#####################################
########     COMPLETION      ########
#####################################

completion_list = []

def complete(text, state):
    """Return the state-th potential completion for the name-fragment, text"""
    options = [name for name in completion_list if name.startswith(text)]
    if state < len(options):
        return options[state] + ' '
    else:
        return None

def completion_add(toot):
    """Add usernames (original author, mentions, booster) co completion_list"""
    if toot['reblog']:
        username = '@' + toot['reblog']['account']['acct']
        if username not in completion_list:
            bisect.insort(completion_list, username)
    username = '@' + toot['account']['acct']
    if username not in completion_list:
        bisect.insort(completion_list, username)
    for user in ['@' + user['acct'] for user in toot['mentions']]:
        if user not in completion_list:
            bisect.insort(completion_list, username)

#####################################
######## CONFIG FUNCTIONS    ########
#####################################
def parse_config(filename):
    """
    Reads configuration from the specified file.
    On success, returns a ConfigParser object containing
    data from the file.  If the file does not exist,
    returns an empty ConfigParser object.

    Exits the program with error if the specified file
    cannot be parsed to prevent damaging unknown files.
    """
    if not os.path.isfile(filename):
        cprint("...No configuration found, generating...", fg('cyan'))
        config = configparser.ConfigParser()
        return config

    config = configparser.ConfigParser()
    try:
        config.read(filename)
    except configparser.Error:
        cprint("This does not look like a valid configuration: {}".format(filename), fg('red'))
        sys.exit(1)

    return config


def save_config(filename, config):
    """
    Writes a ConfigParser object to the specified file.
    If the file does not exist, this will try to create
    it with mode 600 (user-rw-only).

    Errors while writing are reported to the user but
    will not exit the program.
    """
    (dirpath, basename) = os.path.split(filename)
    if not (dirpath == "" or os.path.exists(dirpath)):
        os.makedirs(dirpath)

    # create as user-rw-only if possible
    if not os.path.exists(filename):
        try:
            os.open(filename, flags=os.O_CREAT|os.O_APPEND, mode=0o600)
        except Exception as e:
            cprint("Unable to create file {}: {}".format(filename, e), fg('red'))

    try:
        with open(filename, 'w') as configfile:
            config.write(configfile)
    except os.error:
        cprint("Unable to write configuration to {}".format(filename), fg('red'))
    return



def register_app(instance):
    """
    Registers this client with a Mastodon instance.

    Returns valid credentials if success, likely
    raises a Mastodon exception otherwise.
    """
    return Mastodon.create_app( 'tootstream',
                                api_base_url="https://" + instance )


def login(instance, client_id, client_secret):
    """
    Login to a Mastodon instance.

    Returns a valid Mastodon token if success, likely
    raises a Mastodon exception otherwise.
    """

    # temporary object to aquire the token
    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        api_base_url="https://" + instance
    )

    print("Click the link to authorize login.")
    print(mastodon.auth_request_url())
    print()
    code = input("Enter the code you received >")

    return mastodon.log_in(code = code)


def get_or_input_profile(config, profile, instance=None):
    """
    Validate an existing profile or get user input
    to generate a new one.  If the user is not logged in,
    the user will be prompted 3 times before giving up.

    On success, returns valid credentials: instance,
    client_id, client_secret, token.
    On failure, returns None, None, None, None.
    """
    # shortcut for preexisting profiles
    if config.has_section(profile):
        try:
            return  config[profile]['instance'], \
                    config[profile]['client_id'], \
                    config[profile]['client_secret'], \
                    config[profile]['token']
        except:
            pass
    else:
        config.add_section(profile)

    # no existing profile or it's incomplete
    if (instance != None):
        # Nothing to do, just use value passed on the command line
        pass
    elif "instance" in config[profile]:
        instance = config[profile]['instance']
    else:
        cprint("  Which instance would you like to connect to? eg: 'mastodon.social'", fg('blue'))
        instance = input("  Instance: ")


    client_id = None
    if "client_id" in config[profile]:
        client_id = config[profile]['client_id']

    client_secret = None
    if "client_secret" in config[profile]:
        client_secret = config[profile]['client_secret']

    if (client_id == None or client_secret == None):
        try:
            client_id, client_secret = register_app(instance)
        except Exception as e:
            cprint("{}: please try again later".format(type(e).__name__), fg('red'))
            return None, None, None, None

    token = None
    if "token" in config[profile]:
        token = config[profile]['token']

    if (token == None):
        for i in [1, 2, 3]:
            try:
                token = login(instance, client_id, client_secret)
            except Exception as e:
                cprint("Error authorizing app. Did you enter the code correctly?", fg('red'))
            if token: break

        if not token:
            cprint("Giving up after 3 failed login attempts", fg('red'))
            return None, None, None, None

    return instance, client_id, client_secret, token


#####################################
######## OUTPUT FUNCTIONS    ########
#####################################
def cprint(text, style, end="\n"):
    print(stylize(text, style), end=end)


def format_username(user):
    """Get a user's account name including lock indicator."""
    return ''.join(( "@", user['acct'],
                     (" {}".format(GLYPHS['locked']) if user['locked'] else "") ))


def format_user_counts(user):
    """Get a user's toot/following/follower counts."""
    countfmt = "{} :{}"
    return ' '.join(( countfmt.format(GLYPHS['toots'], user['statuses_count']),
                      countfmt.format(GLYPHS['following'], user['following_count']),
                      countfmt.format(GLYPHS['followed_by'], user['followers_count']) ))


def printUser(user):
    """Prints user data nicely with hardcoded colors."""
    counts = stylize(format_user_counts(user), fg('blue'))

    print(format_username(user) + " " + counts)
    cprint(user['display_name'], fg('cyan'))
    print(user['url'])
    cprint(re.sub('<[^<]+?>', '', user['note']), fg('red'))


def printUsersShort(users):
    for user in users:
        if not user: continue
        userid = "(id:"+str(user['id'])+")"
        userdisp = "'"+str(user['display_name'])+"'"
        userurl = str(user['url'])
        cprint("  "+format_username(user), fg('green'), end=" ")
        cprint(" "+userid, fg('red'), end=" ")
        cprint(" "+userdisp, fg('cyan'))
        cprint("      "+userurl, fg('blue'))


def format_toot_nameline(toot, dnamestyle):
    """Get the display, usernames and timestamp for a typical toot printout.

    dnamestyle: a fg/bg/attr set applied to the display name with stylize()"""
    # name line: display name, user@instance, lock if locked, timestamp
    if not toot: return ''
    out = [ stylize(toot['account']['display_name'], dnamestyle),
            stylize(format_username(toot['account']), fg('green')),
            stylize(toot['created_at'], attr('dim')) ]
    return ' '.join(out)


def format_toot_idline(toot):
    """Get boost/faves counts, toot ID, visibility, and
    already-faved/boosted indicators for a typical toot printout."""
    # id-and-counts line: boosted count, faved count, tootid, visibility, favourited-already, boosted-already
    if not toot: return ''
    out = [ stylize(GLYPHS['boost']+":"+str(toot['reblogs_count']), fg('cyan')),
            stylize(GLYPHS['fave']+":"+str(toot['favourites_count']), fg('yellow')),
            stylize("id:"+str(IDS.to_local(toot['id'])), fg('red')),
            stylize("vis:"+GLYPHS[toot['visibility']], fg('blue')) ]

    # app used to post. frequently empty
    if toot.get('application') and toot.get('application').get('name'):
        out.append( ''.join(( stylize("via ", fg('white')),
                              stylize(toot['application']['name'], fg('blue')) )))
    # some toots lack these next keys, use get() to avoid KeyErrors
    if toot.get('favourited'):
        out.append(stylize(GLYPHS['favourited'], fg('magenta')))
    if toot.get('reblogged'):
        out.append(stylize(GLYPHS['reblogged'], fg('magenta')))

    return ' '.join(out)


def printToot(toot):
    if not toot: return

    out = []
    # if it's a boost, only output header line from toot
    # then get other data from toot['reblog']
    if toot['reblog']:
        header = stylize("  Boosted by ", fg('yellow'))
        name = " ".join(( toot['account']['display_name'],
                          format_username(toot['account'])+":" ))
        out.append(header + stylize(name, fg('blue')))
        toot = toot['reblog']

    # get the first two lines
    random.seed(toot['account']['display_name'])
    out += [ "  "+format_toot_nameline(toot, fg(random.choice(COLORS))),
             "  "+format_toot_idline(toot) ]

    if toot['spoiler_text'] != '':
        # pass CW through get_content for wrapping/indenting
        faketoot = { 'content': "[CW: "+toot['spoiler_text']+"]" }
        out.append( stylize(get_content(faketoot), fg('red')))

    out.append( get_content(toot) )

    if toot['media_attachments']:
        # simple version: output # of attachments. TODO: urls instead?
        nsfw = ("NSFW " if toot['sensitive'] else "")
        out.append( stylize("  "+nsfw+"media: "+str(len(toot['media_attachments'])), fg('magenta')))

    print( '\n'.join(out) )
    print()


def edittoot():
    edited_message = click.edit()
    if edited_message:
        return edited_message
    return ''


#####################################
######## DECORATORS          ########
#####################################
commands = OrderedDict()

def command(func):
    """Adds the function to the command list."""
    commands[func.__name__] = func
    bisect.insort(completion_list, func.__name__)
    return func

#####################################
######## BEGIN COMMAND BLOCK ########
#####################################
__friendly_cmd_error__ = 'Unable to comply.  Command not found: "{}"'
__friendly_help_header__ = """
Tootstream Help:
===============
  usage: {} {}

{}
"""


@command
def help(mastodon, rest):
    """List all commands or show detailed help."""
    # argument case
    if rest and rest != '':
        try:
            args = rest.split()
            cmd_func = commands[args[0]]
        except:
            print(__friendly_cmd_error__.format(rest))
            return

        try:
            cmd_args = cmd_func.__argstr__
        except:
            cmd_args = ''
        # print a friendly header and the detailed help
        print(__friendly_help_header__.format( cmd_func.__name__,
                                               cmd_args,
                                               cmd_func.__doc__ ))
        return

    # no argument, show full list
    print("Commands:")
    for command, cmd_func in commands.items():
        # get only the docstring's first line for the column view
        (cmd_doc, *_) = cmd_func.__doc__.partition('\n')
        try:
            cmd_args = cmd_func.__argstr__
        except:
            cmd_args = ''
        print("{:>15} {:<11}  {:<}".format(command, cmd_args, cmd_doc))
help.__argstr__ = '<cmd>'


@command
def toot(mastodon, rest):
    """Publish a toot.

    ex: 'toot Hello World' will publish 'Hello World'.
    If no text is given then this will run the default editor."""
    if rest == '':
        rest = edittoot()
    try:
        mastodon.toot(rest)
        cprint("You tooted: ", fg('white') + attr('bold'), end="")
        cprint(rest, fg('magenta') + attr('bold') + attr('underlined'))
    except Exception as e:
        cprint("Received error: ", fg('red') + attr('bold'), end="")
        cprint(e, fg('magenta') + attr('bold') + attr('underlined'))

toot.__argstr__ = '<text>'


@command
def rep(mastodon, rest):
    """Reply to a toot by ID.

    ex: 'rep 42 Thank you!' will reply 'Thank you!' to message ID 42.
    If no text is given then this will run the default editor."""
    command = rest.split(' ', 1)

    if command[0] == '':
        msg = "  No message to reply to."
        cprint(msg, fg('red'))
        return

    parent_id = IDS.to_global(command[0])
    if parent_id is None:
        return
    if len(command) < 2:
        reply_text = edittoot()
    else:
        reply_text = command[1]
    parent_toot = mastodon.status(parent_id)
    mentions = [i['acct'] for i in parent_toot['mentions']]
    mentions.append(parent_toot['account']['acct'])
    mentions = ["@%s" % i for i in list(set(mentions))] # Remove dups
    mentions = ' '.join(mentions)
    # TODO: Ensure that content warning visibility carries over to reply
    try:
        reply_toot = mastodon.status_post('%s %s' % (mentions, reply_text),
                                        in_reply_to_id=int(parent_id))
        msg = "  Replied with: " + get_content(reply_toot)
        cprint(msg, fg('red'))
    except Exception as e:
        cprint("Received error: ", fg('red') + attr('bold'), end="")
        cprint(e, fg('magenta') + attr('bold') + attr('underlined'))
rep.__argstr__ = '<id> <text>'


@command
def delete(mastodon, rest):
    """Deletes your toot by ID"""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_delete(rest)
    print("Poof! It's gone.")
delete.__argstr__ = '<id>'


@command
def boost(mastodon, rest):
    """Boosts a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_reblog(rest)
    boosted = mastodon.status(rest)
    msg = "  You boosted: ", fg('white') + get_content(boosted)
    cprint(msg, fg('green'))
boost.__argstr__ = '<id>'


@command
def unboost(mastodon, rest):
    """Removes a boosted tweet by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    msg = "  Removed boost: " + get_content(unboosted)
    cprint(msg, fg('red'))
unboost.__argstr__ = '<id>'


@command
def fav(mastodon, rest):
    """Favorites a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_favourite(rest)
    faved = mastodon.status(rest)
    msg = "  Favorited: " + get_content(faved)
    cprint(msg, fg('red'))
fav.__argstr__ = '<id>'


@command
def unfav(mastodon, rest):
    """Removes a favorite toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unfavourite(rest)
    unfaved = mastodon.status(rest)
    msg = "  Removed favorite: " + get_content(unfaved)
    cprint(msg, fg('yellow'))
unfav.__argstr__ = '<id>'


@command
def home(mastodon, rest):
    """Displays the Home timeline."""
    for toot in reversed(mastodon.timeline_home()):
        printToot(toot)
        completion_add(toot)
        
home.__argstr__ = ''


@command
def fed(mastodon, rest):
    """Displays the Federated timeline."""
    for toot in reversed(mastodon.timeline_public()):
        printToot(toot)
        completion_add(toot)
fed.__argstr__ = ''


@command
def local(mastodon, rest):
    """Displays the Local timeline."""
    for toot in reversed(mastodon.timeline_local()):
        printToot(toot)
        completion_add(toot)
local.__argstr__ = ''


@command
def stream(mastodon, rest):
    """Streams a timeline. Specify home, fed, local, or a #hashtagname.

Use ctrl+C to end streaming"""
    print("Use ctrl+C to end streaming")
    try:
        if rest == "home" or rest == "":
            mastodon.user_stream(toot_listener)
        elif rest == "fed" or rest == "public":
            mastodon.public_stream(toot_listener)
        elif rest == "local":
            # TODO: no corresponding Mastodon method yet, will probably be
            #mastodon.local_stream(TootListener())
            # for now use the stream helper directly
            mastodon._Mastodon__stream('/api/v1/streaming/public/local', TootListener())
        elif rest.startswith('#'):
            tag = rest[1:]
            # TODO: this should work but currently broken
            #mastodon.hashtag_stream(tag, TootListener())
            # for now use the stream helper directly
            endpt = "/api/v1/streaming/hashtag?tag={}".format(tag)
            mastodon._Mastodon__stream(endpt, TootListener())
        else:
            print("Only 'home', 'fed', 'local', and '#hashtag' streams are supported.")
    except KeyboardInterrupt:
        pass
stream.__argstr__ = '<timeline>'


@command
def note(mastodon, rest):
    """Displays the Notifications timeline."""
    for note in reversed(mastodon.notifications()):
        display_name = "  " + note['account']['display_name']
        username = format_username(note['account'])

        random.seed(display_name)


        # Mentions
        if note['type'] == 'mention':
            time = " " + stylize(note['status']['created_at'], attr('dim'))
            cprint(display_name + username, fg('magenta'))
            print("  " + format_toot_idline(note['status']) + "  " + time)
            cprint(get_content(note['status']), attr('bold'), fg('white'))
            print(stylize("", attr('dim')))

        # Favorites
        elif note['type'] == 'favourite':
            countsline = format_toot_idline(note['status'])
            time = " " + stylize(note['status']['created_at'], attr('dim'))
            content = get_content(note['status'])


            cprint(display_name + username, fg(random.choice(COLORS)), end="")
            cprint(" favorited your status:", fg('yellow'))
            print("  "+countsline + stylize(time, attr('dim')))
            cprint(content, attr('dim'))


        # Boosts
        elif note['type'] == 'reblog':
            cprint(display_name + username + " boosted your status:", fg('yellow'))
            cprint(get_content(note['status']), attr('dim'))

        # Follows
        elif note['type'] == 'follow':
            print("  ", end="")
            cprint(display_name + username + " followed you!", fg('yellow'))

        # blank line
        print()
note.__argstr__ = ''


@command
def block(mastodon, rest):
    """Blocks a user by username or id.

    ex: block 23
        block @user
        block @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_block(userid)
            if relations['blocking']:
                cprint("  user " + str(userid) + " is now blocked", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
block.__argstr__ = '<user>'


@command
def unblock(mastodon, rest):
    """Unblocks a user by username or id.

    ex: unblock 23
        unblock @user
        unblock @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_unblock(userid)
            if not relations['blocking']:
                cprint("  user " + str(userid) + " is now unblocked", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
unblock.__argstr__ = '<user>'


@command
def follow(mastodon, rest):
    """Follows an account by username or id.

    ex: follow 23
        follow @user
        follow @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_follow(userid)
            if relations['following']:
                cprint("  user " + str(userid) + " is now followed", fg('blue'))
                username = '@' + mastodon.account(userid)['acct']
                if username not in completion_list:
                    bisect.insort(completion_list, username)
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
follow.__argstr__ = '<user>'


@command
def unfollow(mastodon, rest):
    """Unfollows an account by username or id.

    ex: unfollow 23
        unfollow @user
        unfollow @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_unfollow(userid)
            if not relations['following']:
                cprint("  user " + str(userid) + " is now unfollowed", fg('blue'))
            username = '@' + mastodon.account(userid)['acct']
            if username in completion_list:
                completion_list.remove(username)
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
unfollow.__argstr__ = '<user>'


@command
def mute(mastodon, rest):
    """Mutes a user by username or id.

    ex: mute 23
        mute @user
        mute @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_mute(userid)
            if relations['muting']:
                cprint("  user " + str(userid) + " is now muted", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
mute.__argstr__ = '<user>'


@command
def unmute(mastodon, rest):
    """Unmutes a user by username or id.

    ex: unmute 23
        unmute @user
        unmute @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            relations = mastodon.account_unmute(userid)
            if not relations['muting']:
                cprint("  user " + str(userid) + " is now unmuted", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
unmute.__argstr__ = '<user>'


@command
def search(mastodon, rest):
    """Search for a #tag or @user.

    ex:  search #tagname
         search @user
         search @user@instance.example.com"""
    usage = str( "  usage: search #tagname\n" +
                 "         search @username" )
    try:
        indicator = rest[:1]
        query = rest[1:]
    except:
        cprint(usage, fg('red'))
        return

    # @ user search
    if indicator == "@" and not query == "":
        users = mastodon.account_search(query)

        for user in users:
            printUser(user)
    # end @

    # # hashtag search
    elif indicator == "#" and not query == "":
        for toot in reversed(mastodon.timeline_hashtag(query)):
            printToot(toot)
    # end #

    else:
        cprint("  Invalid format. (General search coming soon.)\n"+usage, fg('red'))

    return
search.__argstr__ = '<query>'


@command
def info(mastodon, rest):
    """Prints your user info."""
    user = mastodon.account_verify_credentials()
    printUser(user)
info.__argstr__ = ''


@command
def followers(mastodon, rest):
    """Lists users who follow you."""
    # TODO: compare user['followers_count'] to len(users)
    #       request more from server if first call doesn't get full list
    # TODO: optional username/userid to show another user's followers?
    user = mastodon.account_verify_credentials()
    users = mastodon.account_followers(user['id'])
    if not users:
        cprint("  Nobody follows you", fg('red'))
    else:
        cprint("  People who follow you ({}):".format(len(users)), fg('magenta'))
        printUsersShort(users)
followers.__argstr__ = ''


@command
def following(mastodon, rest):
    """Lists users you follow."""
    # TODO: compare user['following_count'] to len(users)
    #       request more from server if first call doesn't get full list
    # TODO: optional username/userid to show another user's following?
    user = mastodon.account_verify_credentials()
    users = mastodon.account_following(user['id'])
    if not users:
        cprint("  You aren't following anyone", fg('red'))
    else:
        cprint("  People you follow ({}):".format(len(users)), fg('magenta'))
        printUsersShort(users)
following.__argstr__ = ''


@command
def blocks(mastodon, rest):
    """Lists users you have blocked."""
    users = mastodon.blocks()
    if not users:
        cprint("  You haven't blocked anyone (... yet)", fg('red'))
    else:
        cprint("  You have blocked:", fg('magenta'))
        printUsersShort(users)
blocks.__argstr__ = ''


@command
def mutes(mastodon, rest):
    """Lists users you have muted."""
    users = mastodon.mutes()
    if not users:
        cprint("  You haven't muted anyone (... yet)", fg('red'))
    else:
        cprint("  You have muted:", fg('magenta'))
        printUsersShort(users)
mutes.__argstr__ = ''


@command
def requests(mastodon, rest):
    """Lists your incoming follow requests.

    Run 'accept id' to accept a request
     or 'reject id' to reject."""
    users = mastodon.follow_requests()
    if not users:
        cprint("  You have no incoming requests", fg('red'))
    else:
        cprint("  These users want to follow you:", fg('magenta'))
        printUsersShort(users)
        cprint("  run 'accept <id>' to accept", fg('magenta'))
        cprint("   or 'reject <id>' to reject", fg('magenta'))
requests.__argstr__ = ''


@command
def accept(mastodon, rest):
    """Accepts a user's follow request by username or id.

    ex: accept 23
        accept @user
        accept @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            mastodon.follow_request_authorize(userid)
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
            return

        # assume it worked if no exception
        cprint("  user {}'s request is accepted".format(userid), fg('blue'))
    return
accept.__argstr__ = '<user>'


@command
def reject(mastodon, rest):
    """Rejects a user's follow request by username or id.

    ex: reject 23
        reject @user
        reject @user@instance.example.com"""
    userid = get_userid(mastodon, rest)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        try:
            mastodon.follow_request_reject(userid)
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
            return

        # assume it worked if no exception
        cprint("  user {}'s request is rejected".format(userid), fg('blue'))
    return
reject.__argstr__ = '<user>'


@command
def faves(mastodon, rest):
    """Displays posts you've favourited."""
    for toot in reversed(mastodon.favourites()):
        printToot(toot)
faves.__argstr__ = ''


@command
def view(mastodon, rest):
    """Displays toots from another user.

     <user>:   a userID, @username, or @user@instance
        <N>:   (optional) show N toots maximum

    ex: view 23
        view @user 10
        view @user@instance.example.com"""
    (userid, _, count) = rest.partition(' ')

    # validate count argument
    if not count:
        count = None
    else:
        try:
            count = int(count)
        except ValueError:
            cprint("  invalid count: {}".format(count), fg('red'))
            return

    # validate userid argument
    userid = get_userid(mastodon, userid)
    if isinstance(userid, list):
        cprint("  multiple matches found:", fg('red'))
        printUsersShort(userid)
    elif userid == -1:
        cprint("  username not found", fg('red'))
    else:
        for toot in reversed(mastodon.account_statuses(userid, limit=count)):
            printToot(toot)

    return
view.__argstr__ = '<user> <N>'


@command
def me(mastodon, rest):
    """Displays toots you've tooted.

        <N>:   (optional) show N toots maximum"""
    itme = mastodon.account_verify_credentials()
    # no specific API for user's own timeline
    # let view() do the work
    view(mastodon, "{} {}".format(itme['id'], rest))
me.__argstr__ = '<N>'


@command
def quit(mastodon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")
quit.__argstr__ = ''


#####################################
######### END COMMAND BLOCK #########
#####################################


def authenticated(mastodon):
    if not os.path.isfile(APP_CRED):
        return False
    if mastodon.account_verify_credentials().get('error'):
        return False
    return True


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.option( '--instance', '-i', metavar='<string>',
               help='Hostname of the instance to connect' )
@click.option( '--config', '-c', metavar='<file>',
               type=click.Path(exists=False, readable=True),
               default='~/.config/tootstream/tootstream.conf',
               help='Location of alternate configuration file to load' )
@click.option( '--profile', '-P', metavar='<profile>', default='default',
               help='Name of profile for saved credentials (default)' )
def main(instance, config, profile):
    configpath = os.path.expanduser(config)
    if os.path.isfile(configpath) and not os.access(configpath, os.W_OK):
        # warn the user before they're asked for input
        cprint("Config file does not appear to be writable: {}".format(configpath), fg('red'))

    config = parse_config(configpath)

    # make sure profile name is legal
    profile = re.sub(r'\s+', '', profile)  # disallow whitespace
    profile = profile.lower()              # force to lowercase
    if profile == '' or profile in RESERVED:
        cprint("Invalid profile name: {}".format(profile), fg('red'))
        sys.exit(1)

    if not config.has_section(profile):
        config.add_section(profile)

    instance, client_id, client_secret, token = \
                            get_or_input_profile(config, profile, instance)

    if not token:
        cprint("Could not log you in.  Please try again later.", fg('red'))
        sys.exit(1)

    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        access_token=token,
        api_base_url="https://" + instance)

    # update config before writing
    if "token" not in config[profile]:
        config[profile] = {
                'instance': instance,
                'client_id': client_id,
                'client_secret': client_secret,
                'token': token
        }

    save_config(configpath, config)

    say_error = lambda a, b: cprint("Invalid command. Use 'help' for a list of commands.",
            fg('white') + bg('red'))

    print("You are connected to ", end="")
    cprint(instance, fg('green') + attr('bold'))
    print("Enter a command. Use 'help' for a list of commands.")
    print("\n")

    user = mastodon.account_verify_credentials()
    prompt = "[@{} ({})]: ".format(str(user['username']), profile)
    
    # Completion setup stuff
    for i in mastodon.account_following(user['id'], limit=80):
        bisect.insort(completion_list, '@' + i['acct'])
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(' ')
    
    
    while True:
        command = input(prompt).split(' ', 1)
        rest = ""
        try:
            rest = command[1]
        except IndexError:
            pass
        command = command[0]
        cmd_func = commands.get(command, say_error)
        cmd_func(mastodon, rest)


if __name__ == '__main__':
    main()
