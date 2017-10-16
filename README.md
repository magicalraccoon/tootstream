# tootstream

A command line interface for interacting with Mastodon instances written in python.

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

2: Run the script
```
$ tootstream
```
3: Close the environment with `$ deactivate`

## Contributing

Contributions welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before getting started.

## Code of Conduct

This project is intended to be a safe, welcoming space for collaboration. All contributors are expected to adhere to the [Contributor Covenant](http://contributor-covenant.org) code of conduct. Thank you for being kind to each other!

## License

[MIT](LICENSE.md)
