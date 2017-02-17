from setuptools import setup

setup(
    name='kitsh',
    version='0.1.0',
    author='Harry Roberts',
    packages=[
        'kitsh'
        ],
    package_data={'': ['static/*', 'templates/*']},
    include_package_data=True,
    zip_safe=False
)
