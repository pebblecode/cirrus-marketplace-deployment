# Command line interface to deployment
from __future__ import print_function
import sys
import logging

import argh

from digitalmarketplace.deploy import aws, git


proxy_env_arg = argh.arg(
    '-e', '--proxy-env',
    type=lambda value: filter(None, map(str.strip, value.split(','))),
    default="",
    help="Comma separated list of environment variables to proxy to the " +
         "configuration template")


@argh.arg('db_name', help='Database name')
@argh.arg('db_username', help='Master database username')
@argh.arg('db_password', help='Master database password')
@proxy_env_arg
def bootstrap(db_name, db_username, db_password, proxy_env=None, region=None):
    """Create a new application with an S3 bucket and core environments"""
    aws.get_client(region).bootstrap(proxy_env,
                                     db_name, db_username, db_password)


def create_version(version_label, region=None):
    """Create a new version of the application from the current HEAD"""
    aws.get_client(region).create_version(version_label)


@argh.arg('name', help='Name for the environment')
@argh.arg('db_name', help='Database name')
@argh.arg('db_username', help='Master database username')
@argh.arg('db_password', help='Master database password')
def deploy_to_development_environment(name, db_name, db_username, db_password,
                                      region=None):
    """Deploy the current HEAD to a temporary development environment"""
    aws.get_client(region).deploy_to_development_environment(name, db_name,
                                                             db_username,
                                                             db_password)


@argh.arg('name', help='Name for the environment')
def terminate_development_environment(name, region=None):
    """Terminate a temporary development environment"""
    aws.get_client(region).terminate_development_environment(name)


def deploy_latest_to_staging(region=None):
    """Deploy latest release version to the staging environment"""
    aws.get_client(region).deploy_latest_to_staging()


def deploy_staging_to_production(region=None):
    """Deploy the version currently in staging to production"""
    aws.get_client(region).deploy_staging_to_production()


def deploy_to_staging(version_label, region=None):
    """DANGER: Deploy a version to the staging environment"""
    aws.get_client(region).deploy(version_label, 'staging')


def deploy_to_production(version_label, region=None):
    """DANGER: Deploy a version to the production environment"""
    aws.get_client(region).deploy(version_label, 'production')


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argh.ArghParser()
    parser.add_argument('--region', default='eu-west-1')
    parser.add_commands([
        bootstrap,
        create_version,
        deploy_to_development_environment,
        terminate_development_environment,
        deploy_latest_to_staging,
        deploy_staging_to_production,
        deploy_to_staging,
        deploy_to_production])
    try:
        parser.dispatch()
    except aws.AWSError as e:
        print(e.message, file=sys.stderr)
        sys.exit(1)
