import os.path
import click
import readline
import getpass
import sys
from mastodon import Mastodon

# TODO: need to modify this to support multiple shards, since we have to register per shard
# For now it only supports the default mastodon.social shard
APP_PATH = os.path.expanduser('~/.config/tootstream/client.txt')
APP_CRED = os.path.expanduser('~/.config/tootstream/token.txt')
# USER_REGEX = "[a-zA-Z0-9_]{1,30}"



def register_app():
    if not os.path.exists(os.path.expanduser('~/.config/tootstream')):
        os.makedirs(os.path.expanduser('~/.config/tootstream'))
    if os.path.isfile(APP_PATH):
        return
    Mastodon.create_app(
        'tootstream',
        to_file=APP_PATH
    )


def login(mastodon, email, password, shard=None):
    """
    Login to the mastodon.social shard.
    Return a Mastodon client if login success, otherwise returns None.
    """
    mastodon.log_in(
        email,
        password,
        to_file = APP_CRED
    )

commands = {}
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
def home(mastodon, rest):
    """Displays the Home timeline."""
    for status in reversed(mastodon.timeline_home()):
        print("@" + status['account']['username'])
        print(status)



@command
def note(mastodon, rest):
    """Displays the notifications timeline."""

    for note in reversed(mastodon.notifications()):
        print("@" + note['account']['username'] + " sent you a " + note['type'] + "!")


@command
def quit(mastonon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command
def user(mastodon, rest):
    """Prints your user info."""
    user = mastodon.account_verify_credentials()

    print("@" + str(user['username']))
    print(user['display_name'])
    print(user['url'])
    print(user['note'])


def authenticated(mastodon):
    if not os.path.isfile(APP_CRED):
        return False
    if mastodon.account_verify_credentials().get('error'):
        return False
    return True


@click.command()
@click.option('--email')
@click.option('--password')
def main(email, password):
    register_app()

    mastodon = Mastodon(client_id=APP_PATH, access_token=APP_CRED)

    if email and password:
        login(mastodon, email, password)
    elif not authenticated(mastodon):
        email = input("Email used to login: ")
        password = getpass.getpass()
        login(mastodon, email, password)

    say_error = lambda a, b: print("Invalid command. Use 'help' for a list of commands.")

    print("Welcome to tootstream!")
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
