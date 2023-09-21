import sys
import datetime
import os.path
import re
import configparser
import random
import readline
import bisect
import shutil
from collections import OrderedDict
import webbrowser
import dateutil

# Get the version of Tootstream
import pkg_resources  # part of setuptools
import click
from tootstream.toot_parser import TootParser
from mastodon import Mastodon, StreamListener
from colored import fg, bg, attr, stylize
import humanize
import emoji
import pytimeparse


version = pkg_resources.require("tootstream")[0].version

# placeholder variable for converting emoji to shortcodes until we get it in config
convert_emoji_to_shortcode = False

# placeholder variable for showing media links until we get it in config
show_media_links = True

# Flag for whether we're streaming or not
is_streaming = False

# Looks best with black background.
# TODO: Set color list in config file
COLORS = list(range(19, 231))
GLYPHS = {
    # general icons, keys don't match any Mastodon dict keys
    "fave": "\U00002665",  # Black Heart Suit
    "boost": "\U0000267a",  # Recycling Symbol for generic materials
    "mentions": "\U0000270e",  # Lower Right Pencil
    "toots": "\U0001f4ea",  # mailbox (for toot counts)
    # next key matches key in user dict
    # lock (masto web uses U+F023 from FontAwesome)
    "locked": "\U0001f512",
    # next 2 keys match keys in toot dict indicating user has already faved/boosted
    "favourited": "\U00002605",  # star '\U0001f31f' '\U00002b50' '\U00002605'
    "reblogged": "\U0001f1e7",  # reginal-B '\U0001f1e7' (or reuse ♺?)
    # next 4 keys match possible values for toot['visibility']
    "public": "\U0001f30e",  # globe
    "unlisted": "\U0001f47b",  # ghost '\U0001f47b' ... mute '\U0001f507' ??
    "private": "\U0001f512",  # lock
    # envelopes: '\U0001f4e7' '\U0001f4e9' '\U0001f48c' '\U00002709'
    "direct": "\U0001f4e7",
    # next 5 keys match keys in relationship{}
    "followed_by": "\U0001f43e",  # pawprints '\U0001f43e'
    "following": "\U0001f463",  # footprints '\U0001f463'
    # thumbsdown '\U0001f44e', big X '\U0000274c', stopsign '\U0001f6d1'
    "blocking": "\U0000274c",
    # mute-spkr '\U0001f507', mute-bell '\U0001f515', prohibited '\U0001f6ab'
    "muting": "\U0001f6ab",
    "requested": "\U00002753",  # hourglass '\U0000231b', question '\U00002753'
    "voted": "\U00002714",  # Checkmark
    # catchall
    "unknown": "\U0001f34d",
}

# reserved config sections (disallowed as profile names)
RESERVED = ("theme", "global")


class AlreadyPrintedException(Exception):
    """An exception that has already been shown to the user, so doesn't need to be printed again."""

    pass


class IdDict:
    """Represents a mapping of local (tootstream) ID's to global
    (mastodon) IDs."""

    def __init__(self):
        self._map = []

    def to_local(self, global_id):
        """Returns the local ID for a global ID"""
        try:
            return self._map.index(global_id)
        except ValueError:
            self._map.append(global_id)
            return len(self._map) - 1

    def to_global(self, local_id):
        """Returns the global ID for a local ID, or None if ID is invalid.
        Also prints an error message"""
        try:
            local_id = int(local_id)
            return self._map[local_id]
        except Exception:
            cprint("Invalid ID.", fg("red"))
            return None


def redisplay_prompt():
    print(readline.get_line_buffer(), end="", flush=True)
    readline.redisplay()


class TootListener(StreamListener):
    def on_update(self, status):
        print()
        printToot(status)
        print()
        redisplay_prompt()


IDS = IdDict()

LAST_PAGE = None
LAST_CONTEXT = None

# Get the current width of the terminal
terminal_size = shutil.get_terminal_size((80, 20))
toot_parser = TootParser(
    indent="  ",
    width=int(terminal_size.columns) - 2,
    convert_emoji_to_unicode=False,
    convert_emoji_to_shortcode=convert_emoji_to_shortcode,
)

toot_listener = TootListener()


#####################################
######## UTILITY FUNCTIONS   ########
#####################################


def find_original_toot_id(toot):
    """ Locates the original toot ID in case of a reblog"""
    reblog = toot.get("reblog")
    if reblog:
        original_toot = reblog
    else:
        original_toot = toot
    original_toot_id = original_toot.get("id")
    return IDS.to_local(original_toot_id)


def rest_to_list(rest):
    rest = ",".join(rest.split())
    rest = rest.replace(",,", ",")
    rest = [x.strip() for x in rest.split(",")]
    return rest


def rest_limit(rest):
    rest_list = rest_to_list(rest)
    limit = None
    if len(rest_list) > 1:
        rest = rest_list.pop(0)
        limit = rest_list.pop()
    else:
        rest = rest_list[0]
    return limit, rest


def update_prompt(username, context, profile):
    if context:
        prompt = f"[@{username} <{context}> ({profile})]: "
    else:
        prompt = f"[@{username} ({profile})]: "
    return prompt


def list_support(mastodon, silent=False):
    lists_available = mastodon.verify_minimum_version("2.1.0")
    if lists_available is False and silent is False:
        cprint("List support is not available with this version of Mastodon", fg("red"))
    return lists_available


def step_flag(rest):
    if "step" in rest:
        return True, rest.replace(" step", "")
    return False, rest


def limit_flag(rest):
    if rest.isdigit():
        return int(rest), rest
    return None, rest


def get_content(toot):
    html = toot.get("content")
    if html is None:
        return ""
    toot_parser.parse(html)
    return toot_parser.get_text()


def get_media_attachments(toot):
    out = []
    nsfw = "CW " if toot.get("sensitive") else ""
    out.append(
        stylize(
            "  " + nsfw + "media: " + str(len(toot.get("media_attachments"))),
            fg("magenta"),
        )
    )
    if show_media_links:
        for media in toot.get("media_attachments"):
            description = media.get("description")
            if description:
                toot_parser.reset()
                toot_parser.handle_data(" " + nsfw + " " + description)
                out.append(stylize(toot_parser.get_text(), fg("white")))
            out.append(stylize("   " + nsfw + " " + media.url, fg("green")))
    return out


def get_poll(toot):
    poll = getattr(toot, "poll", None)
    if poll:
        poll_results = ""
        total_votes_count = poll.get("votes_count")
        poll_options = poll.get("options")
        own_votes = poll.get("own_votes")
        for i, poll_element in enumerate(poll_options):
            selected = " "
            poll_title = poll_element.get("title")
            poll_votes_count = poll_element.get("votes_count")
            if total_votes_count > 0:
                poll_percentage = (poll_votes_count / total_votes_count) * 100
            else:
                poll_percentage = 0
            if i in own_votes:
                selected = GLYPHS.get("voted")
            poll_results += f"{selected} {i}: {poll_title} ({poll_votes_count}: {poll_percentage:.2f}%)\n"
        poll_results += f"  Total votes: {total_votes_count}"
        if poll.multiple:
            poll_results += f"\n  (Multiple votes may be cast.)"
        if poll.expired:
            poll_results += f"\n  Polling is over."
        uri = toot["uri"]
        return f"  [poll] {poll['id']} ({uri})\n{poll_results}"


def get_unique_userid(mastodon, rest, exact=True):
    """Get a unique user ID by limiting the search to the top result.
    params:
        rest: rest of the command
        exact: whether to do an exact search or not.
            Most commands should require precision, so

    """
    # Check if the ID is already in numeric form
    try:
        userid = int(rest)
        return userid
    except ValueError:
        pass

    user_list = mastodon.account_search(rest, limit=1)
    if not user_list:
        raise Exception(f"  username '{rest}' not found")
        return
    user = user_list.pop()
    if exact:
        username_check = rest.lstrip("@").strip()
        username_acct = user.get("acct").lstrip("@").strip()
        if username_check != username_acct:
            if "@" not in username_check:
                raise ValueError("  Please use a more exact username for this command.")
            else:
                raise Exception(f"  {username_check} not found.")
    userid = user.get("id")
    return userid


def get_list_id(mastodon, rest):
    """Get the ID for a list"""
    if not rest or not rest.strip():
        raise Exception("List argument missing.")

    # maybe it's already an int
    try:
        return int(rest)
    except ValueError:
        pass

    lists = mastodon.lists()
    desired_title = rest.strip().lower()
    for item in lists:
        if item["title"].lower() == desired_title:
            return item["id"]

    raise Exception("List '{}' is not found.".format(rest))


