from setuptools import setup, find_packages

setup(name='pydotsim',
      version='0.0.1',
      description='',
      author='Kenneth Yin',
      author_email='kyin98@yahoo.com',
      packages=find_packages(),
      install_requires=["pydot==1.2.2",
                        "ipython==8.10.0",
                        "ipdb==0.9.3",
                        "ipaddress==1.0.22"],
      zip_safe=False
)
