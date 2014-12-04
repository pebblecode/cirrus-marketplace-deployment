Digital Marketplace deployment tool
===================================

A deployment tool for deploying Digital Marketplace applications to Beanstalk.


Getting started
---------------

Install with pip::

  pip install git+https:/github.com/alphagov/digitalmarketplace-deployment

View the ``dm-deploy`` help to verify the installation::

  dm-deploy --help

Navigate into the project you want to deploy::

  cd ../digitalmarketplace-api

If this project has not been set up in Beanstalk yet you will have to ``bootstrap`` it.
This will create an S3 bucket for storing the application packages and create a
Beanstalk application with two environments (one for staging, one for production)
set to an initial version. You do not need to provide an application name as that
is taken from the git URL::

  dm-deploy bootstrap

To create an ephemeral environment for a feature branch use the 
``deploy-to-branch-environment`` command. This will create a development version
and a development environment with that version. If a branch is not explicitly
provided then the current branch name will be used::

  dm-deploy deploy-to-branch-environment

When the ephemeral environment is no longer needed it can be removed with
the ``terminate-branch-environment`` command. If a branch is not explicitly
provided then the current branch name will be used::

  dm-deploy terminate-branch-environment

When we want to deploy a new version of the application to staging or production
we need to explicitly create a new version with the ``create-version`` command.
The new version will be created from the current ``HEAD``::

  dm-deploy create-version 1234

Once we have a version label we can deploy it to staging or production::

  dm-deploy deploy-to-staging 1234


AWS Elements
------------

The `Beanstalk application`_ is named the same as the github repository; it is
derived from the git remote origin URL.

For each application there is an `S3 bucket`_ with the same name used for
storing the `application version`_ packages. Note that this S3 bucket must be
in the same `AWS region`_ as the Beanstalk application. Packages are zip files
at a point in the git tree. As such they are named after the full commit sha
that they represent.

When a new application is bootstrapped two `Beanstalk environments`_ are created. These are
named ``{app sha}-staging`` and ``{app sha}-production``. The ``{app sha}`` is a
short unique identifier for the application. This is needed because Beanstalk
environment names must be unique across all your applications. A new version
called ``initial`` is created for these two new environments.

Subsequent versions can be named whatever you like, so long as the name has not
already been used. Strangely version labels do not have to be unique across
all your applications.

Ephemeral environments can also be created for features or experiments. Usually
these would be done from a feature branch but they do not have to be. When
an application is deployed to a new ephemeral environment a new version label
is created named ``dev-{label}-{short commit sha}``. The ``{label}`` is set to the
branch name if none is provided and the ``{short commit sha}`` is the commit sha
truncated to 7 characters. An environment is also created (or updated if it
already exists) with the name ``{app sha}-dev-{label}`` where the ``{app sha}`` is
the same as for the staging and production environments and the ``{label}`` is
the same as for the version label.

.. _S3 bucket: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#bucket
.. _Beanstalk application: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#application
.. _application version: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#appversion
.. _AWS region: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#region
.. _Beanstalk environments: http://docs.aws.amazon.com/general/latest/gr/glos-chap.html#environment