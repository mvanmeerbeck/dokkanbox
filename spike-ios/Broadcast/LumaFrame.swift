import CoreVideo

/// A borrowed view of one screen frame's brightness channel.
///
/// Nothing is copied: the pointer belongs to the pixel buffer the caller has locked, and stops
/// being valid the moment it unlocks. That is the whole reason the scanner needs no storage.
struct LumaFrame {
    let base: UnsafePointer<UInt8>
    let width: Int        // pixels
    let height: Int       // pixels
    let stride: Int       // bytes per row
    let pixelStride: Int  // bytes per pixel

    @inline(__always)
    func at(_ x: Int, _ y: Int) -> Int32 {
        Int32(base[y * stride + x * pixelStride])
    }

    /// Bi-planar YUV exposes brightness as plane 0; for BGRA the green byte stands in closely
    /// enough, since every measurement here is a gradient or a normalised correlation.
    static func borrowing(_ buffer: CVPixelBuffer) -> LumaFrame? {
        if CVPixelBufferIsPlanar(buffer) {
            guard let base = CVPixelBufferGetBaseAddressOfPlane(buffer, 0) else { return nil }
            return LumaFrame(base: base.assumingMemoryBound(to: UInt8.self),
                             width: CVPixelBufferGetWidthOfPlane(buffer, 0),
                             height: CVPixelBufferGetHeightOfPlane(buffer, 0),
                             stride: CVPixelBufferGetBytesPerRowOfPlane(buffer, 0),
                             pixelStride: 1)
        }
        guard CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_32BGRA,
              let base = CVPixelBufferGetBaseAddress(buffer) else { return nil }
        return LumaFrame(base: base.assumingMemoryBound(to: UInt8.self).advanced(by: 1),
                         width: CVPixelBufferGetWidth(buffer),
                         height: CVPixelBufferGetHeight(buffer),
                         stride: CVPixelBufferGetBytesPerRow(buffer),
                         pixelStride: 4)
    }
}
