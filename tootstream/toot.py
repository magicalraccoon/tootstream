import os.path
import click
import readline
import getpass
from mastodon import Mastodon

# TODO: need to modify this to support multiple shards, since we have to register per shard
# For now it only supports the default mastodon.social shard
APP_PATH = os.path.expanduser('~/.config/tootstream/client.txt')
APP_CRED = os.path.expanduser('~/.config/tootstream/token.txt')
USER_REGEX = "[a-zA-Z0-9_]{1,30}"


def register_app():
    if not os.path.exists(os.path.expanduser('~/.config/tootstream')):
        os.makedirs(os.path.expanduser('~/.config/tootstream'))
    if os.path.isfile(APP_PATH):
        return
    Mastodon.create_app(
        'tootstream',
        to_file=APP_PATH
    )


def login(mastodon, name, password, shard=None):
    """
    Login to Mastodon shard.
    Return a Mastodon client if login success, otherwise returns None.
    """
    mastodon.log_in(
        name,
        password,
        to_file = APP_CRED
    )

commands = {}
def command(func):
    commands[func.__name__] = func
    return func

@command
def toot(mastodon, rest):
    """Publish a toot. eg 'toot hello world' will publish 'hello world'"""
    mastodon.toot(rest)

@command
def help(mastodon, rest):
    """List all commands."""
    print("Commands:")
    for command, cmd_func in commands.items():
        print("\t{}\t{}".format(command, cmd_func.__doc__))

def authenticated(mastodon):
    if not os.path.isfile(APP_CRED):
        return False
    if mastodon.account_verify_credentials().get('error'):
        return False
    return True

@click.command()
@click.option('--name')
@click.option('--password')
def main(name, password):
    register_app()

    mastodon = Mastodon(client_id=APP_PATH, access_token=APP_CRED)

    if name and password:
        login(mastodon, name, password)
    elif not authenticated(mastodon):
        name = input("Name: ")
        password = getpass.getpass()
        login(mastodon, name, password)

    say_error = lambda a, b: print("Invalid command. Use 'help' for a list of commands")

    print("Welcome to Tootstream")
    print("Enter a command. Use 'help' for a list of commands")
    while True:
        command = input("> ").split(' ', 1)
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
