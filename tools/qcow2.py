"""Read a qcow2 image without converting it.

The emulator's disk is 58 GB of qcow2 and the Mac has less free space than a raw
conversion would need, so the guest blocks are resolved on the fly instead: qcow2 is
just a two-level page table from guest offsets to file offsets."""
import struct
import zlib

L2_MASK = 0x00FFFFFFFFFFFE00
COMPRESSED = 1 << 62


class Qcow2:
    def __init__(self, path):
        self.f = open(path, 'rb')
        h = self.f.read(112)
        assert h[:4] == b'QFI\xfb', 'pas un qcow2'
        g = lambda fmt, o: struct.unpack_from(fmt, h, o)[0]
        self.version = g('>I', 4)
        self.cluster_bits = g('>I', 20)
        self.cluster = 1 << self.cluster_bits
        self.size = g('>Q', 24)
        assert g('>I', 32) == 0, 'image chiffrée'
        self.l2_bits = self.cluster_bits - 3
        self.l2_size = 1 << self.l2_bits
        l1_size, l1_off = g('>I', 36), g('>Q', 40)
        self.f.seek(l1_off)
        self.l1 = struct.unpack('>%dQ' % l1_size, self.f.read(8 * l1_size))
        self._l2 = {}
        # compressed clusters pack their host offset and length into the entry itself
        self._cbits = self.cluster_bits - 8
        self._coff_mask = (1 << (62 - self._cbits)) - 1

    def _l2_table(self, off):
        t = self._l2.get(off)
        if t is None:
            self.f.seek(off)
            t = struct.unpack('>%dQ' % self.l2_size, self.f.read(8 * self.l2_size))
            if len(self._l2) > 512:
                self._l2.clear()
            self._l2[off] = t
        return t

    def cluster_at(self, guest_off):
        """the raw bytes of the cluster containing `guest_off`, zeros when unallocated"""
        idx = guest_off >> self.cluster_bits
        l1i, l2i = idx >> self.l2_bits, idx & (self.l2_size - 1)
        if l1i >= len(self.l1):
            return b'\0' * self.cluster
        l1e = self.l1[l1i] & L2_MASK
        if not l1e:
            return b'\0' * self.cluster
        e = self._l2_table(l1e)[l2i]
        if e & COMPRESSED:
            nsec = (e >> (62 - self._cbits)) & ((1 << self._cbits) - 1)
            off = e & self._coff_mask
            self.f.seek(off)
            raw = self.f.read((nsec + 1) * 512 + 512)
            return zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw, self.cluster)
        host = e & L2_MASK
        if not host:
            return b'\0' * self.cluster
        self.f.seek(host)
        b = self.f.read(self.cluster)
        return b + b'\0' * (self.cluster - len(b))

    def read(self, off, length):
        out = bytearray()
        while length > 0:
            base = off & ~(self.cluster - 1)
            skip = off - base
            take = min(self.cluster - skip, length)
            out += self.cluster_at(base)[skip:skip + take]
            off += take
            length -= take
        return bytes(out)


class Window:
    """a byte range of a disk, so a partition reads like an image of its own"""

    def __init__(self, disk, start, length=None):
        self.disk, self.start = disk, start
        self.size = length if length is not None else disk.size - start

    def read(self, off, length):
        return self.disk.read(self.start + off, length)
