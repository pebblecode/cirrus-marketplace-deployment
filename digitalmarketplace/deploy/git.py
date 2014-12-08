# Git helper functions for deployment
import re
import subprocess

SSH_REPO_PATTERN = re.compile('git@[^:]*:[^/]+/(.*)\.git')
HTTPS_REPO_PATTERN = re.compile('https://[^/]+/[^/]+/(.*)/(?:.git)?')


def get_repo_url():
    return subprocess.check_output(
        ['git', 'config', 'remote.origin.url']).strip()


def get_application_name():
    repo_url = get_repo_url()
    match = SSH_REPO_PATTERN.match(repo_url)
    if not match:
        match = HTTPS_REPO_PATTERN.match(repo_url)
    return match.group(1)


def get_current_sha():
    return subprocess.check_output(
        ['git', 'rev-parse', 'HEAD']).strip()


def get_current_ref():
    return subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip()


def get_current_branch():
    branch = get_current_ref()
    if branch in ['HEAD', 'master']:
        raise StandardError('Not on a feature branch; on {}'.format(branch))
    return branch


def create_package():
    sha = get_current_sha()
    file_path = '/tmp/{}.zip'.format(sha)

    with open(file_path, 'w+') as package_file:
        subprocess.call(
            ['git', 'archive', '--format=zip', 'HEAD'],
            stdout=package_file)

    return sha, file_path
