# tootstream

A command line interface for interacting with Mastodon instances written in Python (requires Python 3).

OAuth and 2FA are supported.

Inspired by [Rainbowstream](
https://github.com/DTVD/rainbowstream).

## Demo

[![tootstream displaying the Federated timeline](https://i.imgur.com/LqjUXpt.jpg)](https://asciinema.org/a/3m87j1s402ic2llfp517okpv2?t=7&speed=2)

## Install via pip

1: Create a virtual environment
```
$ virtualenv -p python3 /path/to/tootstream
$ source /path/to/tootstream/bin/activate
```

2: Install via pip
```
$ pip install tootstream
```

3: See the *Usage* section for how to use Tootstream.

## Install for development

1: Clone this repo and enter the project directory through a virtual environment
```
$ git clone https://github.com/magicalraccoon/tootstream.git
$ cd tootstream
```

2: Create a Virtual Environment

```
# Create a virtual environment
$ virtualenv -p python3 /path/to/tootstream
$ source /path/to/tootstream/bin/activate
```

3: Install the project 
```
$ python3 setup.py install
```

4: Close the environment with `$ deactivate`

## Usage

1: Return to your virtual environment
```
$ source /path/to/tootstream/bin/activate
```

2: Run the program
```
$ tootstream
```

3: Use the ``help`` command to see the available commands
```
[@myusername (default)]: help
```

4: Exit the program when finished
```
[@myusername (default)]: quit

```

5: Close the environment with `$ deactivate`

## Ubuntu and Unicode

Tootstream relies heavily on Unicode fonts. The best experience can be had by installing the following package:

```
$ sudo apt-get install ttf-ancient-fonts
```

## Configuration

By default tootstream uses [configparser](https://docs.python.org/3/library/configparser.html) for configuration. The default configuration is stored in the default location for configparser (on the developer's machine this is under /home/myusername/.config/tootstream/tootstream.conf). 

At the moment tootstream only stores login information for each instance in the configuration file. Each instance is under its own section (the default configuration is under the ``[default]`` section). Multiple instances can be stored in the ``tootstream.conf`` file. (See "Using multiple instances")

## Using multiple instances

Tootstream supports using accounts on multiple Mastodon instances.

Use the ``--instance`` parameter to pass the server location (in the case of Mastodon.social we'd use ``--instance mastodon.social``).

Use the ``--profile`` parameter to use a different named profile. (in the case of Mastodon.social we could call it ``mastodon.social`` and name the section using ``--profile mastodon.social``).

By default tootstream uses the ``[default]`` profile. If this already has an instance associated with it then tootstream will default to using that instance.

If you have already set up a profile you may use the ``--profile`` command-line switch to start tootstream with it. The ``--instance`` parameter is optional (and redundant).

You may select a different configuration using ``--config`` and pass it the full-path to that file.

## Notes on networking

Tootstream and Mastodon.py use the [requests](https://pypi.python.org/pypi/requests) library for communicating with the Mastodon instance. Any proxy settings you may need to communicate with the network will need to be in a format that the requests library understands. See the requests documentation for more details on what those environment variables should be. 

## Contributing

Contributions welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before getting started.

## Code of Conduct

This project is intended to be a safe, welcoming space for collaboration. All contributors are expected to adhere to the [Contributor Covenant](http://contributor-covenant.org) code of conduct. Thank you for being kind to each other!

## License

[MIT](LICENSE.md)
