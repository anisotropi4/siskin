from setuptools import find_packages, setup

setup(
    name='herbert',
    packages=find_packages(include=['herbert']),
    version='0.2.0',
    description='Population visualisation helper functions library ',
    author='Will Deakin',
    setup_requires=['pytest-runner'],
    tests_require=['pytest==4.4.1'],
    test_suite='tests',
    license='MIT',
)
