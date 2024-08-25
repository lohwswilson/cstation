# These are the CLI Scripts/Tools for Servers Operations

To start using these scripts, you need to clone this repository, got to directory cstation and run the `pip install -e .` script.


[//]: # (addons)

Commands Structure for ControlStation (cstation)
----------------
- *container*
  - deploy

- *github*
  - oca_rebuild
    - Rebuild OCA modules from github
  
  - repo_sync
    - Syncing repositories with upstream

- *odoo*
    Setting Up Odoo 16 or above Repositories
  - *_local_*: Configure Odoo for Local Host Development Operations
  - _*server*_:  Configure Odoo version => 16.0 for Remote Server

- *perfectwork*
  - *_local_*: Configure PerfectWORK for Local Development Operations
  - _*server*_: Configure PerfectWORK for Remote Server

- *perfectwork6*
  - *_local_*: Configure PerfectWORK for Local Development Operations
  - _*server*_:  Configure PerfectWORK => 6.0 for Remote Server


Usage: cstation [OPTIONS] COMMAND [ARGS]...

  Control Station
  A wrapper around ansible for Deployment

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  container     Control Station Docker Container Operations and Deployments
  github        Control Station - Managing GITHUB Account
  odoo          Control Station Setting Up Odoo 16 or above Repositories
  perfectwork   Control Station Setting Up PerfectWORK Repositories
  perfectwork6  Control Station Setting Up PerfectWORK => 6.0 Repositories


[//]: # (end addons)


## Prepare Odoo Codebase

### For Local Development Server

We can use the following script to prepare the Odoo codebase for local development server:

    Prepare Odoo 16.0 for local development

    ```
    $ cd cstation
    $ cstation odoo local 16.0
    ```

    The Odoo 16.0 codebase will be cloned and prepared for local development at _/opt/PW/Odoo.16.0
    

### For Production Server

We can use the following script to prepare the Odoo codebase for production server:

    Prepare Odoo 16.0 for production server

    ```
    $ cd cstation
    $ cstation odoo server 16.0
    ```

    The Odoo 16.0 codebase will be cloned and prepared for production server.
