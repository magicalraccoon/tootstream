import os.path
import click
import getpass
import sys
import re
import configparser
import random
import readline
from toot_parser import TootParser
from mastodon import Mastodon, StreamListener
from collections import OrderedDict
from colored import fg, bg, attr, stylize


#Looks best with black background.
#TODO: Set color list in config file
COLORS = list(range(19,231))

# reserved config sections (disallowed as profile names)
RESERVED = ( "theme", "global" )


class IdDict:
    """Represents a mapping of local (tootstream) ID's to global
    (mastodon) IDs."""
    def __init__(self):
        self._map = []

    def to_local(self, global_id):
        """Returns the local ID for a global ID"""
        global_id = int(global_id) # In case a string gets passed
        try:
            return self._map.index(global_id)
        except ValueError:
            self._map.append(global_id)
            return len(self._map) - 1

    def to_global(self, local_id):
        """Returns the global ID for a local ID, or None if ID is invalid.
        Also prints an error message"""
        local_id = int(local_id)
        try:
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
        return users
    else:
        return users[0]['id']


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


def login(instance, client_id, client_secret, email, password):
    """
    Login to a Mastodon instance.

    Returns a valid Mastodon token if success, likely
    raises a Mastodon exception otherwise.
    """
    if (email == None):
        email = input("  Email used to login: ")
    if (password == None):
        password = getpass.getpass("  Password: ")

    # temporary object to aquire the token
    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        api_base_url="https://" + instance
    )
    return mastodon.log_in(email, password)


def get_or_input_profile(config, profile, instance=None, email=None, password=None):
    """
    Validate an existing profile or get user input
    to generate a new one.  If email/password is
    necessary, the user will be prompted 3 times
    before giving up.

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

    if (token == None or email != None or password != None):
        for i in [1, 2, 3]:
            try:
                token = login(instance, client_id, client_secret, email, password)
            except Exception as e:
                cprint("{}: did you type it right?".format(type(e).__name__), fg('red'))
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


def printUser(user):
    """Prints user data nicely with hardcoded colors."""
    print("@" + str(user['username']))
    cprint(user['display_name'], fg('cyan'))
    print(user['url'])
    cprint(re.sub('<[^<]+?>', '', user['note']), fg('red'))



def printUsersShort(users):
    for user in users:
        if not user: continue
        locked = ""
        # lock glyphs: masto web uses FontAwesome's U+F023 (nonstandard)
        # lock emoji: U+1F512
        if user['locked']: locked = " \U0001f512"
        userstr = "@"+str(user['acct'])+locked
        userid = "(id:"+str(user['id'])+")"
        userdisp = "'"+str(user['display_name'])+"'"
        userurl = str(user['url'])
        cprint("  "+userstr, fg('green'), end=" ")
        cprint(" "+userid, fg('red'), end=" ")
        cprint(" "+userdisp, fg('cyan'))
        cprint("      "+userurl, fg('blue'))

def printToot(toot):
    display_name = "  " + toot['account']['display_name'] + " "
    username = "@" + toot['account']['acct'] + " "
    reblogs_count = "  ♺:" + str(toot['reblogs_count'])
    favourites_count = " ♥:" + str(toot['favourites_count']) + " "
    toot_id = str(IDS.to_local(toot['id']))

    # Prints individual toot/tooter info
    random.seed(display_name)
    cprint(display_name, fg(random.choice(COLORS)), end="")
    cprint(username, fg('green'), end="")
    cprint(toot['created_at'], attr('dim'))

    cprint(reblogs_count, fg('cyan'), end="")
    cprint(favourites_count, fg('yellow'), end="")
    cprint("id:" + toot_id, fg('red'))

    # Shows boosted toots as well
    if toot['reblog']:
        username = "  Boosted @" + toot['reblog']['account']['acct'] +": "
        cprint(username, fg('blue'), end="")
        content = get_content(toot['reblog'])
    else:
        content = get_content(toot)

    print(content + "\n")

#####################################
######## DECORATORS          ########
#####################################
commands = OrderedDict()


def command(func):
    """Adds the function to the command list."""
    commands[func.__name__] = func
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

    ex: 'toot Hello World' will publish 'Hello World'."""
    mastodon.toot(rest)
    cprint("You tooted: ", fg('white') + attr('bold'), end="")
    cprint(rest, fg('magenta') + attr('bold') + attr('underlined'))
toot.__argstr__ = '<text>'


@command
def rep(mastodon, rest):
    """Reply to a toot by ID."""
    command = rest.split(' ', 1)
    parent_id = IDS.to_global(command[0])
    if parent_id is None:
        return
    try:
        reply_text = command[1]
    except IndexError:
        reply_text = ''
    parent_toot = mastodon.status(parent_id)
    mentions = [i['acct'] for i in parent_toot['mentions']]
    mentions.append(parent_toot['account']['acct'])
    mentions = ["@%s" % i for i in list(set(mentions))] # Remove dups
    mentions = ' '.join(mentions)
    # TODO: Ensure that content warning visibility carries over to reply
    reply_toot = mastodon.status_post('%s %s' % (mentions, reply_text),
                                      in_reply_to_id=int(parent_id))
    msg = "  Replied with: " + get_content(reply_toot)
    cprint(msg, fg('red'))
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
home.__argstr__ = ''


