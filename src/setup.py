from setuptools import setup, find_packages

setup(
    name='cstation',
    version='0.1.4',
    packages=find_packages(),
    install_requires=[
        'click',
        'auto_click_auto',
        'ansible',
        'gitoo'
    ],
    entry_points={
        'console_scripts': [
            'cstation = cstation:cli',
        ],
    },
)