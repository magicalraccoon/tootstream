from setuptools import setup, find_packages
setup(
    name="tootstream",
    version="0.1.0",
    install_requires=[line.strip() for line in open('requirements.txt')],

    packages=find_packages('src'),
    package_dir={'tootstream': 'src'}, include_package_data=True,
    package_data={
    },

    # metadata for upload to PyPI
    author="Sara Murray",
    author_email="saramurray@protonmail.com",
    description="A command line interface for interacting with Mastodon instances",
    license="MIT",
    keywords="mastodon, mastodon.social, toot, tootstream",
    url="http://www.github.com/magicalraccoon/tootstream",   # project home page, if any
    entry_points={
        'console_scripts':
            ['tootstream=tootstream.toot:main']
    }

    # could also include long_description, download_url, classifiers, etc.
)
