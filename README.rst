Digital Marketplace deployment tool
===================================

A deployment tool for deploying Digital Marketplace applications to Beanstalk.


Getting started
---------------

Installation
~~~~~~~~~~~~

Install with pip::

  pip install git+https://github.com/alphagov/digitalmarketplace-deployment.git

``dm-deploy`` uses `boto`_ under the hood. AWS credentials can be provided to
boto in few different ways, check their `config tutorial`_ for more information.
At the minimum you will need an access key ID and a secret access key.

View the ``dm-deploy`` help to verify the installation::

  dm-deploy --help

Navigate into the project you want to deploy::

  cd ../digitalmarketplace-api

Bootstrapping
~~~~~~~~~~~~~

If your project has not been set up in Beanstalk yet you will have to ``bootstrap`` it.
This will create:

- An `S3 bucket`_ for storing `application versions <#application-version>`_
- A `Beanstalk application`_ named after the Github repo
- A `Beanstalk configuration template <#configuration-template>`_ named ``default``

For each environment it will create:

- A security group for the `RDS instance`_ named ``db-{app sha}-{environment name}``
- An `RDS instance`_ named ``db-{app sha}-{environment name}``
- A `Beanstalk configuration template <#configuration-template>`_ inheriting from ``default`` with the
  RDS database details.
- A `Beanstalk environment`_ named ``{app sha}-{environment name}``

Environment variables can be added to the ``default`` configuration template from
the current environment with the ``--proxy-env`` argument. In the example below the
``FOO`` and ``BAR`` environment variables will be taken from the current
environment and added to the configuration template::

  dm-deploy bootstrap --proxy-env='FOO,BAR'

Ephemeral environments
~~~~~~~~~~~~~~~~~~~~~~

To create an ephemeral environment for a feature branch use the 
``deploy-to-branch-environment`` command. This will create a development version,
a development environment with that version and an associated RDS instance. If
a branch is not explicitly provided then the current branch name will be used::

  dm-deploy deploy-to-branch-environment

When the ephemeral environment is no longer needed it can be removed with
the ``terminate-branch-environment`` command. If a branch is not explicitly
provided then the current branch name will be used::

  dm-deploy terminate-branch-environment

Deployment
~~~~~~~~~~

When we want to deploy a new version of the application to staging or production
we need to explicitly create a new version with the ``create-version`` command.
The new version will be created from the current ``HEAD``::

  dm-deploy create-version release-1234

Once we have a version label of the form ``release-{ something }`` we can deploy
it to staging and production. The following command will deploy the most recent
'release' version to the staging environment::

  dm-deploy deploy-latest-to-staging

Then we can deploy the version that is currently deployed to staging up to
production::

  dm-deploy deploy-staging-to-production


AWS Elements
------------

Beanstalk application
~~~~~~~~~~~~~~~~~~~~~

`AWS documentation <http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#application>`_

Named the same as the Github application; it is derived from the git remote
origin URL. Contains `Beanstalk environments <#beanstalk-environment>`_.

S3 bucket
~~~~~~~~~

`AWS documentation <http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#bucket>`_

For each application there is an S3 bucket with the same name as the application
used for storing the `Application version`_ packages.

.. note::
  This S3 bucket must be in the same `AWS region`_ as the Beanstalk application.

Beanstalk environment
~~~~~~~~~~~~~~~~~~~~~

`AWS documentation <http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#environment>`_

Beanstalk environments are named ``{app sha}-{environment short name}``.
``{app sha}`` is a short unique identifier for the application, this is needed
because environment names must be unique across all Beanstalk applications.
``{environment short name}`` is the environment name we use; for example
``staging`` or ``production`` for our permanent environments or ``dev-{label}``
for ephemeral environments.

Each environment has it's own RDS instance associated with it, see
`RDS instance`_.

Each environment has a configuration template called ``{environment name}``,
see `Configuration template`_.

RDS instance
~~~~~~~~~~~~

`AWS documentation <http://aws.amazon.com/rds/>`_

An RDS instance is created for each environment and named ``db-{environment name}``.
The associated Beanstalk environment is given access to this via a `Security group`_
also called ``db-{environment name}``.

.. note::
  The RDS instance and security group are not otherwise tied to the Beanstalk
  environment and therefore need to be manually removed or unlinked (via the
  security group) from the environment before it is terminated.

Configuration template
~~~~~~~~~~~~~~~~~~~~~~

`AWS documentation <http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-beanstalk-configurationtemplate.html>`_

When a new application is bootstrapped a configuration template called
``default`` is created and local environment variables can optionally be
added to it. A configuration template inheriting from this one is also created
for each environment which contains the RDS details (connection information
and credentials).

Application version
~~~~~~~~~~~~~~~~~~~

`AWS documentation <http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#appversion>`_

An application version is a package (zip file stored in S3) containing
application code with an associated version label. The package files are named
after the full git commit sha that they represent. When bootstrapping an
application a version called ``initial`` is created all other versions are
named as follows:

- Release versions should be called ``release-{build number}``.
- Ephemeral versions will be called ``dev-{label}-{short commit sha}``.

.. note::
  Version names have a length limit of 100 characters.


.. _boto: https://github.com/boto/boto
.. _config tutorial: http://boto.readthedocs.org/en/latest/boto_config_tut.html
.. _AWS region: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#region
.. _Security group: http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_SecurityGroups.html