def flaghandler(rest, initial, flags):
    """Parse input for flags."""

    # initialize kwargs to default values
    kwargs = {k: initial for k in flags.values()}

    # token-grabbing loop
    # recognize separated (e.g. `-m -f`) as well as combined (`-mf`)
    while rest.startswith("-"):
        # get the next token
        (args, _, rest) = rest.partition(" ")
        # traditional unix "ignore flags after this" syntax
        if args == "--":
            break
        for k in flags.keys():
            if k in args:
                kwargs[flags[k]] = not kwargs[flags[k]]

    return (rest, kwargs)


def flaghandler_note(mastodon, rest):
    return flaghandler(
        rest,
        True,
        {
            "m": "mention",
            "f": "favourite",
            "b": "reblog",
            "F": "follow",
            "r": "follow_request",
            "p": "poll",
            "u": "update",
        },
    )


def flaghandler_tootreply(mastodon, rest):
    """Parse input for flags and prompt user.  On success, returns
    a tuple of the input string (minus flags) and a dict of keyword
    arguments for Mastodon.status_post().  On failure, returns
    (None, None)."""

    (rest, flags) = flaghandler(
        rest, False, {"v": "visibility", "c": "cw", "C": "noCW", "m": "media"}
    )

    # if any flag is true, print a general usage message
    if True in flags.values():
        print("Press Ctrl-C to abort and return to the main prompt.")

    # initialize kwargs to default values
    kwargs = {
        "sensitive": False,
        "media_ids": None,
        "spoiler_text": None,
        "visibility": "",
    }

    # visibility flag
    if flags["visibility"]:
        vis = input("Set visibility [(p)ublic/(u)nlisted/(pr)ivate/(d)irect/None]: ")
        vis = vis.lower()

        # default case; pass on through
        if vis == "" or vis.startswith("n"):
            pass
        # other cases: allow abbreviations
        elif vis.startswith("d"):
            kwargs["visibility"] = "direct"
        elif vis.startswith("u"):
            kwargs["visibility"] = "unlisted"
        elif vis.startswith("pr"):
            kwargs["visibility"] = "private"
        elif vis.startswith("p"):
            kwargs["visibility"] = "public"
        # unrecognized: abort
        else:
            cprint(
                "error: only 'public', 'unlisted', 'private', 'direct' are allowed",
                fg("red"),
            )
            return (None, None)
    # end vis

    # cw/spoiler flag
    if flags["noCW"] and flags["cw"]:
        cprint("error: only one of -C and -c allowed", fg("red"))
        return (None, None)
    elif flags["noCW"]:
        # unset
        kwargs["spoiler_text"] = ""
    elif flags["cw"]:
        # prompt to set
        cw = input("Set content warning [leave blank for none]: ")

        # don't set if empty
        if cw:
            kwargs["spoiler_text"] = cw
    # end cw

    # media flag
    media = []
    if flags["media"]:
        print("You can attach up to 4 files. A blank line will end filename input.")
        count = 0
        while count < 4:
            fname = input("add file {}: ".format(count + 1))

            # break on empty line
            if not fname:
                break

            # expand paths and check file access
            fname = os.path.expanduser(fname).strip()
            if os.path.isfile(fname) and os.access(fname, os.R_OK):
                media.append(fname)
                count += 1
            else:
                raise Exception(f"error: cannot find file {fname}")

        # upload, verify
        if count:
            print("Attaching files:")
            c = 1
            kwargs["media_ids"] = []
            for m in media:
                try:
                    kwargs["media_ids"].append(mastodon.media_post(m))
                except Exception as e:
                    cprint(
                        "{}: API error uploading file {}".format(type(e).__name__, m),
                        fg("red"),
                    )
                    return (None, None)
                print("    {}: {}".format(c, m))
                c += 1

            # prompt for sensitivity
            nsfw = input("Mark sensitive media [y/N]: ")
            nsfw = nsfw.lower()
            if nsfw.startswith("y"):
                kwargs["sensitive"] = True
    # end media

    return (rest, kwargs)


def print_toots(
    mastodon,
    listing,
    stepper=False,
    limit=None,
    ctx_name=None,
    add_completion=True,
    show_toot=False,
    sort_toots=True,
):
    """Print toot listings and allow context dependent commands.

    If `stepper` is True it lets user step through listings with
    enter key. Entering [q] aborts stepping.

    Commands that require a toot id or username are partially applied based on
    context (current toot in listing) so that only the remaining (if any)
    parameters are necessary.

    Args:
        mastodon: Mastodon instance
        listing: Iterable containing toots
        ctx_name (str, optional): Displayed in command prompt
        add_completion (bool, optional): Add toots to completion list
        show:toot (bool, optional): whether to show the toot by default or not

    Examples:
        >>> print_toots(mastodon, mastodon.timeline_home(), ctx_name='home')

    sort_toots is used to apply reversed (chronological) sort to the list of toots.
        Default is true; threading needs this to be false.
    """
    if listing is None:
        cprint("No toots in current context.", fg("white") + bg("red"))
        return
    user = mastodon.account_verify_credentials()
    ctx = "" if ctx_name is None else " in {}".format(ctx_name)

    def say_error(*args, **kwargs):
        cprint(
            "Invalid command. Use 'help' for a list of commands. Press [enter] for next toot, [q] to abort.",
            fg("white") + bg("red"),
        )

    if sort_toots:
        toot_list = enumerate(reversed(listing))
    else:
        toot_list = enumerate(listing)

    for pos, toot in toot_list:
        printToot(toot, show_toot)
        if add_completion is True:
            completion_add(toot)

        if stepper:
            username = user.get("username")
            prompt = f"[@{username} {pos+1}/{len(listing)}{ctx}]: "
            command = None
            while command not in ["", "q"]:
                command = input(prompt).split(" ", 1)

                try:
                    rest = command[1]
                except IndexError:
                    rest = ""
                command = command[0]
                if command not in ["", "q"]:
                    cmd_func = commands.get(command, say_error)
                    if (
                        hasattr(cmd_func, "__argstr__")
                        and cmd_func.__argstr__ is not None
                    ):
                        if cmd_func.__argstr__.startswith("<id>"):
                            rest = str(find_original_toot_id(toot)) + " " + rest
                        if cmd_func.__argstr__.startswith("<user>"):
                            rest = "@" + toot["account"]["username"] + " " + rest
                    cmd_func(mastodon, rest)

            if command == "q":
                break


def toot_visibility(mastodon, flag_visibility=None, parent_visibility=None):
    """Return the visibility of a toot.
    We use the following precedence for flagging the privacy of a toot:
    flags > parent (if not public) > account settings
    """

    default_visibility = mastodon.account_verify_credentials()["source"]["privacy"]
    if flag_visibility:
        return flag_visibility

    if parent_visibility and parent_visibility != "public":
        return parent_visibility

    return default_visibility


#####################################
########     COMPLETION      ########
#####################################

completion_list = []


def complete(text, state):
    """Return the state-th potential completion for the name-fragment, text"""
    options = [name for name in completion_list if name.startswith(text)]
    if state < len(options):
        return options[state] + " "
    else:
        return None


def completion_add(toot):
    """Add usernames (original author, mentions, booster) co completion_list"""
    if toot["reblog"]:
        username = "@" + toot["reblog"]["account"]["acct"]
        if username not in completion_list:
            bisect.insort(completion_list, username)
    username = "@" + toot["account"]["acct"]
    if username not in completion_list:
        bisect.insort(completion_list, username)
    for user in ["@" + user["acct"] for user in toot["mentions"]]:
        if user not in completion_list:
            bisect.insort(completion_list, username)


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
        cprint("...No configuration found, generating...", fg("cyan"))
        config = configparser.ConfigParser()
        return config

    config = configparser.ConfigParser()
    try:
        config.read(filename)
    except configparser.Error:
        cprint(
            "This does not look like a valid configuration: {}".format(filename),
            fg("red"),
        )
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
            os.open(filename, flags=os.O_CREAT | os.O_APPEND, mode=0o600)
        except Exception as e:
            cprint("Unable to create file {}: {}".format(filename, e), fg("red"))

    try:
        with open(filename, "w") as configfile:
            config.write(configfile)
    except os.error:
        cprint("Unable to write configuration to {}".format(filename), fg("red"))
    return


def register_app(instance):
    """
    Registers this client with a Mastodon instance.

    Returns valid credentials if success, likely
    raises a Mastodon exception otherwise.
    """
    return Mastodon.create_app(
        "tootstream",
        scopes=["read", "write", "follow"],
        api_base_url="https://" + instance,
    )


