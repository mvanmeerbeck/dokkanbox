import CoreGraphics
import CoreVideo
import Foundation
import ImageIO

// Runs the very same Detector the broadcast extension uses, but fed from PNG frames on the Mac.
// Lets the detection logic be validated before an iPhone build exists.

func pixelBuffer(fromPNG url: URL) -> CVPixelBuffer? {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return nil }
    let width = image.width, height = image.height
    var buffer: CVPixelBuffer?
    let attributes: [CFString: Any] = [kCVPixelBufferCGImageCompatibilityKey: true,
                                       kCVPixelBufferCGBitmapContextCompatibilityKey: true]
    guard CVPixelBufferCreate(kCFAllocatorDefault, width, height,
                              kCVPixelFormatType_32BGRA, attributes as CFDictionary, &buffer) == kCVReturnSuccess,
          let pb = buffer else { return nil }
    CVPixelBufferLockBaseAddress(pb, [])
    defer { CVPixelBufferUnlockBaseAddress(pb, []) }
    guard let context = CGContext(data: CVPixelBufferGetBaseAddress(pb),
                                  width: width, height: height, bitsPerComponent: 8,
                                  bytesPerRow: CVPixelBufferGetBytesPerRow(pb),
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue
                                      | CGBitmapInfo.byteOrder32Little.rawValue) else { return nil }
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    return pb
}

let arguments = CommandLine.arguments
guard arguments.count > 1 else {
    FileHandle.standardError.write(Data("usage: harness <frames-directory> [stride]\n".utf8))
    exit(2)
}
let directory = URL(fileURLWithPath: arguments[1])
let frameStride = arguments.count > 2 ? Int(arguments[2]) ?? 1 : 1

let frames = ((try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? [])
    .filter { $0.pathExtension.lowercased() == "png" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }
    .enumerated().filter { $0.offset % frameStride == 0 }.map { $0.element }

guard !frames.isEmpty else {
    FileHandle.standardError.write(Data("no PNG frames in \(directory.path)\n".utf8))
    exit(1)
}

let detector = Detector()
if let packPath = ProcessInfo.processInfo.environment["REFPACK"] {
    guard let recognizer = Recognizer(packURL: URL(fileURLWithPath: packPath)) else {
        FileHandle.standardError.write(Data("could not open pack at \(packPath)\n".utf8))
        exit(1)
    }
    if let radius = ProcessInfo.processInfo.environment["RADIUS"].flatMap(Int.init) {
        recognizer.searchRadius = radius
    }
    if let shortlist = ProcessInfo.processInfo.environment["SHORTLIST"].flatMap(Int.init) {
        recognizer.shortlistSize = shortlist
    }
    detector.recognizer = recognizer
    print("reference pack \(recognizer.cardCount) cards, radius \(recognizer.searchRadius), shortlist \(recognizer.shortlistSize)")
}
var totalSeconds = 0.0
var slowestMilliseconds = 0.0

for url in frames {
    guard let pb = pixelBuffer(fromPNG: url) else { continue }
    let began = CFAbsoluteTimeGetCurrent()
    detector.process(pb)
    let elapsed = CFAbsoluteTimeGetCurrent() - began
    totalSeconds += elapsed
    slowestMilliseconds = max(slowestMilliseconds, elapsed * 1000)
}

let averageMilliseconds = totalSeconds / Double(frames.count) * 1000
print("""
    frames        \(frames.count) (every \(frameStride) of the directory)
    size          \(detector.frameWidth) x \(detector.frameHeight)
    grid found    \(detector.framesWithGrid)
    unique tiles  \(detector.uniqueTiles)
    scrolled      \(Int(detector.scrolledPixels)) px
    gap events    \(detector.gapEvents)
    per frame     avg \(String(format: "%.1f", averageMilliseconds)) ms, max \(String(format: "%.1f", slowestMilliseconds)) ms
    """)

if detector.recognizer != nil {
    let perTile = detector.tilesInspected > 0
        ? detector.recognitionSeconds / Double(detector.tilesInspected) * 1000 : 0
    print("""
        ---
        tiles         \(detector.tilesInspected)
        identified    \(detector.tilesInspected - detector.tilesNeedingReview)
        review        \(detector.tilesNeedingReview)
        unique cards  \(detector.identifiedCards.count)
        per tile      \(String(format: "%.2f", perTile)) ms
        """)
}
