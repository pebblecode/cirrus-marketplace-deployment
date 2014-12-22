# AWS client for deployment
import os.path
import hashlib
import logging
import re

from boto import beanstalk, s3
from boto.s3.key import Key
from boto.exception import S3CreateError, BotoServerError

from . import git


DEFAULT_SOLUTION_STACK = '64bit Amazon Linux 2014.03 v1.0.9 running Python 2.7'


def get_client(region):
    return Client(region)


class Client(object):
    """High level interface for deploying in Beanstalk"""

    def __init__(self, region):
        self.s3 = S3Client(region)
        self.beanstalk = BeanstalkClient(region)
        self.application_name = git.get_application_name()

    def create_configuration(self, proxy_env):
        option_name = 'aws:elasticbeanstalk:application:environment'
        option_settings = [
            (option_name, env_name, os.environ[env_name])
            for env_name in proxy_env]

        self.beanstalk.create_configuration_template(
            self.application_name, 'default',
            DEFAULT_SOLUTION_STACK, option_settings)

    def bootstrap(self, proxy_env):
        """Bootstrap a new application"""
        self.s3.create_bucket(self.application_name)
        self.beanstalk.create_application(self.application_name)
        self.create_configuration(proxy_env)

        version_label = self.create_version(
            'initial',
            description='Initial code version for bootstrap')
        for environment_name in ['staging', 'production']:
            self.beanstalk.create_environment(
                self.application_name, environment_name, version_label)

    def create_version(self, version_label, with_sha=False, description=''):
        sha, package_path = git.create_package()
        s3_bucket, s3_key = self.s3.upload_package(
            self.application_name, package_path)
        if with_sha:
            version_label = '{}-{}'.format(version_label, sha[:7])
        self.beanstalk.create_application_version(
            self.application_name, version_label,
            s3_bucket, s3_key,
            description)
        return version_label

    def deploy_to_branch_environment(self, branch):
        environment_name = 'dev-{}'.format(branch)
        version_label = self.create_version(environment_name, with_sha=True)
        self.beanstalk.create_or_update_environment(
            self.application_name, environment_name, version_label)

    def terminate_branch_environment(self, branch):
        environment_name = 'dev-{}'.format(branch)
        self.beanstalk.terminate_environment(
            self.application_name, environment_name)

    def deploy(self, version_label, environment_name):
        self.beanstalk.update_environment(
            self.application_name, environment_name, version_label)


class S3Client(object):
    def __init__(self, region, **kwargs):
        self._region = region
        self._options = kwargs
        self._connection = self._get_connection(region)

    def _get_connection(self, region):
        return s3.connect_to_region(region)

    def create_bucket(self, application_name):
        if self._region.startswith('eu'):
            location = 'EU'
        else:
            location = ''
        try:
            self._connection.create_bucket(application_name, location=location)
        except S3CreateError as e:
            if 'BucketAlreadyOwnedByYou' != e.error_code:
                raise

    def upload_package(self, application_name, package_path):
        bucket = self._connection.get_bucket(application_name)
        key = Key(bucket)
        key.key = os.path.basename(package_path)
        key.set_contents_from_filename(package_path)

        return application_name, key.key


class BeanstalkClient(object):

    def __init__(self, region, **kwargs):
        self._region = region
        self._options = kwargs
        self._connection = self._get_connection(region)

    @property
    def solution_stack_name(self):
        return self._options.get(
            'solution_stack_name', DEFAULT_SOLUTION_STACK)

    def _get_connection(self, region):
        return beanstalk.connect_to_region(region)

    def create_application(self, application_name):
        try:
            self._connection.create_application(application_name)
        except BotoServerError as e:
            if self._application_already_exists(e):
                raise ApplicationAlreadyExists(e.message)
            else:
                raise

    def create_environment(self, application_name, environment_name,
                           version_label):
        environment_name = self._environment_name(
            application_name, environment_name)
        self._connection.create_environment(
            application_name, environment_name, version_label,
            template_name='default')

    def create_configuration_template(self, application_name, template_name,
                                      solution_stack_name, option_settings):
        self._connection.create_configuration_template(
            application_name, template_name, solution_stack_name,
            option_settings=option_settings)

    def _environment_name(self, application_name, environment_name):
        """Return an environment name

        Generate an environment name from the application name and
        an environment name. Amazon Beanstalk requires environment names to
        be unique across applications so the application name must be
        encoded into the environment name.
        """
        return '{}-{}'.format(
            hashlib.sha1(application_name).hexdigest()[:5],
            environment_name)

    def update_environment(self, application_name, environment_name,
                           version_label):
        try:
            environment_name = self._environment_name(
                application_name, environment_name)
            logging.info("Updaing {} to version {}".format(
                         environment_name, version_label))
            self._connection.update_environment(
                environment_name=environment_name,
                version_label=version_label)
        except BotoServerError as e:
            if self._environment_not_ready(e):
                raise EnvironmentNotReady(e.message)
            else:
                raise

    def create_or_update_environment(self, application_name, environment_name,
                                     version_label):
        try:
            self.create_environment(
                application_name, environment_name, version_label)
        except BotoServerError as e:
            if self._environment_already_exists(e):
                self.update_environment(
                    application_name, environment_name, version_label)
            else:
                raise

    def terminate_environment(self, application_name, environment_name):
        try:
            environment_name = self._environment_name(
                application_name, environment_name)
            self._connection.terminate_environment(
                environment_name=environment_name)
        except BotoServerError as e:
            if self._cannot_terminate_environment(e):
                raise CannotTerminateEnvironment(e.message)
            else:
                raise

    def create_application_version(self, application_name, version_label,
                                   s3_bucket, s3_key, description):
        try:
            self._connection.create_application_version(
                application_name, version_label,
                s3_bucket=s3_bucket, s3_key=s3_key,
                description=description)
        except BotoServerError as e:
            if not self._application_version_already_exists(e):
                raise

    def _application_already_exists(self, e):
        if e.error_code != 'InvalidParameterValue':
            return False
        return re.match(r'Application .* already exists.', e.message)

    def _cannot_terminate_environment(self, e):
        if e.error_code != 'InvalidParameterValue':
            return False
        return re.match(r'Cannot terminate environment named', e.message)

    def _environment_not_ready(self, e):
        if e.error_code != 'InvalidParameterValue':
            return False
        pattern = r'Environment named .* is in an invalid state for this ' + \
            'operation. Must be Ready.'
        return re.match(pattern, e.message)

    def _environment_already_exists(self, e):
        if e.error_code != 'InvalidParameterValue':
            return False
        return re.match(r'Environment .* already exists.', e.message)

    def _application_version_already_exists(self, e):
        if e.error_code != 'InvalidParameterValue':
            return False
        return re.match(r'Application Version .* already exists.', e.message)


class AWSError(StandardError):
    pass


class ApplicationAlreadyExists(AWSError):
    pass


class CannotTerminateEnvironment(AWSError):
    pass


class EnvironmentNotReady(AWSError):
    pass
