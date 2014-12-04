from boto import beanstalk


class Beanstalk():
    eu_west = "eu-west-1"
    stack = "64bit Amazon Linux 2014.03 v1.0.9 running Python 2.7"
    connection = None

    def __init__(self):
        self.connection = beanstalk.connect_to_region(self.eu_west)

    def create_application(self, name=None):
        try:
            self.connection.create_application(name)
        except Exception as e:
            print "Application %s already exists %s" % (name, e)

    def create_application_version(self, name=None, auto_create=False):
        self.connection.create_application_version(name, "version-1", "description", "digitalmarketplace-api-deployments", "digitalmarketplace-api.zip", auto_create)

    # def create_configuration_template(self, name=None, template_name=None):
    #     print "create_template"
    #     self.connection.create_configuration_template(name, template_name, self.stack, name, )

    def create_environment(self, name=None, environment_name=None):
         self.connection.create_environment(application_name=name, environment_name=environment_name, version_label="version-1", solution_stack_name=self.stack)

    def delete_application(self, name=None, terminate_env_by_force=True):
        self.connection.delete_application(name, terminate_env_by_force)

    def check_dns_availability(self, name=None):
        if self.connection.check_dns_availability(name):
            print "%s is available" % name
            return True
        else:
            print "%s is not available " % name
            return False
