from setuptools import setup, find_packages
from codecs import open

from digitalmarketplace import deploy

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()

if __name__ == '__main__':
    setup(
        name='digitalmarketplace-deploy',
        version=deploy.__version__,
        packages=find_packages(exclude=['app*']),
        namespace_packages=['digitalmarketplace'],
        description='Digital marketplace deployment tools',
        long_description=readme,
        author=deploy.__author__,
        author_email=deploy.__author_email__,
        url='https://github.com/pebblecode/cirrus-marketplace-deployment',
        licence='MIT',

        install_requires=[
            'argh==0.26.1',
            'boto==2.34.0',
        ],

        entry_points={
            'console_scripts': [
                'dm-deploy=digitalmarketplace.deploy.cli:main',
            ]
        }
    )
