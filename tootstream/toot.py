import os.path
from mastodon import Mastodon

APP_PATH = 'file.txt'

USER_REGEX = "[a-zA-Z0-9_]{1,30}"


def check_file():
    if os.path.isfile(APP_PATH):
        return
    Mastodon.create_app(
        'tootstream',
        to_file=APP_PATH
    )


def main():
    pass


if __name__ == '__main__':
    main()
