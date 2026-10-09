import sqlite3, zipfile, tempfile, datetime, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data';out=ROOT/'backups';out.mkdir(exist_ok=True)
if not (DATA/'flylink.sqlite3').exists():raise SystemExit('请先启动平台创建数据库。')
name='FlyLink-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip'
with tempfile.TemporaryDirectory() as tmp:
    db=Path(tmp)/'flylink.sqlite3'
    with sqlite3.connect(DATA/'flylink.sqlite3') as src,sqlite3.connect(db) as dst:src.backup(dst)
    with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(db,'data/flylink.sqlite3')
        for f in DATA.rglob('*'):
            if f.is_file() and f.name!='flylink.sqlite3' and not f.name.endswith(('-wal','-shm','-journal')):z.write(f,str(f.relative_to(ROOT)))
print('备份已生成：',out/name)