def login(instance, client_id, client_secret):
    """
    Login to a Mastodon instance.

    Returns a valid Mastodon token if success, likely
    raises a Mastodon exception otherwise.
    """

    # temporary object to aquire the token
    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        api_base_url="https://" + instance,
    )

    print("Click the link to authorize login.")
    print(mastodon.auth_request_url(scopes=["read", "write", "follow"]))
    print()
    code = input("Enter the code you received >")

    return mastodon.log_in(code=code, scopes=["read", "write", "follow"])


def get_or_input_profile(config, profile, instance=None):
    """
    Validate an existing profile or get user input
    to generate a new one.  If the user is not logged in,
    the user will be prompted 3 times before giving up.

    On success, returns valid credentials: instance,
    client_id, client_secret, token.
    On failure, returns None, None, None, None.
    """
    # shortcut for preexisting profiles
    if config.has_section(profile):
        try:
            return (
                config[profile]["instance"],
                config[profile]["client_id"],
                config[profile]["client_secret"],
                config[profile]["token"],
            )
        except Exception:
            pass
    else:
        config.add_section(profile)

    # no existing profile or it's incomplete
    if instance is not None:
        # Nothing to do, just use value passed on the command line
        pass
    elif "instance" in config[profile]:
        instance = config[profile]["instance"]
    else:
        cprint(
            "  Which instance would you like to connect to? eg: 'mastodon.social'",
            fg("blue"),
        )
        instance = input("  Instance: ")

    client_id = None
    if "client_id" in config[profile]:
        client_id = config[profile]["client_id"]

    client_secret = None
    if "client_secret" in config[profile]:
        client_secret = config[profile]["client_secret"]

    if client_id is None or client_secret == None:
        try:
            client_id, client_secret = register_app(instance)
        except Exception as e:
            cprint("{}: please try again later".format(type(e).__name__), fg("red"))
            return None, None, None, None

    token = None
    if "token" in config[profile]:
        token = config[profile]["token"]

    if token is None:
        for i in [1, 2, 3]:
            try:
                token = login(instance, client_id, client_secret)
            except Exception as e:
                cprint(
                    "Error authorizing app. Did you enter the code correctly?",
                    fg("red"),
                )
            if token:
                break

        if not token:
            cprint("Giving up after 3 failed login attempts", fg("red"))
            return None, None, None, None

    return instance, client_id, client_secret, token


#####################################
######## OUTPUT FUNCTIONS    ########
#####################################
def cprint(text, style, end="\n"):
    print(stylize(text, style), end=end)


def format_username(user):
    """Get a user's account name including lock indicator."""
    return "".join(
        ("@", user["acct"], (" {}".format(GLYPHS["locked"]) if user["locked"] else ""))
    )


def format_user_counts(user):
    """Get a user's toot/following/follower counts."""
    countfmt = "{} :{}"
    return " ".join(
        (
            countfmt.format(GLYPHS["toots"], user["statuses_count"]),
            countfmt.format(GLYPHS["following"], user["following_count"]),
            countfmt.format(GLYPHS["followed_by"], user["followers_count"]),
        )
    )


def format_display_name(name):
    if convert_emoji_to_shortcode:
        name = emoji.demojize(name)
        return name
    return name


def printUser(user):
    """Prints user data nicely with hardcoded colors."""
    counts = stylize(format_user_counts(user), fg("blue"))

    print(format_username(user) + " " + counts)
    display_name = format_display_name(user["display_name"])
    cprint(display_name, fg("cyan"))
    print(user["url"])
    cprint(re.sub("<[^<]+?>", "", user["note"]), fg("red"))


def printUsersShort(users):
    for user in users:
        if not user:
            continue
        userid = "(id:" + str(user["id"]) + ")"
        display_name = format_display_name(user["display_name"])
        userdisp = "'" + str(display_name) + "'"
        userurl = str(user["url"])
        cprint("  " + format_username(user), fg("green"), end=" ")
        cprint(" " + userid, fg("red"), end=" ")
        cprint(" " + userdisp, fg("cyan"))
        cprint("      " + userurl, fg("blue"))


def format_time(time_event):
    """Return a formatted time and humanized time for a time event"""
    try:
        if not isinstance(time_event, datetime.datetime):
            time_event = dateutil.parser.parse(time_event)
        tz_info = time_event.tzinfo
        time_diff = datetime.datetime.now(tz_info) - time_event
        humanize_format = humanize.naturaltime(time_diff)
        time_format = datetime.datetime.strftime(time_event, "%F %X")
        return time_format + " (" + humanize_format + ")"
    except AttributeError:
        return "(Time format error)"


def format_toot_nameline(toot, dnamestyle):
    """Get the display, usernames and timestamp for a typical toot printout.

    dnamestyle: a fg/bg/attr set applied to the display name with stylize()"""
    # name line: display name, user@instance, lock if locked, timestamp
    if not toot:
        return ""
    formatted_time = format_time(toot["created_at"])

    display_name = format_display_name(toot["account"]["display_name"])
    out = [
        stylize(display_name, dnamestyle),
        stylize(format_username(toot["account"]), fg("green")),
        stylize(formatted_time, attr("dim")),
    ]
    return " ".join(out)


def format_toot_idline(toot):
    """Get boost/faves counts, toot ID, visibility, and
    already-faved/boosted indicators for a typical toot printout."""
    # id-and-counts line: boosted count, faved count, tootid, visibility, favourited-already, boosted-already
    if not toot:
        return ""
    reblogs_count = toot.get("reblogs_count", 0)
    favourites_count = toot.get("favourites_count", 0)
    visibility = toot.get("visibility")
    out = []
    out.append(stylize(GLYPHS["boost"] + ":" + str(reblogs_count), fg("cyan")))
    out.append(stylize(GLYPHS["fave"] + ":" + str(favourites_count), fg("yellow")))
    out.append(stylize("id:" + str(IDS.to_local(toot.get("id"))), fg("white")))
    if visibility:
        out.append(stylize("vis:" + GLYPHS[visibility], fg("blue")))

    # app used to post. frequently empty
    if toot.get("application") and toot.get("application").get("name"):
        out.append(
            "".join(
                (
                    stylize("via ", fg("white")),
                    stylize(toot["application"]["name"], fg("blue")),
                )
            )
        )
    # some toots lack these next keys, use get() to avoid KeyErrors
    if toot.get("favourited"):
        out.append(stylize(GLYPHS["favourited"], fg("magenta")))
    if toot.get("reblogged"):
        out.append(stylize(GLYPHS["reblogged"], fg("magenta")))

    return " ".join(out)


def printToot(toot, show_toot=False, dim=False):
    if not toot:
        return

    show_toot_text = True
    out = []
    # if it's a boost, only output header line from toot
    # then get other data from toot['reblog']
    if toot.get("reblog"):
        header = stylize("  Boosted by ", fg("yellow"))
        display_name = format_display_name(toot["account"]["display_name"])
        name = " ".join((display_name, format_username(toot["account"]) + ":"))
        out.append(header + stylize(name, fg("blue")))
        toot = toot["reblog"]

    # get the first two lines
    random.seed(toot["account"]["display_name"])
    out += [
        "  " + format_toot_nameline(toot, fg(random.choice(COLORS))),
        "  " + format_toot_idline(toot),
    ]

    if toot.get("spoiler_text", "") != "":
        # pass CW through get_content for wrapping/indenting
        faketoot = {"content": "[CW: " + toot["spoiler_text"] + "]"}
        out.append(stylize(get_content(faketoot), fg("red")))
        show_toot_text = False

    if toot.get("filtered"):
        filter_titles = ", ".join([x["filter"]["title"] for x in toot.filtered])
        faketoot = {"content": "[Filter: " + filter_titles + "]"}
        out.append(stylize(get_content(faketoot), fg("red")))
        show_toot_text = False

    if show_toot_text or show_toot:
        out.append(get_content(toot))

    if toot.get("status"):
        out.append(get_content(toot.get("status")))
        if toot.get("status").get("media_attachments"):
            out.append("\n".join(get_media_attachments(toot.get("status"))))

    if toot.get("media_attachments") and (show_toot_text or show_toot):
        # simple version: output # of attachments. TODO: urls instead?
        out.append("\n".join(get_media_attachments(toot)))

    if toot.get("poll"):
        out.append(get_poll(toot))

    if dim:
        cprint("\n".join(out), attr("dim"))
    else:
        print("\n".join(out))
    print()


def edittoot(text):
    global is_streaming
    if is_streaming:
        cprint(
            "Using the editor while streaming is unsupported at this time.", fg("red")
        )
        return ""
    edited_message = click.edit(text)
    if edited_message:
        return edited_message
    return ""


def printList(list_item):
    """Prints list entry nicely with hardcoded colors."""
    cprint(list_item["title"], fg("cyan"), end=" ")
    cprint("(id: %s)" % list_item["id"], fg("red"))


