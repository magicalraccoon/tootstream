# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


### Release
### [0.3.8.1] - 2020-01-22

#### Fixed
- Upgrade to Mastodon.py 1.5.0
- PEP8 code formatting

### Release
### [0.3.7] - 2019-07-20

#### Fixed
- Upgrade to Mastodon.py 1.4.5
- Rudimentary support for polls (shows links to polls)
- Update colored minimum version to 1.3.93 (Fixes GPL license incompatibility)
- Support Pleroma FlakeIDs
- Minor fix for stream command being closed without receiving a toot getting a Nonetype for handle

### Release
### [0.3.6] - 2018-09-29

#### Added
- Updated to Mastodon.py 1.3.1 (No additional features yet)
- Added links command to show links in a toot and optionally open them in a browser
- Added puburl command to show the public URL of a toot

#### Fixed
- Upgrade to Mastodon.py 1.3.1 fixes searching for users issue noted in 0.3.5
- Spelling mistakes 
- Added better error message for streaming support not supported on older mastodon instances

### Release
### [0.3.5] - 2018-08-08

#### Added
- Updated to Mastodon.py 1.3 (no additional features yet)

#### Fixed
- List renames did not work


### Release
### [0.3.4] - 2018-05-30

#### Added
- Added ability to execute commands while streaming (toot, fav, rep, etc.)
- Added step switch for stepping through the timelines (ex: home step, listhome step)
- Execute commands on stepped toots (fav, boost, rep, etc.)
- Added ability to show links and optionally open those links in a browser (see "help links" for details).
- Display media links by default
- Display message when no notifications are present

#### Fixed
- Privacy settings now default to server privacy settings for toots
- CTRL-C in streaming adds a linefeed to preserve prompt spacing
- Streaming now supports lists with spaces
- Added broad exception handling so tootstream shouldn't crash while running commands.
- Minor formatting fixes

### Release
### [0.3.3] - 2018-02-17

#### Added
- List support for servers that support it. (See ``help list`` for more details.)
- Bumped to Mastodon.py 1.2.2

#### Added (awaiting proper config)
( The following items are active but require a re-working of the configuration file to make active. Currently they are flags inside the ``toot_parser.py`` file. Intrepid explorers may find them.)
- Added emoji shortcode (defaults to "off").
- Added emoji "demoji" to show shortcodes for emoji (defaults to off).

#### Fixed
- Fixed boosting private toots
- Fixed message for boosting toots
- Fixed leading / trailing whitespace from media filepath
- Added better exception handling around streaming API

####

### Release
### [0.3.2] - 2017-12-23

#### Added
- Reworked the Tootstream Parser to add styling, link-shortening, link retrieval, and emoji code shortening
- About shows current version of Tootstream and the connected instance
- Notifications may now be filtered

#### Fixed
- Replies no longer include the logged-in user
- Allow user to edit a toot when an API error occurs
- Compatibility with Mastodon.py 1.2.1

### Release
### [0.3.1] - 2017-11-21

#### Fixed
- Compatibility with Mastodon 1.1.2 fix

### Release
### [0.3.0] - 2017-11-17
### Dedicated to the memory of Natalie Nguyen (aka Tipsy Tentacle). May she live on in our hearts and our changelog.
#### Added
- Upload media via a toot and set visibility
- Set content warnings on a toot
- Set visibility of a toot (public, unlisted, private, direct)
- Thread and history commands for viewing a toot's thread
- "Humanized" time formats for toots (how long ago did this occur from now?)
- Clear out notifications / dismiss individual notifications

##### Changed
- Help is split into sections (Help, Toots, Timeline, Users, Discover, and Profile)
- Can type "help section" to see the help for that section

##### Fixed
- Changed the glyphs so they are encoded
- Python 3 requirement is now explicit

### Release
### [0.2.0] - 2017-10-17
#### Added
- Command auto-complete
- Nickname autocomplete for local and federated users
- View command: view the latest toots from a user
- Search function
- Followers / Following list
- Block / Unblock function
- Mute / Unmute function
- Follow requests (accept / reject)
- Bring up the default editor when no text is added for toot and rep commands
- Added --profile command line option
- Proper Python Packaging

#### Changed
- Using Mastodon.py 1.1.0
- ``get_userid`` check API results list for exact match to user input
- Many formatting changes (now using glyphs and content warning, timestamps on metions)
- Refactored login and user prompts
- Simplified the requirements to only include requirements for tootstream

#### Fixed
- Favorite / Boost/ Reply won't crash without ID
- Local timeline actually shows local timeline
- Accept / Reject Status fixed.
- Configuration file more resilient
- Empty toots could crash the program with later Mastodon.py

### Release
### [0.1.0] - 2017-05-02
#### Added
- Contribution guide
- License
