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
RESERVED = ( "theme" )
KEYCFGFILE = __name__ + 'cfgfile'
KEYPROFILE = __name__ + 'profile'
KEYPROMPT = __name__ + 'prompt'


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
cfg = configparser.ConfigParser()
global mastodon
toot_parser = TootParser(indent='  ')


def get_content(toot):
    html = toot['content']
    toot_parser.reset()
    toot_parser.feed(html)
    return toot_parser.get_text()


def set_configfile(filename):
    click.get_current_context().meta[KEYCFGFILE] = filename
    return


def get_configfile():
    return click.get_current_context().meta.get(KEYCFGFILE)


def set_prompt(prompt):
    click.get_current_context().meta[KEYPROMPT] = prompt
    return


def get_prompt():
    return click.get_current_context().meta.get(KEYPROMPT)


def set_active_profile(profile):
    click.get_current_context().meta[KEYPROFILE] = profile
    return


def get_active_profile():
    return click.get_current_context().meta.get(KEYPROFILE)


def get_profile_values(profile):
    # quick return of existing profile, watch out for exceptions
    p = cfg[profile]
    return p['instance'], p['client_id'], p['client_secret'], p['token']

def get_known_profiles():
    return list( set(cfg.sections()) - set(RESERVED) )

def parse_config():
    filename = get_configfile()
    (dirpath, basename) = os.path.split(filename)
    if not (dirpath == "" or os.path.exists(dirpath)):
        os.makedirs(dirpath)

    if not os.path.isfile(filename):
        print("...No configuration found, generating...")
        return

    try:
        cfg.read(filename)
    except configparser.Error:
        cprint("This does not look like a valid configuration:"+filename, 'red')
        sys.exit("Goodbye!")


def save_config():
    filename = get_configfile()
    (dirpath, basename) = os.path.split(filename)
    if not (dirpath == "" or os.path.exists(dirpath)):
        os.makedirs(dirpath)

    try:
        with open(filename, 'w') as configfile:
            cfg.write(configfile)
    except os.error:
        cprint("Unable to write configuration to "+filename, 'red')


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


def login(instance, email, password):
    """
    Login to a Mastodon instance.
    Return a Mastodon client if login success, otherwise returns None.
    """

    return mastodon.log_in(email, password)


def parse_or_input_profile(profile, instance=None, email=None, password=None):
    """
    Validate an existing profile or get user input to generate a new one.
    """
    global cfg
    # shortcut for preexisting profiles
    if cfg.has_section(profile):
        try:
            return get_profile_values(profile)
        except:
            pass
    else:
        cfg.add_section(profile)

    # no existing profile or it's incomplete
    if (instance != None):
        # Nothing to do, just use value passed on the command line
        pass
    elif "instance" in cfg[profile]:
        instance = cfg[profile]['instance']
    else:
        cprint("  Which instance would you like to connect to? eg: 'mastodon.social'", 'blue')
        instance = input("  Instance: ")


    client_id = None
    if "client_id" in cfg[profile]:
        client_id = cfg[profile]['client_id']

    client_secret = None
    if "client_secret" in cfg[profile]:
        client_secret = cfg[profile]['client_secret']

    if (client_id == None or client_secret == None):
        client_id, client_secret = register_app(instance)

    token = None
    if "token" in cfg[profile]:
        token = cfg[profile]['token']

    if (token == None or email != None or password != None):
        if (email == None):
            email = input("  Email used to login: ")
        if (password == None):
            password = getpass.getpass("  Password: ")

        global mastodon
        mastodon = Mastodon(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url="https://" + instance
        )
        token = login(instance, email, password)

    return instance, client_id, client_secret, token


def print_profiles():
    active = get_active_profile()
    inactiveprofiles = get_known_profiles()
    try:
        inactiveprofiles.remove(active)
    except ValueError:
        # somebody removed the active profile. don't panic.
        pass
    # TODO: wrap based on termwidth
    inactives = ' '.join(inactiveprofiles)
    cprint("  *"+active, 'red', end="")
    cprint("  "+inactives, 'blue')
    return


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
def help(rest):
    """List all commands."""
    print("Commands:")
    for command, cmd_func in commands.items():
        print("\t{}\t{}".format(command, cmd_func.__doc__))


@command
def toot(rest):
    """Publish a toot. ex: 'toot Hello World' will publish 'Hello World'."""
    global mastodon
    mastodon.toot(rest)
    cprint("You tooted: ", 'magenta', attrs=['bold'], end="")
    cprint(rest, 'magenta', 'on_white', attrs=['bold', 'underline'])


@command
def boost(rest):
    """Boosts a toot by ID."""
    global mastodon
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_reblog(rest)
    boosted = mastodon.status(rest)
    msg = "  Boosted: " + get_content(boosted)
    tprint(msg, 'green', 'red')


@command
def unboost(rest):
    """Removes a boosted tweet by ID."""
    global mastodon
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    msg = "  Removed boost: " + get_content(unboosted)
    tprint(msg, 'red', 'green')


@command
def fav(rest):
    """Favorites a toot by ID."""
    global mastodon
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_favourite(rest)
    faved = mastodon.status(rest)
    msg = "  Favorited: " + get_content(faved)
    tprint(msg, 'red', 'yellow')


@command
def rep(rest):
    """Reply to a toot by ID."""
    global mastodon
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
def unfav(rest):
    """Removes a favorite toot by ID."""
    global mastodon
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unfavourite(rest)
    unfaved = mastodon.status(rest)
    msg = "  Removed favorite: " + get_content(unfaved)
    tprint(msg, 'yellow', 'red')


