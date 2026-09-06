import ReplayKit
import os

/// Receives the live screen while the player scrolls their box in Dokkan.
///
/// The whole point of the spike is what this class does NOT do: no frame is written to disk,
/// queued, or uploaded. Each buffer is measured and dropped, so memory stays flat however
/// long the capture runs. Progress is published through the unified log, which the Mac reads
/// with `log stream`; a shipping build would post it to the app through an App Group instead.
class SampleHandler: RPBroadcastSampleHandler {

    private let detector = Detector()
    private let log = Logger(subsystem: "io.keyban.dokkanscan", category: "scan")

    private var started = CFAbsoluteTimeGetCurrent()
    private var videoFrames = 0
    private var processingSeconds = 0.0
    private var slowestFrameMs = 0.0
    private var peakFootprintMB = 0.0

    /// The unified log is awkward to read from a Mac and silent when the extension dies
    /// early. Appending to a file inside the extension's own container is not elegant, but
    /// `devicectl device copy from` pulls it afterwards whatever happened.
    private static let trace: URL? = try? FileManager.default
        .url(for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        .appendingPathComponent("scan.log")

    private func note(_ line: String) {
        log.notice("\(line, privacy: .public)")
        guard let url = Self.trace else { return }
        let stamped = ISO8601DateFormatter().string(from: Date()) + " " + line + "\n"
        if let handle = try? FileHandle(forWritingTo: url) {
            handle.seekToEndOfFile(); handle.write(Data(stamped.utf8)); try? handle.close()
        } else {
            try? Data(stamped.utf8).write(to: url)
        }
    }

    override func broadcastStarted(withSetupInfo setupInfo: [String: NSObject]?) {
        started = CFAbsoluteTimeGetCurrent()
        if let url = Bundle.main.url(forResource: "refpack", withExtension: "bin"),
           let recognizer = Recognizer(packURL: url) {
            detector.recognizer = recognizer
            note("SCAN start pack=\(recognizer.cardCount) cards mem=\(Self.footprintMB())")
        } else {
            note("SCAN start WITHOUT pack")
        }
    }

    override func processSampleBuffer(_ sampleBuffer: CMSampleBuffer, with type: RPSampleBufferType) {
        guard type == .video, let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        videoFrames += 1

        let began = CFAbsoluteTimeGetCurrent()
        detector.process(buffer)
        let elapsed = CFAbsoluteTimeGetCurrent() - began

        processingSeconds += elapsed
        slowestFrameMs = max(slowestFrameMs, elapsed * 1000)
        peakFootprintMB = max(peakFootprintMB, Self.footprintMB())

        if videoFrames % 30 == 0 { report(final: false) }
    }

    override func broadcastFinished() {
        report(final: true)
        // The counters say how many, never which. Without the list there is no way to tell a
        // card the scan never saw from one it saw and failed to name.
        let found = detector.identifiedCards.sorted()
        note("SCAN ids " + found.map(String.init).joined(separator: ","))
        let nearly = detector.evidence
            .filter { !detector.identifiedCards.contains($0.key) }
            .sorted { $0.value.best > $1.value.best }
            .prefix(60)
            .map { "\($0.key):\(String(format: "%.2f", $0.value.best))x\($0.value.sightings)" }
        note("SCAN near " + nearly.joined(separator: ","))
        log.notice("SCAN end")
    }

    private func report(final: Bool) {
        let wall = CFAbsoluteTimeGetCurrent() - started
        let fps = wall > 0 ? Double(videoFrames) / wall : 0
        let averageMs = videoFrames > 0 ? processingSeconds / Double(videoFrames) * 1000 : 0
        note("""
            SCAN \(final ? "final" : "tick") \
            frame=\(detector.frameWidth)x\(detector.frameHeight) \
            frames=\(videoFrames) grid=\(detector.framesWithGrid) \
            fps=\(String(format: "%.1f", fps)) \
            avg_ms=\(String(format: "%.2f", averageMs)) \
            max_ms=\(String(format: "%.1f", slowestFrameMs)) \
            tiles=\(detector.uniqueTiles) seen=\(detector.tilesInspected) \
            cards=\(detector.identifiedCards.count) cand=\(detector.evidence.count) \
            review=\(detector.tilesNeedingReview) \
            scrolled=\(Int(detector.scrolledPixels)) gaps=\(detector.gapEvents) \
            mem_mb=\(String(format: "%.1f", Self.footprintMB())) \
            peak_mb=\(String(format: "%.1f", peakFootprintMB))
            """)
    }

    /// Physical footprint is the figure iOS compares against the extension's memory limit.
    private static func footprintMB() -> Double {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<natural_t>.size)
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return -1 }
        return Double(info.phys_footprint) / (1024 * 1024)
    }
}
