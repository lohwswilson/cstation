from setuptools import setup, find_packages

setup(
    name='cstation',
    version='0.1.12',
    py_modules=['cstation'],
    packages=find_packages(),
    url="https://github.com/ansis-ai/cstation.git",
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'cstation = cstation:cli',
        ],
    },
)