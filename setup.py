from setuptools import setup, find_packages

setup(
    name='hodl-net',
    version='2.0',
    description='HODL network',
    author='hodleum',
    packages=find_packages(),
    package_data={'': ['config/*.toml']},
    include_package_data=True,
    install_requires=['twisted',
                      'werkzeug',
                      'attrs',
                      'pycryptodome',
                      'sqlalchemy',
                      'toml',
                      'upnpclient'
                      ]
)
