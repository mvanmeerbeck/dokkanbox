import CoreVideo
import Foundation

/// Throwaway spike detector: finds the Dokkan character-list grid in a live screen frame,
/// tracks how far the list scrolled between frames, and fingerprints each tile so repeated
/// sightings of the same card collapse to one entry.
///
/// Deliberately holds no frame: every buffer is read once and released by the caller.
/// The only state that grows is the fingerprint list, a few bytes per distinct card.
final class Detector {

    // MARK: Reference geometry (measured on a 750 x 1334 portrait screenshot)

    private static let refWidth = 750.0
    private static let refArt = 146.0        // side of the tile artwork box
    private static let refColsX = [0.0, 151.0, 302.0, 453.0, 604.0]
    private static let refGridTop = 160.0    // below the two filter buttons
    private static let refGridBottom = 1062.0 // above the page controls

    // Scaled to the frame actually received.
    private var scale = 1.0
    private var art = 146
    private var period = 176
    private var colsX = [0, 151, 302, 453, 604]
    private var gridTop = 160
    private var gridBottom = 1062
    private var template: [Float] = GridPhase.template

    // MARK: Running results

    private(set) var framesSeen = 0
    private(set) var framesWithGrid = 0
    private(set) var uniqueTiles = 0
    private(set) var scrolledPixels = 0.0
    private(set) var gapEvents = 0
    private(set) var lastPhaseCorrelation: Float = 0
    private(set) var frameWidth = 0
    private(set) var frameHeight = 0

    private var fingerprints: [UInt64] = []
    private var previousProfile: [Float] = []

    /// When set, tiles are identified against the reference pack instead of merely fingerprinted.
    var recognizer: Recognizer?
    private(set) var identifiedCards = Set<UInt32>()

    /// Deciding frame by frame throws away the good readings with the bad: while the box
    /// scrolls, the same tile is blurred on some frames and sharp on others, and a card that
    /// never happens to be sharp when it is looked at is simply lost. Measured on a full box:
    /// 404 cards found out of 553. So the verdict is kept per card, not per frame — the best
    /// score a card ever reaches, and how many times it was seen at all. A card seen thirty
    /// times only has to be sharp once.
    ///
    /// Taking a maximum over tens of thousands of readings does invite noise, so a card must
    /// also have been proposed more than once: a real tile is seen for dozens of frames as it
    /// crosses the screen, a fluke appears once and never again.
    struct Evidence { var best: Float; var margin: Float; var sightings: Int }
    private(set) var evidence: [UInt32: Evidence] = [:]
    private static let sightingScore: Float = 0.45
    private static let minimumSightings = 2
    private(set) var tilesInspected = 0
    private(set) var tilesNeedingReview = 0
    private(set) var recognitionSeconds = 0.0

    // MARK: Entry point

    func process(_ pixelBuffer: CVPixelBuffer) {
        framesSeen += 1
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }
        guard let luma = LumaFrame.borrowing(pixelBuffer) else { return }
        if luma.width != frameWidth || luma.height != frameHeight {
            frameWidth = luma.width
            frameHeight = luma.height
            configureGeometry(forWidth: luma.width)
            previousProfile = []
        }
        guard gridBottom - gridTop > period * 2 else { return }

        let profile = verticalGradientProfile(luma)
        trackScroll(against: profile)
        previousProfile = profile