@command
def home(rest):
    """Displays the Home timeline."""
    global mastodon
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
def public(rest):
    """Displays the Public timeline."""
    global mastodon
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
def note(rest):
    """Displays the Notifications timeline."""
    global mastodon
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
def quit(rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command
def info(rest):
    """Prints your user info."""
    global mastodon
    user = mastodon.account_verify_credentials()

    print("@" + str(user['username']))
    tprint(user['display_name'], 'cyan', 'red')
    print(user['url'])
    tprint(re.sub('<[^<]+?>', '', user['note']), 'red', 'green')


@command
def delete(rest):
    """Deletes your toot by ID"""
    global mastodon
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_delete(rest)
    print("Poof! It's gone.")


@command
def block(rest):
    """Blocks a user by username."""
    # TODO: Find out how to get global usernames
    global mastodon


@command
def unblock(rest):
    """Unblocks a user by username."""
    # TODO: Find out how to get global usernames
    global mastodon


@command
def follow(rest):
    """Follows an account by username."""
    # TODO: Find out how to get global usernames
    global mastodon


@command
def unfollow(rest):
    """Unfollows an account by username."""
    # TODO: Find out how to get global usernames
    global mastodon


@command
def profile(rest):
#def profile(mastodon, rest):
    """Profile operations: create, load, remove, list."""
    global mastodon
    global cfg
    command = rest.split(' ')
    usage = str("  usage: profile load [profilename]\n" +
                "         profile new [profilename [email [password]]]\n" +
                "         profile del [profilename]\n" +
                "         profile list")

    def profile_error(error):
        cprint("  "+error, 'red')
        return

    try:
        profile = command[1]
    except IndexError:
        profile = ""

    # load subcommand
    if command[0] in ["load"]:
        if profile == "":
            profile = input("  Profile name: ")

        if profile in get_known_profiles():
            # shortcut for preexisting profiles
            try:
                instance, client_id, client_secret, token = get_profile_values(profile)
            except:
                return profile_error("Invalid or corrupt profile")

            try:
                newmasto = Mastodon(
                    client_id=client_id,
                    client_secret=client_secret,
                    access_token=token,
                    api_base_url="https://" + instance)
            except:
                return profile_error("Mastodon error")

            # update stuff
            user = newmasto.account_verify_credentials()
            set_prompt("[@" + str(user['username']) + " (" + profile + ")]: ")
            set_active_profile(profile)
            mastodon = newmasto
            cprint("  Profile " + profile + " loaded", 'green')
            return
        else:
            profile_error("Profile " + profile + " doesn't seem to exist")
            print_profiles()
            return
    # end load

    # new/create subcommand
    elif command[0] in ["new", "add", "create"]:
        if profile == "":
            profile = input("  Profile name: ")

        if profile in RESERVED:
            return profile_error("Illegal profile name: " + profile)
        elif profile in get_known_profiles():
            return profile_error("Profile " + profile + " exists")

        instance, client_id, client_secret, token = parse_or_input_profile(profile)
        try:
            newmasto = Mastodon(
                client_id=client_id,
                client_secret=client_secret,
                access_token=token,
                api_base_url="https://" + instance)
        except:
            return profile_error("Mastodon error")

        # update stuff
        cfg[profile] = {
            'instance': instance,
            'client_id': client_id,
            'client_secret': client_secret,
            'token': token
        }
        user = newmasto.account_verify_credentials()
        set_prompt("[@" + str(user['username']) + " (" + profile + ")]: ")
        set_active_profile(profile)
        mastodon = newmasto
        cprint("  Profile " + profile + " loaded", 'green')
        return
    # end new/create

    # delete subcommand
    elif command[0] in ["delete", "del", "rm", "remove"]:
        if profile in [RESERVED, "default"]:
            return profile_error("Illegal profile name: " + profile)
        elif profile == "":
            profile = input("  Profile name: ")

        cfg.remove_section(profile)
        save_config()
        cprint("  Poof! It's gone.", 'blue')
        if profile == get_active_profile():
            set_active_profile("")
        return
    # end delete

    # list subcommand
    elif command[0] in ["ls", "list"]:
        print_profiles()
        return
    # end list

    # no subcommand; print usage
    cprint(usage, 'red')
    return


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
@click.option( '--profile', '-P', metavar='<string>', default='default',
               help='Name of profile for saved credentials (default)' )
def main(instance, email, password, config, profile):
    configpath = os.path.expanduser(config)
    if os.path.isfile(configpath) and not os.access(configpath, os.W_OK):
        # warn the user before they're asked for input
        cprint("Config file does not appear to be writable: "+configpath, 'red')

    set_configfile(configpath)
    parse_config()
    if not cfg.has_section(profile):
        cfg.add_section(profile)

    instance, client_id, client_secret, token = parse_or_input_profile(profile, instance, email, password)


    global mastodon
    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        access_token=token,
        api_base_url="https://" + instance)

    cfg[profile] = {
        'instance': instance,
        'client_id': client_id,
        'client_secret': client_secret,
        'token': token
    }

    set_active_profile(profile)
    save_config()


    say_error = lambda a: tprint("Invalid command. Use 'help' for a list of commands.", 'white', 'red')

    cprint("Welcome to tootstream! Two-Factor-Authentication is currently not supported.", 'blue')
    print("You are connected to ", end="")
    cprint(instance, 'green', attrs=['bold'])
    print("Enter a command. Use 'help' for a list of commands.")
    print("\n")

    user = mastodon.account_verify_credentials()
    set_prompt("[@" + str(user['username']) + " (" + profile + ")]: ")

    while True:
        command = input(get_prompt()).split(' ', 1)
        rest = ""
        try:
            rest = command[1]
        except IndexError:
            pass
        command = command[0]
        cmd_func = commands.get(command, say_error)
        cmd_func(rest)


if __name__ == '__main__':
    main()
