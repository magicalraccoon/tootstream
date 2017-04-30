# tootstream
A command line interface for interacting with Mastodon instances written in python.

tootstream currently does not support 2FA.

#### tootstream displaying the Federated timeline:
![Tootstream displaying the Federated timeline](https://i.imgur.com/HBhhjuV.png)		

## Using tootstream
1: Clone this repo and enter the project directory through a virtual environment
```
$ git clone https://github.com/magicalraccoon/tootstream.git
$ cd tootstream
$ virtualenv -p python3 tootstream
$ source ./tootstream/bin/activate
```
2: Install the project dependencies
```
$ cd tootstream
$ python3 setup.py install
```
3: Run the script
```
$ python3 tootstream/toot.py
```
###### Close with: `$ deactivate`

#### Inspired by Rainbowstream
https://github.com/DTVD/rainbowstream
