# Command line interface to deployment
import argh

from digitalmarketplace.deploy import aws


def get_client(region):
    return aws.Client(region)


def bootstrap(region=None):
    """Create a new application with associated S3 bucket and core environments"""
    get_client(region).bootstrap()


def create_version(version_label, region=None):
    """Create a new version of the application from the current HEAD"""
    get_client(region).create_version(version_label)


def deploy_to_branch_environment(branch, region=None):
    """Deploy the current HEAD to a temporary branch environment"""
    get_client(region).deploy_to_branch_environment(branch)


def terminate_branch_environment(branch, region=None):
    """Terminate a temporary branch environment"""
    get_client(region).terminate_branch_environment(branch)


def deploy_to_staging(version_label, region=None):
    """Deploy a previously created version to the staging environment"""
    get_client(region).deploy(version_label, 'staging')


def deploy_to_production(version_label, region=None):
    """Deploy a previously created version to the production environment"""
    get_client(region).deploy(version_label, 'production')


def main():
    parser = argh.ArghParser()
    parser.add_argument('--region', default='eu-west-1')
    parser.add_commands([
        bootstrap,
        create_version,
        deploy_to_branch_environment,
        terminate_branch_environment,
        deploy_to_staging,
        deploy_to_production])
    parser.dispatch()

if __name__ == '__main__':
    main()
