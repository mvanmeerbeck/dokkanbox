import Accelerate
import Foundation

/// Identifies one tile of the character grid against the reference pack.
///
/// Two stages, cheap then exact. A gradient descriptor ranks all cards in a single matrix
/// product and keeps a handful of candidates; each survivor is then verified by a normalised
/// correlation that only counts the artwork's opaque pixels, so the type-coloured glow showing
/// through transparent artwork cannot skew the score.
///
/// The pack is memory-mapped: only the descriptors stay resident, and the operating system
/// pages in the few templates actually compared.
final class Recognizer {

    struct Match {
        let cardID: UInt32
        let score: Float       // masked correlation of the winner
        let margin: Float      // lead over the best rival
        let offset: (x: Int, y: Int)
    }

    /// Tiles below these are handed to the user for confirmation instead of being trusted.
    static let acceptScore: Float = 0.55
    static let acceptMargin: Float = 0.08

    /// How many descriptor candidates get the exact check, and how far the exact check looks
    /// around the position the grid predicts. Both trade accuracy for time.
    var shortlistSize = 4
    var searchRadius = 1

    private let mapping: UnsafeRawPointer
    private let mappedBytes: Int
    let cardCount: Int
    private let dimension: Int
    private let side: Int
    private let artBox: Int

    private let ids: UnsafePointer<UInt32>
    private let descriptors: UnsafePointer<Float>
    private let templates: UnsafePointer<UInt8>
    private let masks: UnsafePointer<UInt8>
    private let templateStats: UnsafePointer<Float>   // maskCount, sum(M*T), sum(M*T*T)

    private var scores: [Float]
    private var query: [Float]

    // MARK: Loading

    init?(packURL: URL, artBox: Int = 146) {
        guard let handle = try? FileHandle(forReadingFrom: packURL) else { return nil }
        defer { try? handle.close() }
        let bytes = (try? FileManager.default.attributesOfItem(atPath: packURL.path)[.size] as? Int) ?? nil
        guard let total = bytes, total > 24 else { return nil }
        guard let region = mmap(nil, total, PROT_READ, MAP_PRIVATE, handle.fileDescriptor, 0),
              region != MAP_FAILED else { return nil }

        let raw = UnsafeRawPointer(region)
        guard raw.loadUnaligned(as: UInt32.self) == 0x4B50_4B44 else { munmap(region, total); return nil } // "DKPK"
        let version = raw.loadUnaligned(fromByteOffset: 4, as: UInt32.self)
        guard version == 1 else { munmap(region, total); return nil }

        let count = Int(raw.loadUnaligned(fromByteOffset: 8, as: UInt32.self))
        let dim = Int(raw.loadUnaligned(fromByteOffset: 12, as: UInt32.self))
        let templateSide = Int(raw.loadUnaligned(fromByteOffset: 16, as: UInt32.self))
        let plane = templateSide * templateSide

        var cursor = 20
        let idsBase = raw.advanced(by: cursor).assumingMemoryBound(to: UInt32.self); cursor += count * 4
        let descBase = raw.advanced(by: cursor).assumingMemoryBound(to: Float.self); cursor += count * dim * 4
        let tplBase = raw.advanced(by: cursor).assumingMemoryBound(to: UInt8.self); cursor += count * plane
        let maskBase = raw.advanced(by: cursor).assumingMemoryBound(to: UInt8.self); cursor += count * plane
        let statBase = raw.advanced(by: cursor).assumingMemoryBound(to: Float.self); cursor += count * 12
        guard cursor <= total else { munmap(region, total); return nil }

        self.mapping = raw
        self.mappedBytes = total
        self.cardCount = count
        self.dimension = dim
        self.side = templateSide
        self.artBox = artBox
        self.ids = idsBase
        self.descriptors = descBase
        self.templates = tplBase
        self.masks = maskBase
        self.templateStats = statBase
        self.scores = [Float](repeating: 0, count: count)
        self.query = [Float](repeating: 0, count: dim)
    }

    deinit { munmap(UnsafeMutableRawPointer(mutating: mapping), mappedBytes) }

    // MARK: Identification

    /// `x`, `y` is the top-left of the tile's artwork box in the frame.
    func identify(_ frame: LumaFrame, x: Int, y: Int) -> Match? {
        let inset = (artBox - side) / 2
        guard x + inset - searchRadius >= 0, y + inset - searchRadius >= 0,
              x + inset + side + searchRadius <= frame.width,
              y + inset + side + searchRadius <= frame.height else { return nil }

        buildDescriptor(frame, originX: x + inset, originY: y + inset)
        let shortlist = rankCandidates()

        var best = (score: -Float.greatestFiniteMagnitude, index: -1, dx: 0, dy: 0)
        var runnerUp = -Float.greatestFiniteMagnitude
        for candidate in shortlist {
            var candidateBest = -Float.greatestFiniteMagnitude
            var bestOffset = (0, 0)
            for dy in -searchRadius...searchRadius {
                for dx in -searchRadius...searchRadius {
                    let value = maskedCorrelation(frame, candidate,
                                                  originX: x + inset + dx, originY: y + inset + dy)
                    if value > candidateBest { candidateBest = value; bestOffset = (dx, dy) }
                }
            }
            if candidateBest > best.score {
                runnerUp = best.score
                best = (candidateBest, candidate, bestOffset.0, bestOffset.1)
            } else if candidateBest > runnerUp {
                runnerUp = candidateBest
            }
        }
        guard best.index >= 0 else { return nil }
        return Match(cardID: ids[best.index],
                     score: best.score,
                     margin: best.score - max(runnerUp, 0),
                     offset: (best.dx, best.dy))
    }

