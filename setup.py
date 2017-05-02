from setuptools import setup, find_packages
setup(
    name="tootstream",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[line.strip() for line in open('requirements.txt')],

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
    license="MIT",
    keywords="mastodon, mastodon.social, toot, tootstream",
    url="http://www.github.com/magicalraccoon/tootstream",   # project home page, if any

    # could also include long_description, download_url, classifiers, etc.
)