def printFilter(filter_item):
    """Prints filter entry nicely with hardcoded colors."""
    cprint(filter_item["phrase"], fg("cyan"), end=" ")
    cprint("(id: %s," % filter_item["id"], fg("red"), end=" ")
    cprint("context: %s, " % filter_item["context"], fg("red"), end=" ")
    cprint("expires_at: %s, " % filter_item["expires_at"], fg("red"), end=" ")
    cprint("whole_word: %s)" % filter_item["whole_word"], fg("red"))


#####################################
######## DECORATORS          ########
#####################################
commands = OrderedDict()


def command(argstr=None, section=None):
    """Adds the function to the command list."""

    def inner(func):
        commands[func.__name__] = func
        bisect.insort(completion_list, func.__name__)
        func.__argstr__ = argstr
        func.__section__ = section
        return func

    return inner


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


@command("[<cmd>]", "Help")
def help(mastodon, rest):
    """List all commands or show detailed help.

    ex: 'help' shows list of help commands.
        'help toot' shows additional information about the 'toot' command.
        'help discover' shows additional information about the 'discover' section of commands."""

    # Fill out the available sections
    sections = {}
    for cmd, cmd_func in commands.items():
        sections[cmd_func.__section__.lower()] = 1

    section_filter = ""

    # argument case
    if rest and rest != "":

        args = rest.split()
        if args[0] in commands.keys():
            # Show Command Help
            try:
                cmd_func = commands[args[0]]
            except Exception:
                print(__friendly_cmd_error__.format(rest))
                return

            try:
                cmd_args = cmd_func.__argstr__
            except Exception:
                cmd_args = ""
            # print a friendly header and the detailed help
            print(
                __friendly_help_header__.format(
                    cmd_func.__name__, cmd_args, cmd_func.__doc__
                )
            )
            return

        if args[0].lower() in sections.keys():
            # Set the section filter for the full command section
            section_filter = args[0].lower()
        else:
            # Command not found. Exit.
            print(__friendly_cmd_error__.format(rest))
            return

    # Show full list (with section filtering if appropriate)
    section = ""
    new_section = False

    for command, cmd_func in commands.items():
        # get only the docstring's first line for the column view
        (cmd_doc, *_) = cmd_func.__doc__.partition("\n")
        try:
            cmd_args = cmd_func.__argstr__
        except Exception:
            cmd_args = ""

        if cmd_func.__section__ != section:
            section = cmd_func.__section__
            new_section = True

        if section_filter == "" or section_filter == section.lower():
            if new_section:
                cprint(
                    "{section}:".format(section=section),
                    fg("white") + attr("bold") + attr("underline"),
                )
                new_section = False

            print("{:>14} {:<15}  {:<}".format(command, cmd_args, cmd_doc))


@command("[<text>]", "Toots")
def toot(mastodon, rest):
    """Publish a toot.

    ex: 'toot Hello World' will publish 'Hello World'.
    If no text is given then this will run the default editor.

    Toot visibility defaults to your account's settings.  You can change
    the defaults by logging into your instance in a browser and changing
    Preferences > Post Privacy.

    ex: 'toot Hello World'
                  will publish 'Hello World'
        'toot -v Hello World'
                  prompt for visibility setting and publish 'Hello World'

    Options:
        -v     Prompt for visibility (public, unlisted, private, direct)
        -c     Prompt for Content Warning / spoiler text
        -m     Prompt for media files and Sensitive Media
    """
    global is_streaming
    posted = False
    # Fill in Content fields first.
    try:
        (text, kwargs) = flaghandler_tootreply(mastodon, rest)
    except KeyboardInterrupt:
        # user abort, return to main prompt
        print("")
        return

    kwargs["visibility"] = toot_visibility(
        mastodon, flag_visibility=kwargs["visibility"]
    )

    if text == "":
        text = edittoot(text="")

    while posted is False:
        try:
            resp = mastodon.status_post(text, **kwargs)
            cprint("You tooted: ", fg("white") + attr("bold"), end="\n")
            if resp["sensitive"]:
                cprint("CW: " + resp["spoiler_text"], fg("red"))
            cprint(text, fg("magenta") + attr("bold") + attr("underline"))
            posted = True
        except Exception as e:
            cprint("Received error: ", fg("red") + attr("bold"), end="")
            cprint(e, fg("magenta") + attr("bold") + attr("underline"))

        # If we're streaming then we can't edit the toot, so assume that we posted.
        if is_streaming is True:
            posted = True

        if posted is False:
            retry = input("Edit toot and re-try? [Y/N]: ")
            if retry.lower() == "y":
                text = edittoot(text=text)
            else:
                posted = True


@command("<id> [<text>]", "Toots")
def rep(mastodon, rest):
    """Reply to a toot by ID.

    Reply visibility and content warnings default to the original toot's
    settings.

    ex: 'rep 13 Hello again'
                  reply to toot 13 with 'Hello again'
        'rep -vc 13 Hello again'
                  same but prompt for visibility and spoiler changes
    If no text is given then this will run the default editor.

    Options:
        -v     Prompt for visibility (public, unlisted, private, direct)
        -c     Prompt for Content Warning / spoiler text
        -C     No Content Warning (do not use original's CW)
        -m     Prompt for media files and Sensitive Media

    """

    posted = False
    try:
        (text, kwargs) = flaghandler_tootreply(mastodon, rest)
    except KeyboardInterrupt:
        # user abort, return to main prompt
        print("")
        return

    (parent_id, _, text) = text.partition(" ")
    parent_id = IDS.to_global(parent_id)
    if parent_id is None:
        msg = "  No message to reply to."
        cprint(msg, fg("red"))
        return

    if not text:
        text = edittoot(text="")

    if parent_id is None or not text:
        return

    try:
        parent_toot = mastodon.status(parent_id)
    except Exception as e:
        cprint("error searching for original: {}".format(type(e).__name__), fg("red"))
        return

    # Handle mentions text at the beginning:
    mentions_set = set()
    for i in parent_toot["mentions"]:
        mentions_set.add(i["acct"])
    mentions_set.add(parent_toot["account"]["acct"])

    # Remove our account
    # TODO: Better way to get this information?
    my_user = mastodon.account_verify_credentials()
    mentions_set.discard(my_user["username"])

    # Format each using @username@host and add a space
    mentions = ["@%s" % i for i in list(mentions_set)]
    mentions = " ".join(mentions)

    # if user didn't set cw/spoiler, set it here
    if kwargs["spoiler_text"] is None and parent_toot["spoiler_text"] != "":
        kwargs["spoiler_text"] = parent_toot["spoiler_text"]

    kwargs["visibility"] = toot_visibility(
        mastodon,
        flag_visibility=kwargs["visibility"],
        parent_visibility=parent_toot["visibility"],
    )

    while posted is False:
        try:
            reply_toot = mastodon.status_post(
                "%s %s" % (mentions, text), in_reply_to_id=parent_id, **kwargs
            )
            msg = "  Replied with:\n" + get_content(reply_toot)
            cprint(msg, attr("dim"))
            posted = True
        except Exception as e:
            cprint("error while posting: {}".format(type(e).__name__), fg("red"))

        if posted is False:
            retry = input("Edit toot and re-try? [Y/N]: ")
            if retry.lower() == "y":
                text = edittoot(text=text)
            else:
                posted = True


@command("<id> [votes]", "Toots")
def vote(mastodon, rest):
    """Vote  your toot by ID

    Example:
        >>> vote 23 1
        >>> vote 23 1,2,3
    """
    try:
        poll_id = None
        toot_id, rest = rest.split(" ", 1)
        global_id = IDS.to_global(toot_id)
        poll = mastodon.status(global_id).get("poll")
        if poll:
            poll_id = poll.get("id")
        if poll_id is None:
            cprint(f"  {toot_id} does not point to a valid poll.", fg("red"))
            return

        if rest is None:
            cprint("Note has no options.", fg("white") + bg("red"))
            return

        vote_options = rest_to_list(rest)
        if len(vote_options) > 1 and not poll.get("multiple"):
            cprint("Too many votes cast.", fg("white") + bg("red"))
            return

        mastodon.poll_vote(poll_id, vote_options)
        print("Vote cast.")
    except Exception as e:
        cprint(f"  {e}", fg("red"))


@command("<id>", "Toots")
def delete(mastodon, rest):
    """Deletes your toot by ID"""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_delete(rest)
    print("Poof! It's gone.")


