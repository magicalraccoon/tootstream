import os.path
import click
import getpass
import sys
import re
import configparser
import random
import readline
from toot_parser import TootParser
from mastodon import Mastodon
from collections import OrderedDict
from termcolor import cprint

COLORS = ['red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']

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
            tprint('Invalid ID.', 'red', '')
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


def tprint(text, color, bgColor):
    printFn = lambda x: cprint(x, color)
    if bgColor != "":
        bg = 'on_' + bgColor
        printFn = lambda x: cprint(x, color, bg)
    printFn(text)


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
    cprint("You tooted: ", 'magenta', attrs=['bold'], end="")
    cprint(rest, 'magenta', 'on_white', attrs=['bold', 'underline'])


@command
def boost(mastodon, rest):
    """Boosts a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_reblog(rest)
    boosted = mastodon.status(rest)
    msg = "  Boosted: " + get_content(boosted)
    tprint(msg, 'green', 'red')


@command
def unboost(mastodon, rest):
    """Removes a boosted tweet by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    msg = "  Removed boost: " + get_content(unboosted)
    tprint(msg, 'red', 'green')


@command
def fav(mastodon, rest):
    """Favorites a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_favourite(rest)
    faved = mastodon.status(rest)
    msg = "  Favorited: " + get_content(faved)
    tprint(msg, 'red', 'yellow')

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
    tprint(msg, 'red', 'yellow')

@command
def unfav(mastodon, rest):
    """Removes a favorite toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unfavourite(rest)
    unfaved = mastodon.status(rest)
    msg = "  Removed favorite: " + get_content(unfaved)
    tprint(msg, 'yellow', 'red')


@command
def home(mastodon, rest):
    """Displays the Home timeline."""
    for toot in reversed(mastodon.timeline_home()):
        display_name = "  " + toot['account']['display_name'] + " "
        username = "@" + toot['account']['acct'] + " "
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(IDS.to_local(toot['id']))

        # Prints individual toot/tooter info
        random.seed(display_name)
        cprint(display_name, random.choice(COLORS), end="")
        cprint(username, 'green', end="")
        cprint(toot['created_at'], 'grey')

        cprint(reblogs_count, 'cyan', end="")
        cprint(favourites_count, 'yellow', end="")
        
        cprint("id:" + toot_id, 'red')

        # Shows boosted toots as well
        if toot['reblog']:
            username = "  Boosted @" + toot['reblog']['account']['acct'] +": "
            cprint(username, 'blue', end='')
            content = get_content(toot['reblog'])
        else:
            content = get_content(toot)

        print(content + "\n")

@command
def public(mastodon, rest):
    """Displays the Public timeline."""
    for toot in reversed(mastodon.timeline_public()):
        display_name = "  " + toot['account']['display_name']
        username = " @" + toot['account']['username'] + " "
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(IDS.to_local(toot['id']))

        # Prints individual toot/tooter info
        cprint(display_name, 'green', end="",)
        cprint(username + toot['created_at'], 'yellow')
        cprint(reblogs_count + favourites_count, 'cyan', end="")
        cprint(toot_id, 'red', attrs=['bold'])

        # Shows boosted toots as well
        if toot['reblog']:
            username = "  Boosted @" + toot['reblog']['account']['acct'] +": "
            cprint(username, 'blue', end='')
            content = get_content(toot['reblog'])
        else:
            content = get_content(toot)

        print(content + "\n")


@command
def note(mastodon, rest):
    """Displays the Notifications timeline."""
    for note in reversed(mastodon.notifications()):
        display_name = "  " + note['account']['display_name']
        username = " @" + note['account']['username']

        # Mentions
        if note['type'] == 'mention':
            tprint(display_name + username, 'magenta', '')
            tprint(get_content(note['status']), 'magenta', '')

        # Favorites
        elif note['type'] == 'favourite':
            reblogs_count = "  " + "♺:" + str(note['status']['reblogs_count'])
            favourites_count = " ♥:" + str(note['status']['favourites_count'])
            time = " " + note['status']['created_at']
            content = get_content(note['status'])
            tprint(display_name + username + " favorited your status:", 'green', '')
            tprint(reblogs_count + favourites_count + time + '\n' + content, 'green', '')

        # Boosts
        elif note['type'] == 'reblog':
            tprint(display_name + username + " boosted your status:", 'yellow', '')
            tprint(get_content(note['status']), 'yellow', '')

        # Follows
        elif note['type'] == 'follow':
            username = re.sub('<[^<]+?>', '', username)
            display_name = note['account']['display_name']
            cprint("  ", end="")
            cprint(display_name + username + " followed you!", 'red', 'on_green')

        # blank line
        print('')


@command
def quit(mastodon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command
def info(mastodon, rest):
    """Prints your user info."""
    user = mastodon.account_verify_credentials()

    print("@" + str(user['username']))
    tprint(user['display_name'], 'cyan', 'red')
    print(user['url'])
    tprint(re.sub('<[^<]+?>', '', user['note']), 'red', 'green')


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


@click.command()
@click.option('--instance')
@click.option('--email')
@click.option('--password')
@click.option('--config', '-c', type=click.Path(exists=False, readable=True), default='~/.config/tootstream/tootstream.conf')
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

    say_error = lambda a, b: tprint("Invalid command. Use 'help' for a list of commands.", 'white', 'red')

    print("You are connected to ", end="")
    cprint(instance, 'green', attrs=['bold'])
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
