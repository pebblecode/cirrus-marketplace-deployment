# AWS client for deployment
import os.path
import hashlib
import logging
import re
import time
from collections import namedtuple

from boto import beanstalk, ec2, s3, rds2
from boto.s3.key import Key
from boto.exception import S3CreateError, BotoServerError

from . import git


DEFAULT_SOLUTION_STACK = '64bit Amazon Linux 2016.03 v2.1.0 running Python 2.7'
DEFAULT_ENVIRONMENT_NAMES = ['staging', 'production']


def get_client(region):
    """
    :rtype: Client
    """
    return Client(region)


class Client(object):
    """High level interface for deploying in Beanstalk"""

    def __init__(self, region):
        self.s3 = S3Client(region)
        self.beanstalk = BeanstalkClient(region)
        self.ec2 = EC2Client(region)
        self.rds = RDSClient(region)
        self.application_name = git.get_application_name()

    def bootstrap(self, proxy_env, db_name, db_username, db_password):
        """Bootstrap a new application"""
        self.s3.create_bucket(self.application_name)
        self.beanstalk.create_application(self.application_name)
        self.beanstalk.create_configuration_template(
            self.application_name, 'default',
            solution_stack=DEFAULT_SOLUTION_STACK,
            environ=dict(
                (env_name, os.environ[env_name]) for env_name in proxy_env))

        version_label = self.create_version(
            'initial',
            description='Initial code version for bootstrap')

        for environment_short_name in DEFAULT_ENVIRONMENT_NAMES:
            environment_name = self._get_env_name(environment_short_name)
            self._create_environment(environment_name, db_name,
                                     db_username, db_password, version_label)

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

    def deploy_to_branch_environment(self, branch, db_name, db_username,
                                     db_password):
        environment_short_name = 'dev-{}'.format(branch)
        environment_name = self._get_env_name(environment_short_name)
        version_label = self.create_version(
            environment_short_name, with_sha=True)

        if self.rds.get_security_group(environment_name) is None:
            self._create_environment(environment_name, db_name,
                                     db_username, db_password, version_label)
        else:
            self.beanstalk.update_environment(environment_name,
                                              version_label)

    def terminate_branch_environment(self, branch):
        environment_short_name = 'dev-{}'.format(branch)
        environment_name = self._get_env_name(environment_short_name)

        self.beanstalk.terminate_environment(environment_name)

        self.beanstalk.delete_configuration_template(self.application_name,
                                                     environment_name)

        self.rds.delete_dbinstance(environment_name)

    def _create_environment(self, environment_name, db_name, db_username,
                            db_password, version_label):
        db_info = self._create_rds_instance(environment_name, db_name,
                                            db_username, db_password)
        self._create_beanstalk_environment(environment_name, db_info,
                                           version_label)

    def _create_rds_instance(self, environment_name, db_name, db_username,
                             db_password):
        logging.info("Creating RDS instance for {}".format(environment_name))
        dbinstance = self.rds.create_dbinstance(environment_name, db_name,
                                                db_username, db_password)
        logging.info("Waiting for RDS instance to start")
        dbinstance = self.rds.wait_for_endpoint(dbinstance)

        return RDSInformation(
            host=dbinstance['Endpoint']['Address'],
            port=dbinstance['Endpoint']['Port'],
            db_name=db_name,
            username=db_username,
            password=db_password)

    def _create_beanstalk_environment(self, environment_name, db_info,
                                      version_label):
        logging.info("Creating Beanstalk environment for {}".format(
            environment_name))
        self.beanstalk.create_configuration_template(
            self.application_name, environment_name,
            source_configuration='default',
            environ={
                'SQLALCHEMY_DATABASE_URI': db_info.sqlalchemy_uri(),
                'RDS_DB_NAME': db_info.db_name,
                'RDS_USERNAME': db_info.username,
                'RDS_PASSWORD': db_info.password,
                'RDS_HOSTNAME': db_info.host,
                'RDS_PORT': db_info.port,
            })
        self.beanstalk.create_environment(
            self.application_name, environment_name, version_label,
            template_name=environment_name)

        logging.info("Giving Beanstalk environment access to RDS instance")
        rds_security_group = self.rds.get_security_group(environment_name)
        self.beanstalk.wait_for_security_group(environment_name)
        eb_security_group = self.beanstalk.get_security_group(environment_name)

        rds_security_group.authorize(
            ip_protocol='tcp',
            from_port=db_info.port,
            to_port=db_info.port,
            src_group=eb_security_group)

    def deploy(self, version_label, environment_short_name):
        environment_name = self._get_env_name(environment_short_name)
        self.beanstalk.update_environment(environment_name, version_label)

    def deploy_latest_to_staging(self):
        version_label = self.get_latest_release_version()
        self.deploy(version_label, 'staging')

    def get_latest_release_version(self):
        versions = self.beanstalk.list_application_versions(
            self.application_name)

        versions = filter(lambda v: v['VersionLabel'].startswith('release-'),
                          versions)
        versions = sorted(versions,
                          key=lambda v: v['DateCreated'],
                          reverse=True)
        if len(versions) == 0:
            raise AWSError('No release versions available')

        return versions[0]['VersionLabel']

    def deploy_staging_to_production(self):
        version_label = self.get_current_staging_version()
        self.deploy(version_label, 'production')

    def get_current_staging_version(self):
        environment_name = self._get_env_name('staging')
        staging = self.beanstalk.describe_environment(self.application_name,
                                                      environment_name)
        return staging['VersionLabel']

    def _get_env_name(self, environment_short_name):
        """Return an environment name

        Generate an environment name from the application name and
        an environment name. Amazon Beanstalk requires environment names to
        be unique across applications so the application name must be
        encoded into the environment name.
        """
        application_hash = hashlib.sha1(self.application_name).hexdigest()[:5]
        return '{}-{}'.format(application_hash, environment_short_name)