@command
def fed(mastodon, rest):
    """Displays the Federated timeline."""
    for toot in reversed(mastodon.timeline_public()):
        printToot(toot)
fed.__argstr__ = ''


@command
def local(mastodon, rest):
    """Displays the Public timeline."""
    for toot in reversed(mastodon.timeline_public()):
        printToot(toot)
local.__argstr__ = ''


@command
def stream(mastodon, rest):
    """Only 'home' and 'fed' are supported.

Use ctrl+C to end streaming"""
    print("Use ctrl+C to end streaming")
    try:
        if rest == "home" or rest == "":
            mastodon.user_stream(toot_listener)
        elif rest == "fed" or rest == "public":
            mastodon.public_stream(toot_listener)
        else:
            print("Only 'home' and 'fed' are supported")
    except KeyboardInterrupt:
        pass
stream.__argstr__ = '<timeline>'


@command
def note(mastodon, rest):
    """Displays the Notifications timeline."""
    for note in reversed(mastodon.notifications()):
        display_name = "  " + note['account']['display_name']
        username = " @" + note['account']['username']

        random.seed(display_name)


        # Mentions
        if note['type'] == 'mention':
            cprint(display_name + username, fg('magenta'))
            cprint(get_content(note['status']), attr('bold'), fg('white'))
            print()

        # Favorites
        elif note['type'] == 'favourite':
            reblogs_count = "  " + "♺:" + str(note['status']['reblogs_count'])
            favourites_count = " ♥:" + str(note['status']['favourites_count'])
            time = " " + note['status']['created_at']
            content = get_content(note['status'])


            cprint(display_name + username, fg(random.choice(COLORS)), end="")
            cprint(" favorited your status:", fg('yellow'))

            cprint(reblogs_count, fg('cyan'), end="")
            cprint(favourites_count, fg('yellow'))

            cprint(content, attr('dim'))


        # Boosts
        elif note['type'] == 'reblog':
            cprint(display_name + username + " boosted your status:", fg('yellow'))
            cprint(get_content(note['status']), attr('dim'))

        # Follows
        elif note['type'] == 'follow':
            username = re.sub('<[^<]+?>', '', username)
            display_name = note['account']['display_name']
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
            display_name = "  " + toot['account']['display_name']
            username = " @" + toot['account']['username'] + " "
            reblogs_count = "  ♺:" + str(toot['reblogs_count'])
            favourites_count = " ♥:" + str(toot['favourites_count']) + " "
            toot_id = str(IDS.to_local(toot['id']))

            # Prints individual toot/tooter info
            cprint(display_name, fg('green'), end="",)
            cprint(username + toot['created_at'], fg('yellow'))
            cprint(reblogs_count + favourites_count, fg('cyan'), end="")
            cprint(toot_id, fg('red'))

            # Shows boosted toots as well
            if toot['reblog']:
                username = "  Boosted @" + toot['reblog']['account']['acct'] +": "
                cprint(username, fg('blue'), end='')
                content = get_content(toot['reblog'])
            else:
                content = get_content(toot)

            print(content + "\n")
    # end #

    else:
        cprint("  Invalid format.\n"+usage, fg('red'))

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
            user = mastodon.follow_request_authorize(userid)
            # a more thorough check would be to call
            # mastodon.account_relationships(user['id'])
            # and check the returned data
            # here we're lazy and assume we're good if the
            # api return matches the request
            if user['id'] == userid:
                cprint("  user " + str(userid) + "'s request is accepted", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
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
            user = mastodon.follow_request_reject(userid)
            # a more thorough check would be to call
            # mastodon.account_relationships(user['id'])
            # and check the returned data
            # here we're lazy and assume we're good if the
            # api return matches the request
            if user['id'] == userid:
                cprint("  user " + str(userid) + "'s request is rejected", fg('blue'))
        except:
            cprint("  ... well, it *looked* like it was working ...", fg('red'))
reject.__argstr__ = '<user>'


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
@click.option( '--email', '-e', metavar='<string>',
               help='Email to login' )
@click.option( '--password', '-p', metavar='<PASSWD>',
               help='Password to login (UNSAFE)' )
@click.option( '--config', '-c', metavar='<file>',
               type=click.Path(exists=False, readable=True),
               default='~/.config/tootstream/tootstream.conf',
               help='Location of alternate configuration file to load' )
@click.option( '--profile', '-P', metavar='<profile>', default='default',
               help='Name of profile for saved credentials (default)' )
def main(instance, email, password, config, profile):
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
                            get_or_input_profile(config, profile, instance, email, password)

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
