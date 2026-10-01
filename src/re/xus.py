import struct,sys
def load(p):
    d=open(p,'rb').read(); n=struct.unpack_from('>H',d,10)[0]; o=12; out=[]
    for i in range(n):
        l=struct.unpack_from('>H',d,o)[0]; out.append(d[o+2:o+2+2*l].decode('utf-16be')); o+=2+2*l
    return out
if __name__=="__main__":
    for i,s in enumerate(load(sys.argv[1])): print(i, repr(s))
