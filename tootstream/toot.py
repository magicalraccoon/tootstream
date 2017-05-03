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
from colored import fg, bg, attr, stylize


#Looks best with black background.
#TODO: Set color list in config file
COLORS = list(range(19,231))


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


def printUser(user):
    """Prints user data nicely with hardcoded colors."""
    print("@" + str(user['username']))
    cprint(user['display_name'], fg('cyan') + bg('red'))
    print(user['url'])
    cprint(re.sub('<[^<]+?>', '', user['note']), fg('red') + bg('green'))



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

@command
def fed(mastodon, rest):
    """Displays the Federated timeline."""
    for toot in reversed(mastodon.timeline_public()):
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
    """Displays the Public timeline."""
    for toot in reversed(mastodon.timeline_public()):
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


        # Shows boosted toots as well
        if toot['reblog']:
            username = "  Boosted @" + toot['reblog']['account']['acct'] +": "
            cprint(username, fg('blue'), end="")
            content = get_content(toot['reblog'])
        else:
            content = get_content(toot)

        print(content + "\n")


@command
def search(mastodon, rest):
    """Search for a #tag or @user."""
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
            cprint(display_name + username + " followed you!", fg('yellow') + bg('blue'))

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
    printUser(user)


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
    """Blocks a user by username or id."""
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


@command
def unblock(mastodon, rest):
    """Unblocks a user by username or id."""
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


@command
def follow(mastodon, rest):
    """Follows an account by username or id."""
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


@command
def unfollow(mastodon, rest):
    """Unfollows an account by username or id."""
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


@command
def mute(mastodon, rest):
    """Mutes a user by username or id."""
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


@command
def unmute(mastodon, rest):
    """Unmutes a user by username or id."""
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


@command
def accept(mastodon, rest):
    """Accepts a user's follow request by username or id."""
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


@command
def reject(mastodon, rest):
    """Rejects a user's follow request by username or id."""
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


@command
def followers(mastodon, rest):
    """Lists users who follow you."""
    user = mastodon.account_verify_credentials()
    users = mastodon.account_followers(user['id'])
    if not users:
        cprint("  You don't have any followers", fg('red'))
    else:
        cprint("  Your followers:", fg('magenta'))
        printUsersShort(users)


@command
def following(mastodon, rest):
    """Lists users you follow."""
    user = mastodon.account_verify_credentials()
    users = mastodon.account_following(user['id'])
    if not users:
        cprint("  You're safe!  There's nobody following you", fg('red'))
    else:
        cprint("  People following you:", fg('magenta'))
        printUsersShort(users)


@command
def blocks(mastodon, rest):
    """Lists users you have blocked."""
    users = mastodon.blocks()
    if not users:
        cprint("  You haven't blocked anyone (... yet)", fg('red'))
    else:
        cprint("  You have blocked:", fg('magenta'))
        printUsersShort(users)


@command
def mutes(mastodon, rest):
    """Lists users you have muted."""
    users = mastodon.mutes()
    if not users:
        cprint("  You haven't muted anyone (... yet)", fg('red'))
    else:
        cprint("  You have muted:", fg('magenta'))
        printUsersShort(users)


@command
def requests(mastodon, rest):
    """Lists your incoming follow requests."""
    users = mastodon.follow_requests()
    if not users:
        cprint("  You have no incoming requests", fg('red'))
    else:
        cprint("  These users want to follow you:", fg('magenta'))
        printUsersShort(users)
        cprint("  run 'accept <id>' to accept", fg('magenta'))
        cprint("   or 'reject <id>' to reject", fg('magenta'))


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
