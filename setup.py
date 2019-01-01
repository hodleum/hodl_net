from setuptools import setup, find_packages

setup(
    name='hodl_db',
    version='0.1',
    description='HODL network',
    author='hodleum',
    packages=find_packages(),
    install_requires=['twisted', 'werkzeug', 'attrs']
)
