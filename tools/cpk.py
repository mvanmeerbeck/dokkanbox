"""Read CRIWARE's CPK archives and their CRILAYLA compression, the two layers that hide
   the effects the game ships inside the app rather than on its image server."""
import struct

TYPES = {0: ('B', 1), 1: ('b', 1), 2: ('>H', 2), 3: ('>h', 2), 4: ('>I', 4), 5: ('>i', 4),
         6: ('>Q', 8), 7: ('>q', 8), 8: ('>f', 4), 9: ('>d', 8), 0xA: ('>I', 4), 0xB: ('>II', 8)}


def utf(d, off):
    """the @UTF table: CRIWARE's little column store, used for both header and index"""
    assert d[off:off + 4] == b'@UTF', d[off:off + 4]
    base = off + 8
    rows_off, str_off, data_off, _ = struct.unpack_from('>4I', d, base)
    ncol, rowlen = struct.unpack_from('>HH', d, base + 16)
    nrow, = struct.unpack_from('>I', d, base + 20)

    def s(o):
        e = d.index(b'\0', base + str_off + o)
        return d[base + str_off + o:e].decode('utf-8', 'replace')

    p, cols = base + 24, []
    for _ in range(ncol):
        flags = d[p]; p += 1
        no, = struct.unpack_from('>I', d, p); p += 4
        storage, t, const = flags & 0xF0, flags & 0x0F, None
        if storage == 0x30:
            fmt, ln = TYPES[t]
            const = struct.unpack_from(fmt, d, p)[0]
            p += ln
        cols.append((storage, t, s(no), const))

    rows = []
    for r in range(nrow):
        q, row = base + rows_off + r * rowlen, {}
        for storage, t, nm, const in cols:
            if storage == 0x10:
                row[nm] = 0; continue
            if storage == 0x30:
                v = const
            else:
                fmt, ln = TYPES[t]
                if t == 0xB:
                    o, l = struct.unpack_from('>II', d, q); q += 8
                    v = d[base + data_off + o:base + data_off + o + l]
                else:
                    v = struct.unpack_from(fmt, d, q)[0]; q += ln
            row[nm] = s(v) if (t == 0xA and storage != 0x10) else v
        rows.append(row)
    return rows


def decompress(src):
    """CRILAYLA: an LZ that is written, and must be read, back to front"""
    assert src[:8] == b'CRILAYLA', src[:8]
    usize, csize = struct.unpack_from('<2I', src, 8)
    dest = bytearray(src[16 + csize:16 + csize + 0x100]) + bytearray(usize)
    end, pos = 16 + csize, [0]

    def bits(n):
        v = 0
        for _ in range(n):
            b = src[end - 1 - (pos[0] >> 3)]
            v = (v << 1) | ((b >> (7 - (pos[0] & 7))) & 1)
            pos[0] += 1
        return v

    LEVELS = (2, 3, 5, 8)
    out = len(dest) - 1
    while out >= 0x100:
        if bits(1):
            ref, length, lvl = out + bits(13) + 3, 3, 0
            while lvl < 4:
                step = bits(LEVELS[lvl]); length += step
                if step != (1 << LEVELS[lvl]) - 1:
                    break
                lvl += 1
            else:
                while True:
                    step = bits(8); length += step
                    if step != 255:
                        break
            for _ in range(length):
                dest[out] = dest[ref]; out -= 1; ref -= 1
        else:
            dest[out] = bits(8); out -= 1
    return bytes(dest)


def read(path):
    """every file in the archive, decompressed"""
    d = open(path, 'rb').read()
    hdr = utf(d, 0x10)[0]
    toc = utf(d, hdr['TocOffset'] + 0x10)          # each section carries its own 16-byte tag
    out = []
    for f in toc:
        o = hdr['TocOffset'] + f['FileOffset']      # offsets are relative to the index
        blob = d[o:o + f['FileSize']]
        if blob[:8] == b'CRILAYLA':
            blob = decompress(blob)
        out.append((f.get('DirName', ''), f['FileName'], blob))
    return out
