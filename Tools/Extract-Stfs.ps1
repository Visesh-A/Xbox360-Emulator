# Extracts files from an Xbox 360 STFS package (PIRS / LIVE / CON), e.g. system update su20076000_00000000.
param(
    [Parameter(Mandatory)] [string]$Package,
    [Parameter(Mandatory)] [string]$OutDir
)

Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Collections.Generic;

public static class Stfs {
    static byte[] d;
    static int sex;          // 0 = female (read-only packages), 1 = male
    static long firstHash;

    static int U24LE(int o) { return d[o] | (d[o+1] << 8) | (d[o+2] << 16); }
    static int U24BE(int o) { return (d[o] << 16) | (d[o+1] << 8) | d[o+2]; }
    static int U16BE(int o) { return (d[o] << 8) | d[o+1]; }
    static uint U32BE(int o) { return (uint)((d[o] << 24) | (d[o+1] << 16) | (d[o+2] << 8) | d[o+3]); }

    static long BackingDataBlock(long b) {
        long r = (((b + 0xAA) / 0xAA) << sex) + b;
        if (b < 0xAA) return r;
        if (b < 0x70E4) return r + (((b + 0x70E4) / 0x70E4) << sex);
        return (1L << sex) + r + (((b + 0x70E4) / 0x70E4) << sex);
    }
    static long BlockAddr(long b) { return (BackingDataBlock(b) << 12) + firstHash; }

    static long Level0HashBlock(long b) {
        if (b < 0xAA) return 0;
        long step = sex == 0 ? 0xAB : 0xAC;
        long n = (b / 0xAA) * step;
        n += ((b / 0x70E4) + 1) << sex;
        if (b / 0x70E4 == 0) return n;
        return n + (1L << sex);
    }
    static int NextBlock(long b) {
        long addr = (Level0HashBlock(b) << 12) + firstHash + (b % 0xAA) * 0x18;
        return U24BE((int)addr + 0x15);
    }

    public static string Extract(string pkg, string outDir) {
        d = File.ReadAllBytes(pkg);
        uint headerSize = U32BE(0x340);
        firstHash = (headerSize + 0xFFF) & 0xFFFFF000;
        sex = (~d[0x37B]) & 1;
        int ftCount = d[0x37C] | (d[0x37D] << 8);
        int ftBlock = U24LE(0x37E);

        var entries = new List<int>();
        int blk = ftBlock;
        for (int i = 0; i < ftCount; i++) {
            long a = BlockAddr(blk);
            for (int e = 0; e < 0x40; e++) entries.Add((int)a + e * 0x40);
            blk = NextBlock(blk);
        }

        var names = new List<string>();
        var dirs = new Dictionary<int, string>();
        var log = new System.Text.StringBuilder();
        int idx = 0;
        foreach (int o in entries) {
            int flags = d[o + 0x28];
            int nameLen = flags & 0x3F;
            if (nameLen == 0) { idx++; continue; }
            string name = System.Text.Encoding.ASCII.GetString(d, o, nameLen);
            bool isDir = (flags & 0x80) != 0;
            bool consecutive = (flags & 0x40) != 0;
            int startBlock = U24LE(o + 0x2F);
            int parent = (short)U16BE(o + 0x32);
            int size = (int)U32BE(o + 0x34);

            string rel = (parent == -1 || parent == 0xFFFF || !dirs.ContainsKey(parent)) ? name : Path.Combine(dirs[parent], name);
            if (isDir) {
                dirs[idx] = rel;
                Directory.CreateDirectory(Path.Combine(outDir, rel));
            } else {
                string dest = Path.Combine(outDir, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                using (var fs = File.Create(dest)) {
                    int remaining = size; long b = startBlock;
                    while (remaining > 0) {
                        int n = Math.Min(0x1000, remaining);
                        fs.Write(d, (int)BlockAddr(b), n);
                        remaining -= n;
                        b = consecutive ? b + 1 : NextBlock(b);
                    }
                }
                log.AppendLine(string.Format("{0,-40} {1,10}", rel, size));
            }
            idx++;
        }
        return log.ToString();
    }
}
"@

New-Item -ItemType Directory -Force $OutDir | Out-Null
[Stfs]::Extract((Resolve-Path $Package).Path, (Resolve-Path $OutDir).Path)
