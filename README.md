# These are the SYC Ops Scripts/Tools for Servers Operations

To start using these scripts, you need to clone this repository, got to directory cstation and run the `pip install -e .` script.


[//]: # (addons)

Commands Structure for ControlStation (cstation)
----------------
| Commands | Arguments | Options | Summary |
| -------- | --------- | --------| --------|
| odoo     |  local |  --version __{Odoo version}__ | Build Odoo._version_ folder in local development server <br><br> _XX_ {Odoo version} : 16.0, 17.0  <br><br>  ```cstation odoo local --version 16.0 ``` |



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
