#!/usr/bin/env python

from app import beanstalk

if __name__ == '__main__':

	my_beanstalk = beanstalk.Beanstalk()
	my_beanstalk.create_application("my-app")
	my_beanstalk.create_application_version("my-app")
	my_beanstalk.create_environment("my-app", "my-environment")
	#my_beanstalk.delete_application("my-app")