@command("<id>", "Toots")
def boost(mastodon, rest):
    """Boosts a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    try:
        mastodon.status_reblog(rest)
        boosted = mastodon.status(rest)
        msg = "  You boosted:\n " + fg("white") + get_content(boosted)
        cprint(msg, attr("dim"))
    except Exception as e:
        cprint("Received error: ", fg("red") + attr("bold"), end="")
        cprint(e, fg("magenta") + attr("bold") + attr("underline"))


@command("<id>", "Toots")
def unboost(mastodon, rest):
    """Removes a boosted toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unreblog(rest)
    unboosted = mastodon.status(rest)
    msg = "  Removed boost:\n " + get_content(unboosted)
    cprint(msg, attr("dim"))


@command("<id> [<id>]", "Toots")
def fav(mastodon, rest):
    """Favorites a toot by ID or IDs."""
    favorite_ids = rest_to_list(rest)
    multiple = len(favorite_ids) > 1
    for favorite_id in favorite_ids:
        if favorite_id:
            favorite_global_id = IDS.to_global(favorite_id)
            if favorite_global_id is None:
                cprint(
                    f"  Can't favorite id {favorite_id}: Not found",
                    fg("red") + attr("bold"),
                )
                next
            faved = mastodon.status_favourite(favorite_global_id)
            msg = f"  Favorited ({favorite_id}):\n" + get_content(faved)
            cprint(msg, attr("dim"))
            if multiple:
                print()


@command("<id> [<id>]", "Toots")
def unfav(mastodon, rest):
    """Removes a favorite toot by ID or IDs."""
    favorite_ids = rest_to_list(rest)
    multiple = len(favorite_ids) > 1
    for favorite_id in favorite_ids:
        if favorite_id:
            favorite_global_id = IDS.to_global(favorite_id)
            if favorite_global_id is None:
                cprint(
                    f"  Can't unfavorite id {favorite_id}: Not found",
                    fg("red") + attr("bold"),
                )
                next
            unfaved = mastodon.status_unfavourite(favorite_global_id)
            msg = f"  Removed favorite ({favorite_id}):\n" + get_content(unfaved)
            cprint(msg, fg("yellow"))
            if multiple:
                print()


@command("<id>", "Toots")
def show(mastodon, rest):
    """Shows a toot by ID"""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    printToot(mastodon.status(rest), show_toot=True)


@command("", "Filter")
def filters(mastodon, rest):
    """Shows the filters that the user has created."""
    if not (list_support(mastodon)):
        return
    user_filters = mastodon.filters()
    if len(user_filters) == 0:
        cprint("No filters found", fg("red"))
        return
    for filter_item in user_filters:
        printFilter(filter_item)