_RDSInformation = namedtuple(
    'RDSInformation',
    ['db_name', 'username', 'password', 'host', 'port'])


class RDSInformation(_RDSInformation):
    def sqlalchemy_uri(self):
        return 'postgres://{}:{}@{}:{}/{}'.format(
            self.username, self.password,
            self.host, self.port,
            self.db_name)


class S3Client(object):
    def __init__(self, region, **kwargs):
        self._region = region
        self._options = kwargs
        self._connection = s3.connect_to_region(region)

    def create_bucket(self, application_name):
        logging.info("Creating S3 bucket {} in region {}".format(
            application_name, self._region))
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
        self._connection = beanstalk.connect_to_region(region)
        self._ec2 = EC2Client(region)

    @property
    def solution_stack_name(self):
        return self._options.get(
            'solution_stack_name', DEFAULT_SOLUTION_STACK)

    def create_application(self, application_name):
        logging.info("Creating Beanstalk application {}".format(
            application_name))
        try:
            self._connection.create_application(application_name)
        except BotoServerError as e:
            if self._application_already_exists(e):
                raise ApplicationAlreadyExists(e.message)
            else:
                raise

    def create_environment(self, application_name, environment_name,
                           version_label, template_name):
        self._connection.create_environment(
            application_name, environment_name, version_label,
            template_name=template_name)

    def create_configuration_template(self, application_name, template_name,
                                      solution_stack=None,
                                      source_configuration=None,
                                      option_settings=None,
                                      environ=None):
        logging.info(
            "Creating Beanstalk configuration template {} in {}".format(
                template_name, application_name))
        kwargs = dict()
        if source_configuration is not None:
            if solution_stack is not None:
                raise AWSError('Must select either source config or '
                               'solution stack, not both')
            kwargs['source_configuration_application_name'] = application_name
            kwargs['source_configuration_template_name'] = source_configuration
        elif solution_stack is not None:
            kwargs['solution_stack_name'] = solution_stack
        else:
            raise AWSError('Must select either source config or '
                           'solution stack')

        if option_settings is None:
            option_settings = []
        if environ is not None:
            for key, value in environ.items():
                option_settings.append((
                    'aws:elasticbeanstalk:application:environment',
                    key, value))

        self._connection.create_configuration_template(
            application_name, template_name,
            option_settings=option_settings,
            **kwargs)

    def delete_configuration_template(self, application_name, environment_name):
        logging.info(
            "Deleting configuration template {}".format(environment_name))
        self._connection.delete_configuration_template(application_name,
                                                       environment_name)

    def describe_environment(self, application_name, environment_name):
        for environment in self.list_environments(application_name):
            if environment['EnvironmentName'] == environment_name:
                return environment

    def list_environments(self, application_name):
        response = self._connection.describe_environments(application_name)
        response = response['DescribeEnvironmentsResponse']
        result = response['DescribeEnvironmentsResult']
        environments = result['Environments']

        return environments

    def update_environment(self, environment_name, version_label):
        try:
            logging.info("Updating {} to version {}".format(
                         environment_name, version_label))
            self._connection.update_environment(
                environment_name=environment_name,
                version_label=version_label)
        except BotoServerError as e:
            if self._environment_not_ready(e):
                raise EnvironmentNotReady(e.message)
            else:
                raise

    def terminate_environment(self, environment_name):
        try:
            logging.info(
                "Terminating Beanstalk environment {}".format(environment_name))
            self._connection.terminate_environment(
                environment_name=environment_name)
        except BotoServerError as e:
            if self._cannot_terminate_environment(e):
                raise CannotTerminateEnvironment(e.message)
            else:
                raise

    def list_application_versions(self, application_name):
        response = self._connection.describe_application_versions(
            application_name)
        response = response['DescribeApplicationVersionsResponse']
        result = response['DescribeApplicationVersionsResult']
        versions = result['ApplicationVersions']

        return versions

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

    def wait_for_security_group(self, environment_name):
        while self.get_security_group(environment_name) is None:
            time.sleep(2)

    def get_security_group(self, environment_name):
        resources = self._connection.describe_environment_resources(
            environment_name=environment_name)
        resources = resources['DescribeEnvironmentResourcesResponse']
        resources = resources['DescribeEnvironmentResourcesResult']
        resources = resources['EnvironmentResources']
        resources = resources['Resources']

        for resource in resources:
            if resource['Type'] == 'AWS::EC2::SecurityGroup':
                return self._ec2.get_security_group(
                    resource['PhysicalResourceId'])

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


