from setuptools import setup, find_packages
setup(
    name="tootstream",
    version="0.3.0rc1",
    install_requires=[line.strip() for line in open('requirements.txt')],

    packages=find_packages('src'),
    package_dir={'': 'src'}, include_package_data=True,
    package_data={
    },

    author="Sara Murray",
    author_email="saramurray@protonmail.com",
    description="A command line interface for interacting with Mastodon instances",
    license="MIT",
    keywords="mastodon, mastodon.social, toot, tootstream",
    url="http://www.github.com/magicalraccoon/tootstream",
    entry_points={
        'console_scripts':
            ['tootstream=tootstream.toot:main']
    }

)
