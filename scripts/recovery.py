"""CLI for encrypted whole-instance backups. Never overwrites a restore target."""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'traceform'))
from recovery import backup,restore

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    b=sub.add_parser('backup');b.add_argument('--output',required=True);b.add_argument('--master-key-file',required=True)
    r=sub.add_parser('restore');r.add_argument('--bundle',required=True)
    for child in (b,r):
        child.add_argument('--url-file',required=True,help='Private file containing an async SQLAlchemy database URL')
        child.add_argument('--storage',required=True);child.add_argument('--key-file',required=True)
        child.add_argument('--confirm-stopped',action='store_true',help='API/workers are stopped for this source or restore target')
    args=parser.parse_args();url=Path(args.url_file).read_text().strip()
    try:
        if args.operation=='backup':result=asyncio.run(backup(url,args.storage,args.master_key_file,args.output,args.key_file,args.confirm_stopped))
        else:result=asyncio.run(restore(args.bundle,args.key_file,url,args.storage,args.confirm_stopped))
        print(json.dumps(result,indent=2))
    except Exception as exc:
        # Driver errors may contain database credentials. Do not print them.
        print(json.dumps({'status':'failed','type':type(exc).__name__,'message':str(exc) if isinstance(exc,ValueError) else 'Recovery failed; verify the key, target and database connectivity.'}));sys.exit(1)
