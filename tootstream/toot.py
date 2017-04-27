import os.path
import click
import getpass
import sys
import re
import configparser
import random
#Do we still need readline?
#import readline
from toot_parser import TootParser
from mastodon import Mastodon
from collections import OrderedDict
from colored import fg, bg, attr, stylize

<<<<<<< HEAD
#Looks best with black background.
#TODO: Set color list in config file
COLORS = list(range(19,231))
=======
COLORS = ['red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
GLYPHS =     { # general icons, keys don't specifically match any Mastodon dict keys
               'fave':          '♥',
               'boost':         '♺',
               'pineapple':     '\U0001f34d', # pineapple
               'toots':         '\U0001f4ea', # mailbox (for toot counts)
               # next key matches key in user dict
               'locked':        '\U0001f512', # lock (masto web uses U+F023 from FontAwesome)
               # next 2 keys match keys in toot dict indicating user has faved/boosted
               'favourited':    '\U00002b50', # star '\U0001f31f' '\U00002b50'
               'reblogged':     '\U0001f1e7', # regional-B '\U0001f1e7'? reuse ♺?
               # next 4 keys match possible values for toot['visibility']
               'public':        '\U0001f30e', # globe
               'unlisted':      '\U0001f47b', # ghost '\U0001f47b' ... mute '\U0001f507' ??
               'private':       '\U0001f512', # lock
               'direct':        '\U0001f4e7', # envelopes: '\U0001f4e7' '\U0001f4e9' '\U0001f48c' '\U00002709'
               # next 5 keys match keys in relationship{}
               'followed_by':   '\U0001f43e', # pawprints '\U0001f43e'
               'following':     '\U0001f463', # footprints '\U0001f463'
               'blocking':      '\U0000274c', # thumbsdown '\U0001f44e', big X '\U0000274c', stopsign '\U0001f6d1'
               'muting':        '\U0001f6ab', # prohibited '\U0001f6ab', mute-spkr '\U0001f507', mute-bell '\U0001f515'
               'requested':     '\U00002753', # hourglass '\U0000231b', question '\U00002753'
               # catchall
               'unknown':       '\U0001f34d' }

>>>>>>> brrzap-add-glyphs

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

IDS = IdDict();

toot_parser = TootParser(indent='  ')

def get_content(toot):
    html = toot['content']
    toot_parser.reset()
    toot_parser.feed(html)
    toot_parser.close()
    return toot_parser.get_text()

def parse_config(filename):
    (dirpath, basename) = os.path.split(filename)
    if not (dirpath == "" or os.path.exists(dirpath)):
        os.makedirs(dirpath)

    if not os.path.isfile(filename):
        return {}

    config = configparser.ConfigParser()

    parsed = config.read(filename)
    if len(parsed) == 0:
        return {}

    return config

def save_config(filename, instance, client_id, client_secret, token):
    (dirpath, basename) = os.path.split(filename)
    if not (dirpath == "" or os.path.exists(dirpath)):
        os.makedirs(dirpath)
    config = configparser.ConfigParser()
    config['default'] = {
        'instance': instance,
        'client_id': client_id,
        'client_secret': client_secret,
        'token': token
    }

    with open(filename, 'w') as configfile:
        config.write(configfile)


def register_app(instance):
    # filename = CONF_PATH + instance + CLIENT_FILE
    # if not os.path.exists(CONF_PATH):
        # os.makedirs(CONF_PATH)
    # if os.path.isfile(filename):
        # return

    return Mastodon.create_app(
        'tootstream',
        api_base_url="https://" + instance
    )


def login(mastodon, instance, email, password):
    """
    Login to a Mastodon instance.
    Return a Mastodon client if login success, otherwise returns None.
    """

    return mastodon.log_in(email, password)

def cprint(text, style, end="\n"):
    print(stylize(text, style), end=end)


#####################################
######## BEGIN COMMAND BLOCK ########
#####################################
commands = OrderedDict()


def command(func):
    commands[func.__name__] = func
    return func


@command
def help(mastodon, rest):
    """List all commands."""
    print("Commands:")
    for command, cmd_func in commands.items():
        print("\t{}\t{}".format(command, cmd_func.__doc__))


@command
def toot(mastodon, rest):
    """Publish a toot. ex: 'toot Hello World' will publish 'Hello World'."""
    mastodon.toot(rest)
    cprint("You tooted: ", fg('magenta') + attr('bold'), end="")
    cprint(rest, fg('magenta') + bg('white') + attr('bold') + attr('underlined'))


@command
def boost(mastodon, rest):
    """Boosts a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_reblog(rest)
    boosted = mastodon.status(rest)
    msg = "  Boosted: " + get_content(boosted)
    cprint(msg, fg('green') + bg('red'))


@command
def unboost(mastodon, rest):
    """Removes a boosted tweet by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    msg = "  Removed boost: " + get_content(unboosted)
    cprint(msg, fg('red') + bg('green'))


@command
def fav(mastodon, rest):
    """Favorites a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_favourite(rest)
    faved = mastodon.status(rest)
    msg = "  Favorited: " + get_content(faved)
    cprint(msg, fg('red') + bg('yellow'))

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
    cprint(msg, fg('red') + bg('yellow'))

@command
def unfav(mastodon, rest):
    """Removes a favorite toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unfavourite(rest)
    unfaved = mastodon.status(rest)
    msg = "  Removed favorite: " + get_content(unfaved)
    cprint(msg, fg('yellow') + bg('red'))


@command
def home(mastodon, rest):
    """Displays the Home timeline."""
    for toot in reversed(mastodon.timeline_home()):
        display_name = "  " + toot['account']['display_name'] + " "
        username = ''.join(( "@", toot['account']['acct'], " ",
                             (GLYPHS['locked']+" " if toot['account']['locked'] else "") ))
        vis = ''.join(( "  vis:", GLYPHS[toot['visibility']], " " ))
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(IDS.to_local(toot['id']))
        toot_acted = " "+' '.join(( (GLYPHS['favourited'] if toot['favourited'] else ""),
                                    (GLYPHS['reblogged'] if toot['reblogged'] else "") ))

        # Prints individual toot/tooter info
        random.seed(display_name)
        cprint(display_name, fg(random.choice(COLORS)), end="")
        cprint(username, fg('green'), end="")
        cprint(toot['created_at'], attr('dim'))

        cprint(reblogs_count, fg('cyan'), end="")
        cprint(favourites_count, fg('yellow'), end="")
<<<<<<< HEAD
        cprint("id:" + toot_id, fg('red'))
=======
        cprint("id:" + toot_id, fg('red'), end="")
        cprint(vis + toot_acted, fg('blue'))
>>>>>>> brrzap-add-glyphs

        # Shows boosted toots as well
        if toot['reblog']:
            username = ''.join(( "  Boosted @", toot['reblog']['account']['acct'],
                                 (" "+GLYPHS['locked'] if toot['account']['locked'] else ""),
                                 ": " ))
            cprint(username, fg('blue'), end="")
            content = get_content(toot['reblog'])
        else:
            content = get_content(toot)

        print(content + "\n")

@command
def fed(mastodon, rest):
    """Displays the Federated timeline."""
    for toot in reversed(mastodon.timeline_public()):
        display_name = "  " + toot['account']['display_name']
        username = ''.join(( " @", toot['account']['username'], " ",
                             (GLYPHS['locked']+" " if toot['account']['locked'] else "") ))
        vis = ''.join(( "  vis:", GLYPHS[toot['visibility']], " " ))
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(IDS.to_local(toot['id']))
        toot_acted = " "+' '.join(( (GLYPHS['favourited'] if toot['favourited'] else ""),
                                    (GLYPHS['reblogged'] if toot['reblogged'] else "") ))

        # Prints individual toot/tooter info
<<<<<<< HEAD
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


@command
def local(mastodon, rest):
    """Displays the Local (instance) timeline."""
    for toot in reversed(mastodon.timeline_local()):
        display_name = "  " + toot['account']['display_name']
        username = " @" + toot['account']['username'] + " "
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
=======
        cprint(display_name, fg('green'), end="")
        cprint(username + toot['created_at'], fg('yellow'))
        cprint(reblogs_count + favourites_count, fg('cyan'), end=" ")
        cprint(toot_id, fg('red') + attr('bold'))
        cprint(vis + toot_acted, fg('blue'))
>>>>>>> brrzap-add-glyphs

        # Shows boosted toots as well
        if toot['reblog']:
            username = ''.join(( "  Boosted @", toot['reblog']['account']['acct'],
                                 (" "+GLYPHS['locked'] if toot['reblog']['account']['locked'] else ""),
                                 ": " ))
            cprint(username, fg('blue'), end="")
            content = get_content(toot['reblog'])
        else:
            content = get_content(toot)

        print(content + "\n")


@command
def note(mastodon, rest):
    """Displays the Notifications timeline."""
    for note in reversed(mastodon.notifications()):
        display_name = "  " + note['account']['display_name']
<<<<<<< HEAD
        username = " @" + note['account']['username']
        random.seed(display_name)
=======
        username = ''.join(( " @", note['account']['acct'],
                             (" "+GLYPHS['locked'] if note['account']['locked'] else "") ))
>>>>>>> brrzap-add-glyphs

        # Mentions
        if note['type'] == 'mention':
            cprint(display_name + username, (fg(random.choice(COLORS)), attr('bold')), end="")
            cprint(" mentioned you:", attr('bold'))

            cprint(get_content(note['status']), (fg('white'), attr('bold')))

        # Favorites
        elif note['type'] == 'favourite':
            vis = ''.join(( "  vis:", GLYPHS[note['status']['visibility']], " " ))
            reblogs_count = "  " + "♺:" + str(note['status']['reblogs_count'])
            favourites_count = " ♥:" + str(note['status']['favourites_count'])
            time = " " + note['status']['created_at']
            content = get_content(note['status'])
<<<<<<< HEAD

            cprint(display_name + username, fg(random.choice(COLORS)), end="")
            cprint(" favorited your status:", fg('yellow'))

            cprint(reblogs_count, fg('cyan'), end="")
            cprint(favourites_count, fg('yellow'))

            cprint(content, attr('dim'))
=======
            cprint(display_name + username + " favorited your status:", fg('green'))
            cprint(reblogs_count + favourites_count + vis + time + '\n' + content, fg('green'))
>>>>>>> brrzap-add-glyphs

        # Boosts
        elif note['type'] == 'reblog':
            cprint(display_name + username, fg(random.choice(COLORS)), end="")
            cprint(" boosted your status:", fg('blue'))
            cprint(get_content(note['status']), attr('dim'))

        # Follows
        elif note['type'] == 'follow':
            print("  ", end="")
            cprint(display_name + username + " followed you!", fg('red') + attr('bold'))

        # blank line
        print('')


@command
def exit(mastodon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command
def info(mastodon, rest):
    """Prints your user info."""
    user = mastodon.account_verify_credentials()

    counts = stylize( ''.join(( " ", GLYPHS['toots'], ":", str(user['statuses_count']),
                                " ", GLYPHS['following'], ":", str(user['following_count']),
                                " ", GLYPHS['followed_by'], ":", str(user['followers_count']) )),
                      fg('blue'))
    print( ''.join(( "@", str(user['acct']),
                     (" "+GLYPHS['locked'] if user['locked'] else ""),
                     " ", counts )) )
    cprint(user['display_name'], fg('cyan') + bg('red'))
    print(user['url'])
    cprint(re.sub('<[^<]+?>', '', user['note']), fg('red') + bg('green'))


@command
def delete(mastodon, rest):
    """Deletes your toot by ID"""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_delete(rest)
    print("Poof! It's gone.")


@command
def block(mastodon, rest):
    """Blocks a user by username."""
    # TODO: Find out how to get global usernames


@command
def unblock(mastodon, rest):
    """Unblocks a user by username."""
    # TODO: Find out how to get global usernames


@command
def follow(mastodon, rest):
    """Follows an account by username."""
    # TODO: Find out how to get global usernames


@command
def unfollow(mastodon, rest):
    """Unfollows an account by username."""
    # TODO: Find out how to get global usernames


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
def main(instance, email, password, config):
    configpath = os.path.expanduser(config)
    config = parse_config(configpath)

    if 'default' not in config:
        config['default'] = {}

    if (instance != None):
        # Nothing to do, just use value passed on the command line
        pass
    elif "instance" in config['default']:
        instance = config['default']['instance']

    else: instance = input("Which instance would you like to connect to? eg: 'mastodon.social' ")


    client_id = None
    if "client_id" in config['default']:
        client_id = config['default']['client_id']

    client_secret = None
    if "client_secret" in config['default']:
        client_secret = config['default']['client_secret']

    if (client_id == None or client_secret == None):
        client_id, client_secret = register_app(instance)

    token = None
    if "token" in config['default']:
        token = config['default']['token']

    if (token == None or email != None or password != None):
        if (email == None):
            email = input("Welcome to tootstream! Two-Factor-Authentication is currently not supported. Email used to login: ")
        if (password == None):
            password = getpass.getpass()

        mastodon = Mastodon(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url="https://" + instance
        )
        token = login(mastodon, instance, email, password)

    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        access_token=token,
        api_base_url="https://" + instance)

    save_config(configpath, instance, client_id, client_secret, token)

    say_error = lambda a, b: cprint("Invalid command. Use 'help' for a list of commands.",
            fg('white') + bg('red'))

    print("You are connected to ", end="")
    cprint(instance, fg('green') + attr('bold'))
    print("Enter a command. Use 'help' for a list of commands.")
    print("\n")

    user = mastodon.account_verify_credentials()
    prompt = "[@" + str(user['username']) + "]: "

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
