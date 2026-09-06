"""Just enough ext4 to walk a path and pull one file out of an Android /data image.

Read-only, extent-based, no bitmap or journal handling: the point is to reach a single
known file without touching the emulator or converting its disk."""
import struct

EXTENTS_FL = 0x80000
INLINE_FL = 0x10000000
ROOT_INO = 2


class Ext4:
    def __init__(self, dev):
        self.dev = dev
        sb = dev.read(0x400, 1024)
        assert struct.unpack_from('<H', sb, 0x38)[0] == 0xEF53, 'pas de superbloc ext4'
        u32 = lambda o: struct.unpack_from('<I', sb, o)[0]
        u16 = lambda o: struct.unpack_from('<H', sb, o)[0]
        self.block_size = 1024 << u32(0x18)
        self.blocks_per_group = u32(0x20)
        self.inodes_per_group = u32(0x28)
        self.inode_size = u16(0x58) or 128
        self.first_data_block = u32(0x14)
        self.incompat = u32(0x60)
        self.desc_size = u16(0xFE) if (self.incompat & 0x80) else 32
        if self.desc_size < 32:
            self.desc_size = 32
        self.inode_count = u32(0x00)

    def block(self, n, count=1):
        return self.dev.read(n * self.block_size, count * self.block_size)

    def _group_desc(self, g):
        gd_block = self.first_data_block + 1 if self.block_size == 1024 else 1
        off = gd_block * self.block_size + g * self.desc_size
        return self.dev.read(off, self.desc_size)

    def inode(self, ino):
        g, i = divmod(ino - 1, self.inodes_per_group)
        d = self._group_desc(g)
        table = struct.unpack_from('<I', d, 0x08)[0]
        if self.desc_size >= 64:
            table |= struct.unpack_from('<I', d, 0x28)[0] << 32
        off = table * self.block_size + i * self.inode_size
        return self.dev.read(off, self.inode_size)

    # ---- where an inode's bytes live ---------------------------------------
    def _extents(self, node, out):
        assert struct.unpack_from('<H', node, 0)[0] == 0xF30A, 'en-tête d’extent absent'
        entries, depth = struct.unpack_from('<HH', node, 2)[0], struct.unpack_from('<H', node, 6)[0]
        for k in range(entries):
            e = node[12 + k * 12:24 + k * 12]
            if depth == 0:
                blk, ln, hi, lo = struct.unpack('<IHHI', e)
                start = lo | (hi << 32)
                out.append((blk, ln & 0x7FFF, start))       # bit 15 marks uninitialised
            else:
                blk, lo, hi, _ = struct.unpack('<IIHH', e)
                self._extents(self.block(lo | (hi << 32)), out)

    def read_file(self, ino_bytes, size=None):
        flags = struct.unpack_from('<I', ino_bytes, 0x20)[0]
        if size is None:
            size = struct.unpack_from('<I', ino_bytes, 0x04)[0] \
                | (struct.unpack_from('<I', ino_bytes, 0x6C)[0] << 32)
        if flags & INLINE_FL:
            return ino_bytes[0x28:0x28 + min(size, 60)]
        assert flags & EXTENTS_FL, 'inode sans extents (blocs indirects non gérés)'
        runs = []
        self._extents(ino_bytes[0x28:0x28 + 60], runs)
        out = bytearray(size)
        for logical, length, phys in runs:
            for j in range(length):
                pos = (logical + j) * self.block_size
                if pos >= size:
                    break
                chunk = self.block(phys + j)
                out[pos:pos + min(self.block_size, size - pos)] = chunk[:max(0, min(self.block_size, size - pos))]
        return bytes(out)

    # ---- directories --------------------------------------------------------
    def listdir(self, ino):
        raw = self.read_file(self.inode(ino))
        names = {}
        for start in range(0, len(raw), self.block_size):
            blk, p = raw[start:start + self.block_size], 0
            while p + 8 <= len(blk):
                child, rec_len, name_len, ftype = struct.unpack_from('<IHBB', blk, p)
                if rec_len < 8:
                    break
                if child and name_len:
                    nm = blk[p + 8:p + 8 + name_len].decode('utf-8', 'replace')
                    if nm not in ('.', '..'):
                        names[nm] = (child, ftype)
                p += rec_len
        return names

    def resolve(self, path):
        ino = ROOT_INO
        for part in [p for p in path.strip('/').split('/') if p]:
            entry = self.listdir(ino).get(part)
            if entry is None:
                raise FileNotFoundError(part + ' absent de ' + path)
            ino = entry[0]
        return ino

    def cat(self, path):
        return self.read_file(self.inode(self.resolve(path)))
