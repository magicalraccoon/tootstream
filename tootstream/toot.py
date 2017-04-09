import os.path
import click
import getpass
import sys
import re
import configparser
from html.parser import HTMLParser
from mastodon import Mastodon
from collections import OrderedDict


html_parser = HTMLParser()


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
    config['default'] = {'instance':instance,
                         'client_id':client_id,
                         'client_secret':client_secret,
                         'token':token}

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
        api_base_url = "https://" + instance
    )


def login(mastodon, instance, email, password):
    """
    Login to a Mastodon instance.
    Return a Mastodon client if login success, otherwise returns None.
    """

    return mastodon.log_in(email, password)


def tprint(toot):
    """Prints string with unescaped HTML characters"""
    print(html_parser.unescape(toot))

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
    print("Published: " + rest)


@command
def boost(mastodon, rest):
    """Boosts a toot by ID."""
    # TODO catch if boost is not a real ID
    mastodon.status_reblog(rest)
    boosted = mastodon.status(rest)
    tprint("  Boosted: " + re.sub('<[^<]+?>', '', boosted['content']))


@command
def unboost(mastodon, rest):
    """Removes a boosted tweet by ID."""
    # TODO catch if uboost is not a real ID
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    tprint("  Removed boost: " + re.sub('<[^<]+?>', '', unboosted['content']))


@command
def fav(mastodon, rest):
    """Favorites a toot by ID."""
    # TODO catch if fav is not a real ID
    mastodon.status_favourite(rest)
    faved = mastodon.status(rest)
    tprint("  Favorited: " + re.sub('<[^<]+?>', '', faved['content']))


@command
def unfav(mastodon, rest):
    """Removes a favorite toot by ID."""
    # TODO catch if ufav is not a real ID
    mastodon.status_unfavourite(rest)
    unfaved = mastodon.status(rest)
    tprint("  Removed favorite: " + re.sub('<[^<]+?>', '', unfaved['content']))


@command
def home(mastodon, rest):
    """Displays the Home timeline."""
    for toot in reversed(mastodon.timeline_home()):
        display_name = "  " + toot['account']['display_name']
        username = " @" + toot['account']['username'] + " "
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(toot['id'])

        # Prints individual toot/tooter info
        tprint(display_name + username + toot['created_at'])
        print(reblogs_count + favourites_count + toot_id)

        # shows boosted toots as well
        if toot['reblog']:
            username = "  Boosted @" + toot['reblog']['account']['username']
            display_name = toot['reblog']['account']['display_name'] + ": "
            clean = re.sub('<[^<]+?>', '', toot['reblog']['content'])
            content = username + display_name + clean

        # TODO: Toots with only HTML do not display (images, links)
        # TODO: Breaklines should be displayed correctly
        content = "  " + re.sub('<[^<]+?>', '', toot['content'])
        #content = toot['content']
        tprint(content + "\n")


@command
def public(mastodon, rest):
    """Displays the Public timeline."""
    for toot in reversed(mastodon.timeline_public()):
        display_name = "  " + toot['account']['display_name']
        username = " @" + toot['account']['username'] + " "
        reblogs_count = "  ♺:" + str(toot['reblogs_count'])
        favourites_count = " ♥:" + str(toot['favourites_count']) + " "
        toot_id = str(toot['id'])

        # Prints individual toot/tooter info
        tprint(display_name + username + toot['created_at'])
        tprint(reblogs_count + favourites_count + toot_id)


        # shows boosted toots as well
        if toot['reblog']:
            username = "  Boosted @" + toot['reblog']['account']['username']
            display_name = toot['reblog']['account']['display_name'] + ": "
            clean = re.sub('<[^<]+?>', '', toot['reblog']['content'])
            content = username + display_name + clean

        # TODO: Toots with only HTML do not display (images, links)
        # TODO: Breaklines should be displayed correctly
        content = "  " + re.sub('<[^<]+?>', '', toot['content'])
        tprint(content + "\n")

@command
def note(mastodon, rest):
    """Displays the Notifications timeline."""
    for note in reversed(mastodon.notifications()):
        display_name = "  " + note['account']['display_name']
        username = " @" + note['account']['username']


        # Mentions
        if note['type'] == 'mention':
            tprint(display_name + username)
            tprint("  " + re.sub('<[^<]+?>', '', note['status']['content']))

        # Favorites
        elif note['type'] == 'favourite':
            reblogs_count = "  " + "♺:" + str(note['status']['reblogs_count'])
            favourites_count = " ♥:" + str(note['status']['favourites_count'])
            time = " " + note['status']['created_at']
            content = "  " + re.sub('<[^<]+?>', '', note['status']['content'])
            tprint(display_name + username + " favorited your status:")
            tprint(reblogs_count + favourites_count + time + '\n' + content)

        # Boosts
        elif note['type'] == 'reblog':
            tprint(display_name + username + " boosted your status:")
            tprint("  " + re.sub('<[^<]+?>', '', note['status']['content']))

        # Follows
        elif note['type'] == 'follow':
            username = re.sub('<[^<]+?>', '', username)
            tprint(display_name + username + " followed you!")

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
    tprint(user['display_name'])
    print(user['url'])
    tprint(re.sub('<[^<]+?>', '', user['note']))


@command
def delete(mastodon, rest):
    """Deletes your toot by ID"""
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
    configpath = config
    config = parse_config(configpath)

    if (not 'default' in config):
        config['default'] = {}

    if (instance != None):
        # Nothing to do, just use value passed on the command line
        pass
    elif "instance" in config['default']:
        instance = config['default']['instance']
    else: instance = input("Which instance would you like to connect to? ")


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
                client_id = client_id,
                client_secret = client_secret,
                api_base_url = "https://" + instance)
        token = login(mastodon, instance, email, password)

    mastodon = Mastodon(
            client_id = client_id,
            client_secret = client_secret,
            access_token = token,
            api_base_url = "https://" + instance)

    save_config(configpath, instance, client_id, client_secret, token)

    say_error = lambda a, b: tprint("Invalid command. Use 'help' for a \
                                    list of commands.")

    print("You are connected to " + instance)
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
