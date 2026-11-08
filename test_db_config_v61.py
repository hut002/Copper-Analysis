"""Offline deterministic configuration tests; no external database connection."""
import os
from unittest.mock import patch
import cloud_db


def run():
    names=['DATABASE_URL','DB_HOST','DB_PORT','DB_NAME','DB_USER','DB_PASSWORD']
    with patch.dict(os.environ,{x:'' for x in names}):
        with patch.object(cloud_db,'_secret_value', side_effect=lambda n, default=None: {'DB_HOST':'example.pooler.supabase.com','DB_PORT':'5432','DB_NAME':'postgres','DB_USER':'postgres.ref','DB_PASSWORD':'p@:# % /?++'}.get(n,default)):
            opts=cloud_db.connection_options()
            assert opts['password']=='p@:# % /?++'
            assert opts['port']==5432 and opts['sslmode']=='require'
        with patch.object(cloud_db,'_secret_value',side_effect=lambda n, default=None: None):
            try:cloud_db.connection_options()
            except cloud_db.DatabaseConfigError as e:assert 'DB_CONFIG' in str(e)
            else:raise AssertionError('Expected DB_CONFIG error')
    cases=[('FATAL: password authentication failed for user "postgres"','DB_AUTH'),('could not translate host name','DB_DNS'),('connection timed out','DB_TIMEOUT'),('Tenant or user not found','DB_POOLER_USER'),('ssl certificate issue','DB_TLS')]
    for msg,expected in cases:
        assert cloud_db.classify_connection_error(RuntimeError(msg)).startswith(expected)
        assert 'postgres"' not in cloud_db.classify_connection_error(RuntimeError(msg))
    print('PASS: structured DB options, special characters, secret omission, error codes')

if __name__=='__main__':run()
