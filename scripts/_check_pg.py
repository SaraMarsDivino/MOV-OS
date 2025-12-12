import psycopg2
hosts = ['127.0.0.1', 'localhost', '::1']
for host in hosts:
    try:
        print('Trying', host)
        conn = psycopg2.connect(dbname='movos', user='postgres', password='postgres', host=host, port=5433, connect_timeout=5)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        print('OK', host, cur.fetchone())
        cur.close()
        conn.close()
    except Exception as e:
        print('ERR', host, type(e).__name__, e)
