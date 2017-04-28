# tootstream

A command line interface for interacting with Mastodon instances written in python.

(tootstream currently does NOT support Two-Factor-Authentication)

Inspired by [Rainbowstream](
https://github.com/DTVD/rainbowstream).

## Demo

[![tootstream displaying the Federated timeline](https://asciinema.org/a/3m87j1s402ic2llfp517okpv2.png)](https://asciinema.org/a/3m87j1s402ic2llfp517okpv2?t=7&speed=2)

## Install

1: Clone this repo and enter the project directory through a virtual environment
```
$ git clone https://github.com/magicalraccoon/tootstream.git
$ cd tootstream
$ virtualenv -p python3 tootstream
$ source ./tootstream/bin/activate
```
2: Install the project dependencies
```
$ cd ..
$ python3 setup.py install
```
3: Close the environment with `$ deactivate`

## Usage

1: Return to your virtual environment

`$ source ./tootstream/bin/activate`

2: Run the script
```
$ python3 tootstream/toot.py
```
3: Close the environment with: `$ deactivate`

## Contributing

Contributions welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before getting started.

## License

[MIT](LICENSE.md)