        guard let firstRowTop = detectRowPhase(profile) else { return }
        framesWithGrid += 1
        fingerprintRows(luma, firstRowTop: firstRowTop)
    }

    // MARK: Frame access

    private func configureGeometry(forWidth width: Int) {
        scale = Double(width) / Detector.refWidth
        art = Int((Detector.refArt * scale).rounded())
        period = Int((Double(GridPhase.period) * scale).rounded())
        colsX = Detector.refColsX.map { Int(($0 * scale).rounded()) }
        gridTop = Int((Detector.refGridTop * scale).rounded())
        gridBottom = min(Int((Detector.refGridBottom * scale).rounded()), frameHeight - 1)
        template = resample(GridPhase.template, to: period)
    }

    private func resample(_ source: [Float], to count: Int) -> [Float] {
        guard count != source.count, count > 1 else { return source }
        var out = [Float](repeating: 0, count: count)
        for i in 0..<count {
            let position = Double(i) * Double(source.count) / Double(count)
            out[i] = source[min(source.count - 1, Int(position))]
        }
        return normalised(out)
    }

    private func normalised(_ values: [Float]) -> [Float] {
        var out = values
        let mean = out.reduce(0, +) / Float(out.count)
        var norm: Float = 0
        for i in out.indices { out[i] -= mean; norm += out[i] * out[i] }
        norm = norm.squareRoot()
        guard norm > 0 else { return out }
        for i in out.indices { out[i] /= norm }
        return out
    }

    // MARK: Grid detection

    /// Strength of horizontal edges on each scanline: rows of tiles produce a strong,
    /// strictly periodic signature that survives compression and motion blur.
    private func verticalGradientProfile(_ luma: LumaFrame) -> [Float] {
        let step = max(1, Int(4 * scale))
        var profile = [Float](repeating: 0, count: gridBottom - gridTop)
        for y in gridTop..<gridBottom {
            guard y > 0, y + 1 < luma.height else { continue }
            var sum: Int32 = 0
            var x = 0
            while x < luma.width {
                sum += abs(luma.at(x, y + 1) - luma.at(x, y - 1))
                x += step
            }
            profile[y - gridTop] = Float(sum)
        }
        return profile
    }

    /// Folds the profile at the known row period for every candidate phase and keeps the fold
    /// that best matches the reference row signature. Returns nil when no grid is on screen.
    private func detectRowPhase(_ profile: [Float]) -> Int? {
        var best: (correlation: Float, phase: Int) = (-1, 0)
        for phase in 0..<period {
            let folds = (profile.count - phase) / period
            guard folds >= 2 else { continue }
            var fold = [Float](repeating: 0, count: period)
            for k in 0..<folds {
                let offset = phase + k * period
                for i in 0..<period { fold[i] += profile[offset + i] }
            }
            var correlation: Float = 0
            let unit = normalised(fold)
            for i in 0..<period { correlation += unit[i] * template[i] }
            if correlation > best.correlation { best = (correlation, phase) }
        }
        lastPhaseCorrelation = best.correlation
        guard best.correlation >= 0.5 else { return nil }
        return gridTop + best.phase
    }

    /// Estimates vertical scroll by sliding the previous profile over the current one.
    /// A jump larger than one row means content passed by unprocessed, which the caller
    /// surfaces to the user rather than silently losing cards.
    private func trackScroll(against profile: [Float]) {
        guard previousProfile.count == profile.count, profile.count > 0 else { return }
        let limit = min(period, profile.count / 3)
        var best: (score: Float, shift: Int) = (-Float.greatestFiniteMagnitude, 0)
        for shift in -limit...limit {
            var score: Float = 0
            var count = 0
            var i = max(0, -shift)
            let end = min(profile.count, profile.count - shift)
            while i < end {
                score += previousProfile[i + shift] * profile[i]
                count += 1
                i += 2
            }
            guard count > 0 else { continue }
            let normalisedScore = score / Float(count)
            if normalisedScore > best.score { best = (normalisedScore, shift) }
        }
        let distance = abs(Double(best.shift))
        scrolledPixels += distance
        if distance > Double(period) { gapEvents += 1 }
    }

    // MARK: Tile fingerprints

    private func fingerprintRows(_ luma: LumaFrame, firstRowTop: Int) {
        var top = firstRowTop - period
        while top < gridBottom {
            defer { top += period }
            guard top >= gridTop, top + art <= gridBottom, top + art <= luma.height else { continue }
            for x in colsX where x + art <= luma.width {
                tilesInspected += 1
                if let recognizer {
                    let began = CFAbsoluteTimeGetCurrent()
                    let match = recognizer.identify(luma, x: x, y: top)
                    recognitionSeconds += CFAbsoluteTimeGetCurrent() - began
                    if let match {
                        var seen = evidence[match.cardID]
                            ?? Evidence(best: -1, margin: 0, sightings: 0)
                        if match.score > seen.best {
                            seen.best = match.score
                            seen.margin = match.margin
                        }
                        if match.score >= Detector.sightingScore { seen.sightings += 1 }
                        evidence[match.cardID] = seen
                        if seen.best >= Recognizer.acceptScore,
                           seen.margin >= Recognizer.acceptMargin,
                           seen.sightings >= Detector.minimumSightings {
                            identifiedCards.insert(match.cardID)
                        } else {
                            tilesNeedingReview += 1
                        }
                    } else {
                        tilesNeedingReview += 1
                    }
                    continue
                }
                guard let print = fingerprint(luma, x: x, y: top) else { continue }
                register(print)
            }
        }
    }

    /// Average hash of the tile's central artwork, ignoring the frame and the corner badges.
    private func fingerprint(_ luma: LumaFrame, x: Int, y: Int) -> UInt64? {
        let inset = Int(Double(art) * 0.2)
        let side = art - inset * 2
        guard side >= 16 else { return nil }
        let cell = side / 8
        var cells = [Int32](repeating: 0, count: 64)
        var total: Int32 = 0
        for row in 0..<8 {
            for column in 0..<8 {
                var sum: Int32 = 0
                for dy in stride(from: 0, to: cell, by: 2) {
                    let sy = y + inset + row * cell + dy
                    for dx in stride(from: 0, to: cell, by: 2) {
                        sum += luma.at(x + inset + column * cell + dx, sy)
                    }
                }
                cells[row * 8 + column] = sum
                total += sum
            }
        }
        let mean = total / 64
        var bits: UInt64 = 0
        for i in 0..<64 where cells[i] > mean { bits |= (1 << UInt64(i)) }
        // An all-dark or all-flat tile carries no information: reject it.
        let ones = bits.nonzeroBitCount
        guard ones > 8, ones < 56 else { return nil }
        return bits
    }

    private func register(_ print: UInt64) {
        for existing in fingerprints where (existing ^ print).nonzeroBitCount <= 6 { return }
        fingerprints.append(print)
        uniqueTiles = fingerprints.count
    }
}