    // MARK: Stage one, gradient descriptor

    /// Horizontal and vertical Sobel responses, box-averaged into an 8x8 grid each.
    /// The template side is a whole multiple of 8, so this is a plain average with no
    /// interpolation, which keeps the exporter and this code bit-comparable.
    private func buildDescriptor(_ frame: LumaFrame, originX: Int, originY: Int) {
        // Two gradient planes share the descriptor, so each is a square grid of dimension/2 cells.
        let cells = Int((Double(dimension) / 2).squareRoot().rounded())
        let cell = side / cells
        var horizontal = [Float](repeating: 0, count: cells * cells)
        var vertical = [Float](repeating: 0, count: cells * cells)

        // Sobel needs one pixel of context; mirror at the edges the way the exporter does.
        @inline(__always) func sample(_ column: Int, _ row: Int) -> Int32 {
            let c = column < 0 ? 1 : (column >= side ? side - 2 : column)
            let r = row < 0 ? 1 : (row >= side ? side - 2 : row)
            return frame.at(originX + c, originY + r)
        }

        for row in 0..<side {
            let cellRow = row / cell
            for column in 0..<side {
                let tl = sample(column - 1, row - 1), tc = sample(column, row - 1), tr = sample(column + 1, row - 1)
                let ml = sample(column - 1, row), mr = sample(column + 1, row)
                let bl = sample(column - 1, row + 1), bc = sample(column, row + 1), br = sample(column + 1, row + 1)
                let gxRaw: Int32 = (tr - tl) + 2 * (mr - ml) + (br - bl)
                let gyRaw: Int32 = (bl - tl) + 2 * (bc - tc) + (br - tr)
                let gx = Float(gxRaw)
                let gy = Float(gyRaw)
                let slot = cellRow * cells + column / cell
                horizontal[slot] += gx
                vertical[slot] += gy
            }
        }

        let cellArea = Float(cell * cell)
        for i in 0..<(cells * cells) {
            query[i] = horizontal[i] / cellArea
            query[cells * cells + i] = vertical[i] / cellArea
        }
        normaliseQuery()
    }

    private func normaliseQuery() {
        var mean: Float = 0
        vDSP_meanv(query, 1, &mean, vDSP_Length(dimension))
        var negated = -mean
        vDSP_vsadd(query, 1, &negated, &query, 1, vDSP_Length(dimension))
        var norm: Float = 0
        vDSP_svesq(query, 1, &norm, vDSP_Length(dimension))
        norm = norm.squareRoot()
        guard norm > 0 else { return }
        var inverse = 1 / norm
        vDSP_vsmul(query, 1, &inverse, &query, 1, vDSP_Length(dimension))
    }

    /// One matrix-vector product scores every card at once, then a partial selection keeps the best few.
    private func rankCandidates() -> [Int] {
        cblas_sgemv(CblasRowMajor, CblasNoTrans,
                    Int32(cardCount), Int32(dimension), 1,
                    descriptors, Int32(dimension),
                    query, 1, 0, &scores, 1)
        var best = [Int]()
        best.reserveCapacity(shortlistSize)
        var worstKept: Float = -.greatestFiniteMagnitude
        for index in 0..<cardCount {
            let score = scores[index]
            if best.count < shortlistSize {
                best.append(index)
                if best.count == shortlistSize {
                    best.sort { scores[$0] > scores[$1] }
                    worstKept = scores[best[shortlistSize - 1]]
                }
            } else if score > worstKept {
                best[shortlistSize - 1] = index
                var position = shortlistSize - 1
                while position > 0, scores[best[position]] > scores[best[position - 1]] {
                    best.swapAt(position, position - 1)
                    position -= 1
                }
                worstKept = scores[best[shortlistSize - 1]]
            }
        }
        return best
    }

    // MARK: Stage two, masked correlation

    /// Pearson correlation between the frame patch and the template, restricted to the pixels
    /// the artwork actually paints. Template sums are precomputed in the pack.
    private func maskedCorrelation(_ frame: LumaFrame, _ index: Int, originX: Int, originY: Int) -> Float {
        let plane = side * side
        let template = templates + index * plane
        let mask = masks + index * plane
        var sumImage: Float = 0, sumImageSquared: Float = 0, sumImageTemplate: Float = 0

        for row in 0..<side {
            let rowBase = frame.base + (originY + row) * frame.stride
            let templateRow = template + row * side
            let maskRow = mask + row * side
            for column in 0..<side {
                let keep = Float(maskRow[column] >> 7)          // 0 or 1, no branch
                let pixel = Float(rowBase[(originX + column) * frame.pixelStride])
                let reference = Float(templateRow[column])
                sumImage += keep * pixel
                sumImageSquared += keep * pixel * pixel
                sumImageTemplate += keep * pixel * reference
            }
        }

        let count = templateStats[index * 3]
        let sumTemplate = templateStats[index * 3 + 1]
        let sumTemplateSquared = templateStats[index * 3 + 2]
        guard count > 0 else { return -1 }

        let numerator = sumImageTemplate - sumImage * sumTemplate / count
        let imageVariance = sumImageSquared - sumImage * sumImage / count
        let templateVariance = sumTemplateSquared - sumTemplate * sumTemplate / count
        guard imageVariance > 0, templateVariance > 0 else { return -1 }
        return numerator / (imageVariance * templateVariance).squareRoot()
    }
}