class EC2Client(object):
    def __init__(self, region):
        self._region = region
        self._connection = ec2.connect_to_region(region)

    def create_security_group(self, name, description):
        security_group = self.get_security_group(name)
        if security_group is None:
            self._connection.create_security_group(
                name,
                'Security group for {} {}'.format(description, name))
            security_group = self.get_security_group(name)

        return security_group

    def get_security_group(self, security_group_name):
        for sg in self._connection.get_all_security_groups():
            if sg.name == security_group_name:
                return sg


class RDSClient(object):
    def __init__(self, region, **kwargs):
        self._region = region
        self._options = kwargs
        self._connection = rds2.connect_to_region(region)
        self._ec2 = EC2Client(region)

    @staticmethod
    def instance_id(environment_name):
        return 'db-{}'.format(environment_name)

    def create_dbinstance(self, environment_name, db_name, username, password):
        instance_id = self.instance_id(environment_name)

        security_group = self._ec2.create_security_group(instance_id,
                                                         'RDS instance')
        try:
            dbinstance = self.get_dbinstance(instance_id)
            if dbinstance is None:
                self._connection.create_db_instance(
                    db_instance_identifier=instance_id,
                    allocated_storage=5,
                    db_instance_class='db.t1.micro',
                    engine='postgres',
                    master_username=username,
                    master_user_password=password,
                    db_name=db_name,
                    backup_retention_period=0,
                    vpc_security_group_ids=[security_group.id],
                )
                dbinstance = self.get_dbinstance(instance_id)
            return dbinstance
        except:
            self.get_security_group(environment_name).delete()
            raise

    def delete_dbinstance(self, environment_name):
        logging.info(
            "Deleting RDS instance {}".format(environment_name))
        instance_id = self.instance_id(environment_name)
        # TODO: We should probably take final snapshots for production databases
        self._connection.delete_db_instance(instance_id,
                                            skip_final_snapshot=True)
        logging.info(
            "Waiting for RDS instance {} to go".format(environment_name))
        self.wait_for_instance_to_go(instance_id)
        self.get_security_group(environment_name).delete()

    def wait_for_endpoint(self, dbinstance):
        while dbinstance.get('Endpoint') is None:
            dbinstance = self.get_dbinstance(dbinstance['DBInstanceIdentifier'])
            time.sleep(10)
        return dbinstance

    def wait_for_instance_to_go(self, instance_id):
        while self.get_dbinstance(instance_id) is not None:
            time.sleep(10)

    def get_dbinstance(self, instance_id):
        dbinstances = self._connection.describe_db_instances()
        dbinstances = dbinstances['DescribeDBInstancesResponse']
        dbinstances = dbinstances['DescribeDBInstancesResult']
        dbinstances = dbinstances['DBInstances']
        for dbinstance in dbinstances:
            if dbinstance['DBInstanceIdentifier'] == instance_id:
                return dbinstance

    def get_security_group(self, environment_name):
        return self._ec2.get_security_group(self.instance_id(environment_name))


class AWSError(StandardError):
    pass


class ApplicationAlreadyExists(AWSError):
    pass


class CannotTerminateEnvironment(AWSError):
    pass


class EnvironmentNotReady(AWSError):
    pass
