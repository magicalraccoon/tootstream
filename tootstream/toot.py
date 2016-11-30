import os.path
import click
from mastodon import Mastodon

# TODO: need to modify this to support multiple shards, since we have to register per shard
# i think
APP_PATH = 'file.txt'

USER_REGEX = "[a-zA-Z0-9_]{1,30}"


def register_app():
    if os.path.isfile(APP_PATH):
        return
    Mastodon.create_app(
        'tootstream',
        to_file=APP_PATH
    )


def login(name, password, shard=None):
    """
    Login to Mastodon shard.
    Return a Mastodon client if login success, otherwise returns None.
    """
    mastodon = Mastodon(client_id=APP_PATH)
    mastodon.log_in(
        name,
        password,
        to_file = 'tootstream_usercred.txt'
    )
    return mastodon


@click.command()
@click.option('--name', prompt=True)
@click.option('--password', prompt=True, hide_input=True)
def main(name, password):
    register_app()
    mastodon = login(name, password)
    mastodon.toot()

if __name__ == '__main__':
    main()