@command("<id>", "Toots")
def bookmark(mastodon, rest):
    """Bookmark a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_bookmark(rest)
    item = mastodon.status(rest)
    msg = "  Bookmarked:\n" + get_content(item)
    cprint(msg, fg("red"))


@command("<id>", "Toots")
def unbookmark(mastodon, rest):
    """Remove a bookmark from a toot by ID."""
    rest = IDS.to_global(rest)
    if rest is None:
        return
    mastodon.status_unbookmark(rest)
    item = mastodon.status(rest)
    msg = "  Removed bookmark: " + get_content(item)
    cprint(msg, fg("yellow"))


@command("<id>", "Toots")
def showhistory(mastodon, rest):
    """Shows the history of the conversation for an ID with CWs/ Filters displayed"""
    history(mastodon, rest, show_toot=True)


@command("<id>", "Toots")
def history(mastodon, rest, show_toot=False):
    """Shows the history of the conversation for an ID.

    ex: history 23"""
    stepper, rest = step_flag(rest)
    rest = IDS.to_global(rest)
    if rest is None:
        return

    try:
        current_toot = mastodon.status(rest)
        conversation = mastodon.status_context(rest)
        print_toots(
            mastodon,
            conversation["ancestors"],
            stepper,
            ctx_name="Previous toots",
            show_toot=show_toot,
            sort_toots=False,
        )

        if stepper is False:
            cprint("Current Toot:", fg("yellow"))
        print_toots(
            mastodon,
            [current_toot],
            stepper,
            ctx_name="Current toot",
            show_toot=show_toot,
        )
        # printToot(current_toot)
        # completion_add(current_toot)
    except Exception as e:
        cprint("{}: please try again later".format(type(e).__name__), fg("red"))


@command("<id>", "Toots")
def showthread(mastodon, rest):
    """Shows the complete thread of the conversation for an ID while showing CWs / filters.

    ex: showthread 23"""
    thread(mastodon, rest, show_toot=True)


@command("<id>", "Toots")
def thread(mastodon, rest, show_toot=False):
    """Shows the complete thread of the conversation for an ID.

    ex: thread 23"""

    # Save the original "rest" so the history command can use it
    original_rest = rest
    stepper, rest = step_flag(rest)

    rest = IDS.to_global(rest)
    if rest is None:
        return

    try:
        # First display the history
        history(mastodon, original_rest, show_toot)

        # Then display the rest
        # current_toot = mastodon.status(rest)
        conversation = mastodon.status_context(rest)
        print_toots(
            mastodon,
            conversation["descendants"],
            stepper,
            show_toot=show_toot,
            sort_toots=False,
        )

    except Exception as e:
        raise e
        cprint("{}: please try again later".format(type(e).__name__), fg("red"))


@command("<id>", "Toots")
def puburl(mastodon, rest):
    """Shows the public URL of a toot, optionally open in browser.

    Example:
        >>> puburl 29       # Shows url for toot 29
        >>> puburl 29 open  # Opens toot 29 in your browser
    """

    # replace whitespace sequences with a single space
    args = " ".join(rest.split())
    args = args.split()
    if len(args) < 1:
        return

    status_id = IDS.to_global(args[0])
    if status_id is None:
        return

    try:
        toot = mastodon.status(status_id)
    except Exception as e:
        cprint("{}: please try again later".format(type(e).__name__), fg("red"))
    else:
        url = toot.get("url")

    if len(args) == 1:
        # Print public url
        print("{}".format(url))
    elif len(args) == 2 and args[1] == "open":
        webbrowser.open(url)
    else:
        cprint("PubURL argument was not correct. Please try again.", fg("red"))


@command("<id>", "Toots")
def links(mastodon, rest):
    """Show URLs or any links in a toot, optionally open in browser.

    Use `links <id> open` to open all link URLs or `links <id> open <number>` to
    open a specific link.

    Examples:
        >>> links 23         # Shows links for toot 23
        >>> links 23 open    # opens all links for toot 23 in your browser
        >>> links 23 open 1  # opens just the first link for toot 23 in your browser
    """

    # replace whitespace sequences with a single space
    args = " ".join(rest.split())
    args = args.split()
    if len(args) < 1:
        return

    status_id = IDS.to_global(args[0])
    if status_id is None:
        return

    try:
        toot = mastodon.status(status_id)
        toot_parser.parse(toot["content"])
    except Exception as e:
        cprint("{}: please try again later".format(type(e).__name__), fg("red"))
    else:
        links = toot_parser.get_weblinks()
        for media in toot.get("media_attachments"):
            links.append(media.url)

        if len(args) == 1:
            # Print links
            for i, link in enumerate(links):
                print("{}: {}".format(i + 1, link))
        else:
            # Open links
            link_num = None
            if len(args) == 3 and args[1] == "open" and len(args[2]) > 0:
                # Parse requested link number
                link_num = int(args[2])
                if len(links) < link_num or link_num < 1:
                    cprint(
                        "Cannot open link {}. Toot contains {} weblinks".format(
                            link_num, len(links)
                        ),
                        fg("red"),
                    )
                else:
                    webbrowser.open(links[link_num - 1])

            elif args[1] == "open":
                for link in links:
                    webbrowser.open(link)
            else:
                cprint("Links argument was not correct. Please try again.", fg("red"))


@command("", "Timeline")
def home(mastodon, rest):
    """Displays the Home timeline."""
    global LAST_PAGE, LAST_CONTEXT
    stepper, rest = step_flag(rest)
    limit, rest = limit_flag(rest)
    LAST_PAGE = mastodon.timeline_home(limit=limit)
    LAST_CONTEXT = "home"
    print_toots(mastodon, LAST_PAGE, stepper, limit, ctx_name=LAST_CONTEXT)


@command("", "Timeline")
def fed(mastodon, rest):
    """Displays the Federated timeline."""
    global LAST_PAGE, LAST_CONTEXT
    stepper, rest = step_flag(rest)
    limit, rest = limit_flag(rest)
    LAST_PAGE = mastodon.timeline_public(limit=limit)
    LAST_CONTEXT = "federated timeline"
    print_toots(mastodon, LAST_PAGE, stepper, limit, ctx_name=LAST_CONTEXT)


@command("", "Timeline")
def local(mastodon, rest):
    """Displays the Local timeline."""
    global LAST_PAGE, LAST_CONTEXT
    stepper, rest = step_flag(rest)
    limit, rest = limit_flag(rest)
    LAST_PAGE = mastodon.timeline_local(limit=limit)
    LAST_CONTEXT = "local timeline"
    print_toots(mastodon, LAST_PAGE, stepper, limit, ctx_name=LAST_CONTEXT)


@command("", "Timeline")
def next(mastodon, rest):
    """Displays the next page of paginated results."""
    global LAST_PAGE, LAST_CONTEXT
    curr_page = LAST_PAGE
    stepper, rest = step_flag(rest)
    if LAST_PAGE:
        LAST_PAGE = mastodon.fetch_next(LAST_PAGE)
        if LAST_PAGE:
            print_toots(mastodon, LAST_PAGE, stepper, ctx_name=LAST_CONTEXT)
            return
        else:
            LAST_PAGE = curr_page
    if LAST_CONTEXT:
        cprint(
            "No more toots in current context: " + LAST_CONTEXT, fg("white") + bg("red")
        )
    else:
        cprint("No current context.", fg("white") + bg("red"))


@command("", "Timeline")
def prev(mastodon, rest):
    """Displays the previous page of paginated results."""
    global LAST_PAGE, LAST_CONTEXT
    stepper, rest = step_flag(rest)
    curr_page = LAST_PAGE
    if LAST_PAGE:
        LAST_PAGE = mastodon.fetch_previous(LAST_PAGE)
        if LAST_PAGE:
            print_toots(mastodon, LAST_PAGE, stepper, ctx_name=LAST_CONTEXT)
            return
        else:
            LAST_PAGE = curr_page
    if LAST_CONTEXT:
        cprint(
            "No more toots in current context: " + LAST_CONTEXT, fg("white") + bg("red")
        )
    else:
        cprint("No current context.", fg("white") + bg("red"))


@command("<timeline>", "Timeline")
def stream(mastodon, rest):
    """Streams a timeline. Specify home, fed, local, list, or a #hashtagname.

    Timeline 'list' requires a list name (ex: stream list listname).

    Commands may be typed while streaming (ex: fav 23).

    Only one stream may be running at a time.

    Use ctrl+c to end streaming"""

    global is_streaming
    if is_streaming:
        cprint("Already streaming. Press ctrl+c to end this stream.", fg("red"))
        return

    cprint("Initializing stream...", style=fg("magenta"))

    def say_error(*args, **kwargs):
        cprint(
            "Invalid command. Use 'help' for a list of commands or press ctrl+c to end streaming.",
            fg("white") + bg("red"),
        )

    try:
        if rest == "home" or rest == "":
            handle = mastodon.stream_user(
                toot_listener, run_async=True, reconnect_async=True
            )
        elif rest == "fed" or rest == "public":
            handle = mastodon.stream_public(
                toot_listener, run_async=True, reconnect_async=True
            )
        elif rest == "local":
            handle = mastodon.stream_local(
                toot_listener, run_async=True, reconnect_async=True
            )
        elif rest.startswith("list"):
            # Remove list from the rest string
            items = rest.split("list ")
            if len(items) < 2:
                print("list stream must have a list ID.")
                return
            item = get_list_id(mastodon, items[-1])
            handle = mastodon.stream_list(
                item, toot_listener, run_async=True, reconnect_async=True
            )
        elif rest.startswith("#"):
            tag = rest[1:]
            handle = mastodon.stream_hashtag(
                tag, toot_listener, run_async=True, reconnect_async=True
            )
        else:
            handle = None
            print(
                "Only 'home', 'fed', 'local', 'list', and '#hashtag' streams are supported."
            )
    except KeyboardInterrupt:
        # Prevent the ^C from interfering with the prompt
        print("\n")
    except KeyError as e:
        if getattr(e, "args", None) == ("urls",):
            cprint(
                "The Mastodon instance is too old for this version of streaming support.",
                fg("red"),
            )
        else:
            cprint("Something went wrong: {}".format(e), fg("red"))
    except Exception as e:
        cprint("Something went wrong: {}".format(e), fg("red"))
    else:
        print("Use 'help' for a list of commands or press ctrl+c to end streaming.")

    if handle is not None:
        is_streaming = True
        command = None
        while command != "abort":
            try:
                command = input().split(" ", 1)
            except KeyboardInterrupt:
                cprint(
                    "Wrapping up, this can take a couple of seconds...",
                    style=fg("magenta"),
                )
                command = "abort"
            else:
                try:
                    rest_ = command[1]
                except IndexError:
                    rest_ = ""
                command = command[0]
                cmd_func = commands.get(command, say_error)
                cmd_func(mastodon, rest_)
        try:
            handle.close()
        except AttributeError:
            handle.running = False
            pass  # Trap for handle not getting set if no toots were received while streaming
        is_streaming = False


@command("", "Timeline")
def mentions(mastodon, rest):
    """Displays the Notifications timeline with only mentions

    ex: 'mentions'"""
    note(mastodon, "-bfFpru")


@command("[<filter>]", "Timeline")
def note(mastodon, rest):
    """Displays the Notifications timeline.

    ex: 'note'
                 will show all notifications
        'note -b'
                 will show all notifications minus boosts
        'note -f -F -b -u' (or 'note -fFb')
                will only show mentions

    Options:
        -b    Filter boosts
        -f    Filter favorites
        -F    Filter follows
        -m    Filter mentions
        -p    Filter polls
        -r    Filter follow requests
        -u    Filter updates"""

    displayed_notification = False

    # Fill in Content fields first.
    try:
        (text, kwargs) = flaghandler_note(mastodon, rest)
    except KeyboardInterrupt:
        # user abort, return to main prompt
        print("")
        return

    notifications = (
        mastodon.notifications()
    )  # TODO: Check if fetch_remaining should be used here
    if not (len(notifications) > 0):
        cprint("You don't have any notifications yet.", fg("magenta"))
        return

    for note in reversed(notifications):
        note_type = note.get("type")
        note_status = note.get("status", {})
        note_created_at = note_status.get("created_at")
        if note_created_at:
            note_time = " " + stylize(format_time(note_created_at), attr("dim"))
        note_media_attachments = note_status.get("media_attachments")
        display_name = "  " + format_display_name(
            note.get("account").get("display_name")
        )
        username = format_username(note.get("account"))
        note_id = str(note.get("id"))

        random.seed(display_name)

        # Check if we should even display this note type
        if kwargs[note_type]:
            # Display Note ID
            cprint(" note: " + note_id, fg("magenta"))

            # Mentions
            if note_type == "mention":
                displayed_notification = True
                cprint(display_name + username, fg("magenta"))
                print("  " + format_toot_idline(note_status) + "  " + note_time)
                cprint(get_content(note_status), attr("bold"), fg("white"))
                print(stylize("", attr("dim")))
                if note_media_attachments:
                    print("\n".join(get_media_attachments(note_status)))

            # Follows
            elif note_type == "follow":
                displayed_notification = True
                print("  ", end="")
                cprint(display_name + username + " followed you!", fg("yellow"))

            elif note_type == "follow_request":
                displayed_notification = True
                cprint(display_name + username + " sent a follow request", fg("yellow"))
                cprint(
                    "  Use 'accept' or 'reject' to accept or reject the request",
                    fg("yellow"),
                )

            # Update
            elif note_type in ["update", "favourite", "reblog", "poll"]:
                displayed_notification = True
                countsline = format_toot_idline(note_status)
                content = get_content(note_status)
                cprint(display_name + username, fg(random.choice(COLORS)), end="")
                if note_type == "update":
                    cprint(f" updated their status:", fg("yellow"))
                elif note_type == "reblog":
                    cprint(f" boosted your status:", fg("yellow"))
                elif note_type == "poll":
                    cprint(f" ended their poll:", fg("yellow"))
                else:
                    cprint(f" favorited your status:", fg("yellow"))
                print("  " + countsline + stylize(note_time, attr("dim")))
                cprint(content, attr("dim"))
                if getattr(note_status, "poll", None):
                    poll = get_poll(note_status)
                    cprint(poll, attr("dim"))

            print()

    if not displayed_notification:
        cprint("No notifications of this type are available.", fg("magenta"))


@command("[<note_id>]", "Timeline")
def dismiss(mastodon, rest):
    """Dismisses notifications.

    ex: dismiss or dismiss 1234567

    dismiss clears all notifications if no note ID is provided.
    dismiss 1234567 will dismiss note ID 1234567.

    The note ID is the id provided by the `note` command.
    """
    try:
        if rest == "":
            mastodon.notifications_clear()
            cprint(" All notifications were dismissed. ", fg("yellow"))
        else:
            if rest is None:
                return
            mastodon.notifications_dismiss(rest)
            cprint(" Note " + rest + " was dismissed. ", fg("yellow"))
    except Exception as e:
        cprint("Something went wrong: {}".format(e), fg("red"))


@command("<user>", "Users")
def block(mastodon, rest):
    """Blocks a user by username or id.

    ex: block 23
        block @user
        block @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    relations = mastodon.account_block(userid)
    if relations["blocking"]:
        cprint("  user " + str(userid) + " is now blocked", fg("blue"))
        username = "@" + mastodon.account(userid)["acct"]
        if username in completion_list:
            completion_list.remove(username)


