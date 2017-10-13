# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

### Release
### [0.2.0] - TBA
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
