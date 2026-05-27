import gzip, shutil, os
src='movos_dump.sql.gz'
dst='movos_dump.sql'
if not os.path.exists(src):
    print('ERROR: movos_dump.sql.gz not found')
else:
    with gzip.open(src,'rb') as f_in, open(dst,'wb') as f_out:
        shutil.copyfileobj(f_in,f_out)
    print('Created', dst)
