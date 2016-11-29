from mastodon import Mastodon
import os.path

APP_PATH = 'file.txt'


"^login (?P<name>[a-z0-9_]{1,30}) (?P<pass>\w+)$"


def main():
    checkFile()
    while True:
        

def checkFile():
    if os.path.isfile(APP_PATH):
        return
    Mastodon.create_app(
        'tootstream',
         to_file = APP_PATH
    )

    
if __name__ == '__main__':
    main()

    
    #############################

from setuptools import setup, find_packages
setup(
    name="TootStream",
    version="0.1",
    packages=find_packages(),
    scripts=['tootstream.py'],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=['docutils>=0.3'],

    package_data={
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        'hello': ['*.msg'],
    },

    # metadata for upload to PyPI
    author="Sara Murray",
    author_email="saramurray@protonmail.com",
    description="A command line interface for interacting with Mastodon instances",
    license="PSF",
    keywords="mastodon, mastodon.social, toot, tootstream",
    url="http://www.github.com/magicalraccoon/tootstream",   # project home page, if any

    # could also include long_description, download_url, classifiers, etc.
)
