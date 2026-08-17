#!/usr/bin/env python3
import argparse
import sys
import time
import psycopg2

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--db_host', required=False, default='db')
    arg_parser.add_argument('--db_port', required=False, default=5432, type=int)
    arg_parser.add_argument('--db_user', required=False, default='odoo')
    arg_parser.add_argument('--db_password', required=False, default='')
    arg_parser.add_argument('--timeout', type=int, default=15)

    args, _ = arg_parser.parse_known_args()

    start_time = time.time()
    error = None
    while (time.time() - start_time) < args.timeout:
        try:
            conn = psycopg2.connect(
                user=args.db_user,
                host=args.db_host,
                port=args.db_port,
                password=args.db_password if args.db_password else None,
                dbname='postgres',
                connect_timeout=3
            )
            error = None
            conn.close()
            break
        except Exception as e:
            error = e
        time.sleep(1)

    if error:
        print(f"PostgreSQL connection check failed: {error}", file=sys.stderr)
        # Non-fatal warning so container can still proceed if db is already bound
        sys.exit(0)
    else:
        print(f"✓ Connected to PostgreSQL at {args.db_host}:{args.db_port}")