@command("<user>", "Users")
def unblock(mastodon, rest):
    """Unblocks a user by username or id.

    ex: unblock 23
        unblock @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    relations = mastodon.account_unblock(userid)
    if not relations["blocking"]:
        cprint("  user " + str(userid) + " is now unblocked", fg("blue"))
        username = "@" + mastodon.account(userid)["acct"]
        if username not in completion_list:
            bisect.insort(completion_list, username)


@command("<user>", "Users")
def follow(mastodon, rest):
    """Follows an account by username or id.

    ex: follow 23
        follow @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    relations = mastodon.account_follow(userid)
    if relations["following"]:
        cprint("  user " + str(userid) + " is now followed", fg("blue"))
        username = "@" + mastodon.account(userid)["acct"]
        if username not in completion_list:
            bisect.insort(completion_list, username)


@command("<user>", "Users")
def unfollow(mastodon, rest):
    """Unfollows an account by username or id.

    ex: unfollow 23
        unfollow @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    relations = mastodon.account_unfollow(userid)
    if not relations.get("following"):
        cprint("  user " + str(userid) + " is now unfollowed", fg("blue"))
    username = "@" + mastodon.account(userid)["acct"]
    if username in completion_list:
        completion_list.remove(username)


@command("<user> [<duration>]", "Users")
def mute(mastodon, rest):
    """Mutes a user by username or id.

    ex: mute 23
        mute @user@instance.example.com
        mute @user 30s"""
    mute_time = None
    mute_seconds = None
    if " " in rest:
        username, mute_time = rest.split(" ")
    else:
        username = rest
    if mute_time:
        mute_seconds = pytimeparse.parse(mute_time)
    userid = get_unique_userid(mastodon, username)
    relations = mastodon.account_mute(userid, duration=mute_seconds)
    if relations.get("muting"):
        if mute_seconds:
            cprint("  user " + username + " is now muted for " + mute_time, fg("blue"))
        else:
            cprint("  user " + username + " is now muted", fg("blue"))


@command("<user>", "Users")
def unmute(mastodon, rest):
    """Unmutes a user by username or id.

    ex: unmute 23
        unmute @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    relations = mastodon.account_unmute(userid)
    username = rest
    if not relations["muting"]:
        cprint("  user " + username + " is now unmuted", fg("blue"))


@command("<query>", "Discover")
def search(mastodon, rest):
    """Search for a #tag or @user.

    ex:  search #tagname
         search @user
         search @user@instance.example.com"""
    global LAST_PAGE, LAST_CONTEXT
    usage = str("  usage: search #tagname\n" + "         search @username")
    stepper, rest = step_flag(rest)
    limit, rest = rest_limit(rest)
    try:
        indicator = rest[:1]
        query = rest[1:]
    except Exception:
        cprint(usage, fg("red"))
        return

    # @ user search
    if indicator == "@" and not query == "":
        users = mastodon.account_search(query, limit=limit)

        for user in users:
            printUser(user)
    # end @

    # # hashtag search
    elif indicator == "#" and not query == "":
        LAST_PAGE = mastodon.timeline_hashtag(query, limit=limit)
        LAST_CONTEXT = "search for #{}".format(query)
        print_toots(
            mastodon, LAST_PAGE, stepper, ctx_name=LAST_CONTEXT, add_completion=False
        )
    # end #

    else:
        raise ValueError("  Invalid format.\n" + usage)
    return


@command("<user> [<N>]", "Discover")
def user(mastodon, rest):
    """Displays profile information for another user

     <user>:   a userID, @username, or @user@instance

    ex: user 23
        user @user
        user @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest, exact=False)
    profile = mastodon.account(userid)
    if profile:
        printUser(profile)
        return
    raise Exception("user {rest} not found")


@command("<user> [<N>]", "Discover")
def view(mastodon, rest):
    """Displays toots from another user.

     <user>:   a userID, @username, or @user@instance
        <N>:   (optional) show N toots maximum

    ex: view 23
        view @user 10
        view @user@instance.example.com"""
    global LAST_PAGE, LAST_CONTEXT
    (user, _, count) = rest.partition(" ")

    # validate count argument
    if not count:
        count = None
    else:
        try:
            count = int(count)
        except ValueError:
            raise ValueError("  invalid count: {count}")

    userid = get_unique_userid(mastodon, user, exact=False)
    LAST_PAGE = mastodon.account_statuses(userid, limit=count)
    LAST_CONTEXT = f"{user} timeline"
    print_toots(mastodon, LAST_PAGE, ctx_name=LAST_CONTEXT, add_completion=False)


@command("", "Profile")
def info(mastodon, rest):
    """Prints your user info."""
    user = mastodon.account_verify_credentials()
    printUser(user)


@command("", "Profile")
def followers(mastodon, rest):
    """Lists users who follow you."""
    # TODO: compare user['followers_count'] to len(users)
    #       request more from server if first call doesn't get full list
    # TODO: optional username/userid to show another user's followers?
    user = mastodon.account_verify_credentials()
    limit, rest = limit_flag(rest)
    users = mastodon.fetch_remaining(mastodon.account_followers(user["id"], limit=limit))
    if not users:
        cprint("  Nobody follows you", fg("red"))
    else:
        cprint("  People who follow you ({}):".format(len(users)), fg("magenta"))
        printUsersShort(users)


@command("", "Profile")
def following(mastodon, rest):
    """Lists users you follow."""
    # TODO: compare user['following_count'] to len(users)
    #       request more from server if first call doesn't get full list
    # TODO: optional username/userid to show another user's following?
    user = mastodon.account_verify_credentials()
    limit, rest = limit_flag(rest)
    users = mastodon.fetch_remaining(mastodon.account_following(user["id"], limit=limit))
    if not users:
        cprint("  You aren't following anyone", fg("red"))
    else:
        cprint("  People you follow ({}):".format(len(users)), fg("magenta"))
        printUsersShort(users)


@command("", "Profile")
def blocks(mastodon, rest):
    """Lists users you have blocked."""
    limit, rest = limit_flag(rest)
    users = mastodon.fetch_remaining(mastodon.blocks(limit=limit))
    if not users:
        cprint("  You haven't blocked anyone (... yet)", fg("red"))
    else:
        cprint("  You have blocked:", fg("magenta"))
        printUsersShort(users)


@command("", "Profile")
def domainblocks(mastodon, rest):
    """Lists domains you have blocked."""
    limit, rest = limit_flag(rest)
    domains = mastodon.fetch_remaining(mastodon.domain_blocks(limit=limit))
    if not domains:
        cprint("  You haven't blocked any domains (... yet)", fg("red"))
    else:
        cprint("  You have blocked:", fg("magenta"))
        for domain in domains:
            cprint("  " + domain, fg('cyan'))


@command("", "Profile")
def mutes(mastodon, rest):
    """Lists users you have muted."""
    limit, rest = limit_flag(rest)
    users = mastodon.fetch_remaining(mastodon.mutes(limit=limit))
    if not users:
        cprint("  You haven't muted anyone (... yet)", fg("red"))
    else:
        cprint("  You have muted:", fg("magenta"))
        printUsersShort(users)


@command("", "Profile")
def requests(mastodon, rest):
    """Lists your incoming follow requests.

    Run 'accept id' to accept a request
     or 'reject id' to reject."""
    users = mastodon.fetch_remaining(mastodon.follow_requests())
    if not users:
        cprint("  You have no incoming requests", fg("red"))
    else:
        cprint("  These users want to follow you:", fg("magenta"))
        printUsersShort(users)
        cprint("  run 'accept <id>' to accept", fg("magenta"))
        cprint("   or 'reject <id>' to reject", fg("magenta"))


@command("<user>", "Profile")
def accept(mastodon, rest):
    """Accepts a user's follow request by username or id.

    ex: accept 23
        accept @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    mastodon.follow_request_authorize(userid)
    cprint(f"  user {rest}'s follow request is accepted", fg("blue"))


