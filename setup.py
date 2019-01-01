from setuptools import setup, find_packages

setup(
    name='hodl_net',
    version='0.1',
    description='HODL network',
    author='hodleum',
    packages=find_packages(),
    install_requires=['twisted', 'werkzeug', 'attrs']
)
