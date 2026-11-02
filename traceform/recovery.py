"""Encrypted, checksummed, portable recovery bundles. Writers must be stopped first."""
import asyncio,base64,enum,hashlib,io,json,os,zipfile
from datetime import datetime,date
from pathlib import Path,PurePosixPath
from uuid import UUID
from cryptography.fernet import Fernet
from sqlalchemy import select,inspect,Enum,DateTime,Date,LargeBinary
from sqlalchemy.ext.asyncio import create_async_engine
from db.models import Base,DurableJob
from db.migrate import migrate

MAX_BYTES=256*1024*1024
def sha(value):return hashlib.sha256(value).hexdigest()
def encode(value):
    if isinstance(value,enum.Enum):return value.name
    if isinstance(value,(datetime,date,UUID)):return str(value)
    if isinstance(value,bytes):return {'$binary':base64.b64encode(value).decode()}
    raise TypeError(type(value).__name__)
def decode(column,value):
    if value is None:return None
    t=column.type
    if isinstance(t,Enum) and t.enum_class:
        return t.enum_class.__members__.get(value) or t.enum_class(value)
    if isinstance(t,DateTime):return datetime.fromisoformat(value)
    if isinstance(t,Date):return date.fromisoformat(value)
    if isinstance(t,LargeBinary):return base64.b64decode(value['$binary'],validate=True)
    if getattr(t,'as_uuid',False):return UUID(value)
    return value
def engine_for(url):return create_async_engine(url,connect_args={'timeout':30} if url.startswith('sqlite') else {})
def key(path):return Fernet(Path(path).read_bytes().strip())
def safe_name(name):
    path=PurePosixPath(name)
    if not name or str(path)!=name or path.is_absolute() or '\\' in name or ':' in name or any(p in {'..','.'} for p in path.parts):raise ValueError('Unsafe archive path.')
    return path

async def backup(url,storage,master_key_file,output,key_file,confirm_stopped=False):
    if not confirm_stopped:raise ValueError('Stop API and workers, then confirm the maintenance window.')
    root=Path(storage).resolve();out=Path(output).resolve()
    if out.exists():raise ValueError('Backup destination already exists.')
    if not root.is_dir():raise ValueError('Storage directory is missing.')
    master=Path(master_key_file).read_bytes().strip();Fernet(master)
    cipher=key(key_file);engine=engine_for(url)
    try:
        async with engine.connect() as connection:
            if engine.dialect.name=='postgresql':connection=await connection.execution_options(isolation_level='REPEATABLE READ')
            async with connection.begin():
                from sqlalchemy import text
                revision=await connection.scalar(text('SELECT version_num FROM alembic_version'))
                names=await connection.run_sync(lambda c:set(inspect(c).get_table_names()))
                if names!=set(Base.metadata.tables)|{'alembic_version'}:raise ValueError('Database schema differs from the supported application tables.')
                active=await connection.scalar(select(DurableJob.generation_id).where(DurableJob.status.in_(['queued','running'])).limit(1))
                if active:raise ValueError('Queued/running jobs must finish or be cancelled before backup.')
                tables={table.name:[dict(r) for r in (await connection.execute(select(table))).mappings().all()] for table in Base.metadata.sorted_tables}
        entries={};total=0
        for path in root.rglob('*'):
            if path.is_symlink():raise ValueError('Storage symlinks are not supported.')
            if not path.is_file():continue
            relative=path.relative_to(root)
            if relative.parts[0]=='backups' or path.resolve() in {out,Path(key_file).resolve(),Path(master_key_file).resolve()}:continue
            content=path.read_bytes();total+=len(content)
            if total>MAX_BYTES:raise ValueError('Bundle exceeds the 256 MiB supported limit.')
            entries['storage/'+relative.as_posix()]=content
        references=[]
        for table_name,column in [('sources','raw_content_ref'),('artifacts','rendered_file_ref')]:
            for row in tables[table_name]:
                value=row[column]
                if not value:continue
                path=Path(value)
                if not path.is_absolute():
                    options=[root/path,root.parent/path]
                    path=next((p for p in options if p.is_file()),options[0])
                path=path.resolve()
                if not path.is_relative_to(root):raise ValueError('A stored file reference is outside the configured storage directory.')
                rel=path.relative_to(root).as_posix()
                if 'storage/'+rel not in entries:raise ValueError('A referenced source/output file is missing from storage.')
                references.append({'table':table_name,'id':str(row['id']),'column':column,'path':rel})
        data=json.dumps(tables,default=encode,ensure_ascii=False,allow_nan=False,sort_keys=True).encode()
        entries['database.json']=data;entries['secrets/provider-master-key']=master
        manifest={'format':'traceform-recovery:1','revision':revision,'counts':{name:len(rows) for name,rows in tables.items()},
            'files':{name:sha(content) for name,content in entries.items()},'references':references}
        if sum(len(c) for c in entries.values())+len(json.dumps(manifest).encode())>MAX_BYTES:raise ValueError('Bundle exceeds the supported limit.')
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,content in entries.items():archive.writestr(name,content)
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
        if buffer.tell()>MAX_BYTES:raise ValueError('Bundle exceeds the supported limit.')
        # Detect concurrent file writes during the maintenance snapshot.
        for name,content in entries.items():
            if name.startswith('storage/') and sha((root/name[8:]).read_bytes())!=sha(content):raise ValueError('Storage changed during backup.')
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as stream:stream.write(cipher.encrypt(buffer.getvalue()))
        os.chmod(out,0o600)
        return {'format':manifest['format'],'revision':revision,'counts':manifest['counts'],'sha256':sha(out.read_bytes())}
    finally:await engine.dispose()

