from setuptools import setup, find_packages
setup(
    name="tootstream",
    version="0.1",
    packages=find_packages(),
    scripts=['tootstream.py'],

    install_requires=[
        'mastodon',
        'click',
    ],

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
