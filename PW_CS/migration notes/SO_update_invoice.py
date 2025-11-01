from pw_cli import Client, Env
# from odoo import api, fields, models, _

source_connection = Client(server='http://localhost:8069', db='PW3.0-BSM', user='admin.synercatalyst', password='Wengseng1@')

sale_order_line_obj = source_connection.env['sale.order.line'].search([('state', '=', 'sale')])

for line in sale_order_line_obj:
    print('SALES ORDER lINE')
    print(line.order_id.name, line.name)
    if line.invoice_lines:
        print('INVOICE LINES')
        for inv_lines in line.invoice_lines:
            print('UPDATE INVOICE LINE')
            inv_lines.name = line.name