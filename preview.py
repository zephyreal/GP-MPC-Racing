"""Development preview entry; accepts the standard preview daemon's Vite-style arguments."""
import argparse,os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8020);parser.add_argument('--strictPort',action='store_true');args=parser.parse_args()
import uvicorn
uvicorn.run('gp_mpc_racing.demo:app',host=args.host,port=args.port)