@command("<user>", "Profile")
def reject(mastodon, rest):
    """Rejects a user's follow request by username or id.

    ex: reject 23
        reject @user@instance.example.com"""
    userid = get_unique_userid(mastodon, rest)
    mastodon.follow_request_reject(userid)
    cprint(f"  user {rest}'s follow request is rejected", fg("blue"))


@command("", "Profile")
def faves(mastodon, rest):
    """Displays posts you've favourited."""
    print_toots(
        mastodon, mastodon.favourites(), ctx_name="favourites", add_completion=False
    )


@command("", "Profile")
def bookmarks(mastodon, rest):
    """Displays posts you've bookmarked."""
    print_toots(
        mastodon, mastodon.bookmarks(), ctx_name="bookmarks", add_completion=False
    )


@command("[<N>]", "Profile")
def me(mastodon, rest):
    """Displays toots you've tooted.

    <N>:   (optional) show N toots maximum"""
    itme = mastodon.account_verify_credentials()
    # no specific API for user's own timeline
    # let view() do the work
    view(mastodon, "{} {}".format(itme["id"], rest))


me.__section__ = "Profile"


@command("", "Profile")
def about(mastodon, rest):
    """Shows version information and connected instance"""
    print("Tootstream version: %s" % version)
    print("You are connected to ", end="")
    cprint(mastodon.api_base_url, fg("green") + attr("bold"))


@command("", "Profile")
def quit(mastodon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command("", "Profile")
def exit(mastodon, rest):
    """Ends the program."""
    sys.exit("Goodbye!")


@command("", "List")
def lists(mastodon, rest):
    """Shows the lists that the user has created."""
    if not (list_support(mastodon)):
        return
    user_lists = mastodon.lists()
    if len(user_lists) == 0:
        cprint("No lists found", fg("red"))
        return
    for list_item in user_lists:
        printList(list_item)


@command("<list>", "List")
def listcreate(mastodon, rest):
    """Creates a list."""
    if not (list_support(mastodon)):
        return
    mastodon.list_create(rest)
    cprint("List {} created.".format(rest), fg("green"))


@command("<list> <list>", "List")
def listrename(mastodon, rest):
    """Rename a list.
    ex:  listrename oldlist newlist"""
    if not (list_support(mastodon)):
        return
    rest = rest.strip()
    if not rest:
        cprint("Argument required.", fg("red"))
        return
    items = rest.split(" ")
    if len(items) < 2:
        cprint("Not enough arguments.", fg("red"))
        return

    list_id = get_list_id(mastodon, items[0])
    updated_name = items[1]

    mastodon.list_update(list_id, updated_name)
    cprint("Renamed {} to {}.".format(items[1], items[0]), fg("green"))


@command("<list>", "List")
def listdestroy(mastodon, rest):
    """Destroys a list.
    ex: listdestroy listname
        listdestroy 23"""
    if not (list_support(mastodon)):
        return
    item = get_list_id(mastodon, rest)

    mastodon.list_delete(item)
    cprint("List {} deleted.".format(rest), fg("green"))


@command("<list>", "List")
def listhome(mastodon, rest):
    """Show the toots from a list.
    ex:  listhome listname
         listhome 23"""
    global LAST_PAGE, LAST_CONTEXT
    if not (list_support(mastodon)):
        return
    if not rest:
        cprint("Argument required.", fg("red"))
        return
    stepper, rest = step_flag(rest)
    limit, list_name = rest_limit(rest)
    item = get_list_id(mastodon, list_name)
    LAST_PAGE = mastodon.timeline_list(item, limit=limit)
    LAST_CONTEXT = f"list ({list_name})"
    print_toots(mastodon, LAST_PAGE, stepper, limit, ctx_name=LAST_CONTEXT)


@command("<list>", "List")
def listaccounts(mastodon, rest):
    """Show the accounts for the list.
    ex:  listaccounts listname
         listaccounts 23"""
    if not (list_support(mastodon)):
        return
    item = get_list_id(mastodon, rest)
    list_accounts = mastodon.fetch_remaining(mastodon.list_accounts(item))

    cprint("List: %s" % rest, fg("green"))
    for user in list_accounts:
        username = "@" + user.get("acct")
        if username not in completion_list:
            bisect.insort(completion_list, username)
        printUser(user)


@command("<list> <user>", "List")
def listadd(mastodon, rest):
    """Add user to list.
    ex:  listadd listname @user@instance.example.com
         listadd 23 @user@instance.example.com"""
    if not (list_support(mastodon)):
        return
    if not rest:
        cprint("Argument required.", fg("red"))
        return
    items = rest.split(" ")
    if len(items) < 2:
        cprint("Not enough arguments.", fg("red"))
        return

    list_id = get_list_id(mastodon, items[0])
    account_id = get_unique_userid(mastodon, items[1])
    mastodon.list_accounts_add(list_id, account_id)
    cprint("Added {} to list {}.".format(items[1], items[0]), fg("green"))


@command("<list> <user>", "List")
def listremove(mastodon, rest):
    """Remove user from list.
    ex:  listremove list user@instance.example.com
         listremove 23 user@instance.example.com
         listremove 23 42"""
    if not (list_support(mastodon)):
        return
    if not rest:
        cprint("Argument required.", fg("red"))
        return
    items = rest.split(" ")
    if len(items) < 2:
        cprint("Not enough arguments.", fg("red"))
        return

    list_id = get_list_id(mastodon, items[0])
    account_id = get_unique_userid(mastodon, items[1])
    mastodon.list_accounts_delete(list_id, account_id)
    cprint("Removed {} from list {}.".format(items[1], items[0]), fg("green"))


#####################################
######### END COMMAND BLOCK #########
#####################################


def authenticated(mastodon):
    if not os.path.isfile(APP_CRED):
        return False
    if mastodon.account_verify_credentials().get("error"):
        return False
    return True


def get_mastodon(instance, config, profile):
    configpath = os.path.expanduser(config)
    if os.path.isfile(configpath) and not os.access(configpath, os.W_OK):
        # warn the user before they're asked for input
        cprint(
            "Config file does not appear to be writable: {}".format(configpath),
            fg("red"),
        )

    config = parse_config(configpath)

    # make sure profile name is legal
    profile = re.sub(r"\s+", "", profile)  # disallow whitespace
    profile = profile.lower()  # force to lowercase
    if profile == "" or profile in RESERVED:
        cprint("Invalid profile name: {}".format(profile), fg("red"))
        sys.exit(1)

    if not config.has_section(profile):
        config.add_section(profile)

    instance, client_id, client_secret, token = get_or_input_profile(
        config, profile, instance
    )

    if not token:
        cprint("Could not log you in.  Please try again later.", fg("red"))
        sys.exit(1)

    mastodon = Mastodon(
        client_id=client_id,
        client_secret=client_secret,
        access_token=token,
        api_base_url="https://" + instance,
    )

    # update config before writing
    if "token" not in config[profile]:
        config[profile] = {
            "instance": instance,
            "client_id": client_id,
            "client_secret": client_secret,
            "token": token,
        }

    save_config(configpath, config)
    return (mastodon, profile)


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--instance", "-i", metavar="<string>", help="Hostname of the instance to connect"
)
@click.option(
    "--config",
    "-c",
    metavar="<file>",
    type=click.Path(exists=False, readable=True),
    default="~/.config/tootstream/tootstream.conf",
    help="Location of alternate configuration file to load",
)
@click.option(
    "--profile",
    "-P",
    metavar="<profile>",
    default="default",
    help="Name of profile for saved credentials (default)",
)
def main(instance, config, profile):
    mastodon, profile = get_mastodon(instance, config, profile)

    def say_error(a, b):
        return cprint(
            "Invalid command. Use 'help' for a list of commands.",
            fg("white") + bg("red"),
        )

    about(mastodon, "")

    print("Enter a command. Use 'help' for a list of commands.")
    print("\n")

    user = mastodon.account_verify_credentials()
    username = str(user.get("username"))
    prompt = update_prompt(username=username, context=LAST_CONTEXT, profile=profile)

    # Completion setup stuff
    if list_support(mastodon, silent=True):
        for i in mastodon.lists():
            bisect.insort(completion_list, i["title"].lower())

    for i in mastodon.account_following(user["id"], limit=80):
        bisect.insort(completion_list, "@" + i["acct"])
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" ")

    while True:
        command = input(prompt).split(" ", 1)
        rest = ""
        try:
            rest = command[1]
        except IndexError:
            pass
        try:
            command = command[0]
            cmd_func = commands.get(command, say_error)
            cmd_func(mastodon, rest)
        except AlreadyPrintedException:
            pass
        except Exception as e:
            cprint(e, fg("red"))
        prompt = update_prompt(username=username, context=LAST_CONTEXT, profile=profile)


if __name__ == "__main__":
    main()