def read_bundle(bundle,key_file):
    path=Path(bundle)
    if path.stat().st_size>MAX_BYTES*2:raise ValueError('Encrypted bundle exceeds the supported limit.')
    raw=key(key_file).decrypt(path.read_bytes())
    archive=zipfile.ZipFile(io.BytesIO(raw));names=archive.namelist()
    if len(set(names))!=len(names) or sum(i.file_size for i in archive.infolist())>MAX_BYTES:raise ValueError('Invalid or oversized bundle.')
    for name in names:safe_name(name)
    entries={name:archive.read(name) for name in names};manifest=json.loads(entries.pop('manifest.json'))
    if manifest.get('format')!='traceform-recovery:1' or set(entries)!=set(manifest['files']):raise ValueError('Unsupported/incomplete bundle.')
    if any(sha(content)!=manifest['files'][name] for name,content in entries.items()):raise ValueError('Bundle checksum mismatch.')
    return manifest,entries

async def restore(bundle,key_file,url,storage,confirm_stopped=False):
    if not confirm_stopped:raise ValueError('Confirm that the restore target has no running API/workers.')
    manifest,entries=read_bundle(bundle,key_file);root=Path(storage).resolve()
    if root.exists() and any(root.iterdir()):raise ValueError('Restore storage must be empty.')
    from sqlalchemy.engine import make_url
    parsed=make_url(url)
    if parsed.drivername.startswith('sqlite') and Path(parsed.database).exists():raise ValueError('Restore database must be new, not an existing SQLite file.')
    tables=json.loads(entries['database.json'])
    if set(tables)!=set(Base.metadata.tables):raise ValueError('Bundle tables do not match this application version.')
    for name,rows in tables.items():
        if len(rows)!=manifest['counts'][name]:raise ValueError('Bundle row counts do not match.')
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config=Config();config.set_main_option('script_location',str(Path(__file__).parent/'db/migrations'))
    if manifest['revision']!=ScriptDirectory.from_config(config).get_current_head():raise ValueError('Use the application version matching this backup before migrating it.')
    for ref in manifest['references']:
        safe_name(ref['path'])
        if 'storage/'+ref['path'] not in entries:raise ValueError('Missing referenced storage file.')
        row=next(r for r in tables[ref['table']] if r['id']==ref['id'])
        row[ref['column']]=ref['path']
    engine=engine_for(url)
    try:
        async with engine.connect() as connection:
            existing=await connection.run_sync(lambda c:inspect(c).get_table_names())
            if existing:raise ValueError('Restore database must contain no application tables.')
        await migrate(engine)
        async with engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                rows=[{c.name:decode(c,row[c.name]) for c in table.columns} for row in tables[table.name]]
                self_keys=[fk.parent.name for fk in table.foreign_keys if fk.column.table.name==table.name]
                if self_keys:
                    inserted=set()
                    while rows:
                        ready=[row for row in rows if all(row[name] is None or row[name] in inserted for name in self_keys)]
                        if not ready:raise ValueError('Invalid cyclic self-references in backup.')
                        await connection.execute(table.insert(),ready)
                        inserted.update(row['id'] for row in ready);rows=[r for r in rows if r not in ready]
                elif rows:await connection.execute(table.insert(),rows)
        root.mkdir(parents=True,exist_ok=True)
        for name,content in entries.items():
            if not name.startswith('storage/'):continue
            destination=root/name[8:];destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
        (root/'.provider-master-key').write_bytes(entries['secrets/provider-master-key']);os.chmod(root/'.provider-master-key',0o600)
        async with engine.connect() as connection:
            counts={table.name:await connection.scalar(select(__import__('sqlalchemy').func.count()).select_from(table)) for table in Base.metadata.sorted_tables}
        if counts!=manifest['counts']:raise ValueError('Restored row counts differ from the backup.')
        return {'format':manifest['format'],'revision':manifest['revision'],'counts':counts,'verified':True}
    finally:await engine.dispose()
